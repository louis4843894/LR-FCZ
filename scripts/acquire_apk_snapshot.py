"""Acquire an immutable APK-only snapshot from one explicitly selected device."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
PACKAGE_RE = re.compile(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+\Z")
TAIPEI_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Taipei")


class AcquisitionError(Exception):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_adb(adb: Path, serial: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            [str(adb), "-s", serial, *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AcquisitionError(f"ADB command failed: {error}") from error
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AcquisitionError(
            f"adb -s {serial} {' '.join(arguments)} failed "
            f"(exit {result.returncode}): {detail or 'no error text'}"
        )
    return result


def get_property(adb: Path, serial: str, name: str) -> str:
    value = run_adb(adb, serial, "shell", "getprop", name).stdout.strip()
    if not value:
        raise AcquisitionError(f"Android property {name} is empty")
    return value


def make_snapshot_id() -> str:
    timestamp = datetime.now(TAIPEI_TIMEZONE).strftime("%Y%m%dT%H%M%S%f")
    return f"lr_{timestamp}_{uuid.uuid4().hex[:8]}"


def write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def acquire(adb: Path, serial: str, package_name: str, snapshot_id: str) -> Path:
    if not PACKAGE_RE.fullmatch(package_name):
        raise AcquisitionError("package name contains unsupported characters")
    if not SNAPSHOT_RE.fullmatch(snapshot_id):
        raise AcquisitionError("snapshot ID contains unsupported characters")
    if not adb.is_file():
        raise AcquisitionError(f"adb.exe not found: {adb}")

    snapshot_dir = ROOT / "data" / "raw" / snapshot_id
    try:
        (snapshot_dir / "apk").mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise AcquisitionError(
            f"snapshot already exists; refusing to overwrite: {snapshot_dir}"
        ) from error

    acquired_at = datetime.now(TAIPEI_TIMEZONE).isoformat()
    manifest: dict[str, object] = {
        "snapshotId": snapshot_id,
        "acquiredAt": acquired_at,
        "manifestGeneratedAt": datetime.now(TAIPEI_TIMEZONE).isoformat(),
        "snapshotStatus": "partial",
        "complete": False,
        "package": {"name": package_name, "versionName": None, "versionCode": None},
        "device": {"serial": serial},
        "files": [],
        "resourceDirectories": [],
        "errors": [],
    }

    try:
        state = run_adb(adb, serial, "get-state").stdout.strip()
        if state != "device":
            raise AcquisitionError(
                f"selected device is not ready: adb -s {serial} get-state returned {state!r}"
            )

        installed = run_adb(adb, serial, "shell", "pm", "list", "packages", "-3")
        installed_packages = {
            line.removeprefix("package:").strip()
            for line in installed.stdout.splitlines()
            if line.strip()
        }
        if package_name not in installed_packages:
            raise AcquisitionError(
                f"confirmed package {package_name!r} is not in the device's third-party app list"
            )

        package_dump = run_adb(adb, serial, "shell", "dumpsys", "package", package_name)
        version_code_match = re.search(
            r"(?m)^\s*versionCode=(\d+)\b", package_dump.stdout
        )
        version_name_match = re.search(
            r"(?m)^\s*versionName=([^\s]+)", package_dump.stdout
        )
        if version_code_match is None or version_name_match is None:
            raise AcquisitionError(
                "dumpsys package output did not contain both versionCode and versionName"
            )

        package_metadata = manifest["package"]
        if isinstance(package_metadata, dict):
            package_metadata["versionName"] = version_name_match.group(1)
            package_metadata["versionCode"] = int(version_code_match.group(1))

        device_metadata = manifest["device"]
        if isinstance(device_metadata, dict):
            device_metadata["model"] = get_property(adb, serial, "ro.product.model")
            device_metadata["androidVersion"] = get_property(
                adb, serial, "ro.build.version.release"
            )
            device_metadata["apiLevel"] = int(
                get_property(adb, serial, "ro.build.version.sdk")
            )
            device_metadata["abi"] = get_property(adb, serial, "ro.product.cpu.abi")
            supported_abis = get_property(adb, serial, "ro.product.cpu.abilist")
            device_metadata["supportedAbis"] = [
                abi.strip() for abi in supported_abis.split(",") if abi.strip()
            ]

        paths_output = run_adb(adb, serial, "shell", "pm", "path", package_name)
        remote_paths: list[str] = []
        for line in paths_output.stdout.splitlines():
            path = line.strip()
            if path.startswith("package:"):
                path = path[len("package:") :]
            if path.startswith("/") and path not in remote_paths:
                remote_paths.append(path)
        if not remote_paths or not any(PurePosixPath(path).name == "base.apk" for path in remote_paths):
            raise AcquisitionError("pm path did not identify a base.apk and split APK set")

        filenames: set[str] = set()
        file_entries: list[dict[str, object]] = []
        for remote_path in remote_paths:
            filename = PurePosixPath(remote_path).name
            if (
                not re.fullmatch(r"[A-Za-z0-9._-]+", filename)
                or filename in (".", "..")
                or filename in filenames
            ):
                raise AcquisitionError(
                    f"pm path returned an invalid or duplicate APK filename: {filename!r}"
                )
            filenames.add(filename)
            local_path = snapshot_dir / "apk" / filename
            run_adb(adb, serial, "pull", remote_path, str(local_path))
            file_entries.append(
                {
                    "path": local_path.relative_to(ROOT).as_posix(),
                    "bytes": local_path.stat().st_size,
                    "sha256": sha256_file(local_path),
                    "source": remote_path,
                    "snapshotId": snapshot_id,
                }
            )
        manifest["files"] = file_entries

        resource_directories: list[dict[str, object]] = []
        for candidate in (
            f"/sdcard/Android/data/{package_name}",
            f"/sdcard/Android/obb/{package_name}",
        ):
            try:
                result = subprocess.run(
                    [str(adb), "-s", serial, "shell", "ls", "-ld", candidate],
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                resource_directories.append(
                    {
                        "path": candidate,
                        "status": "unavailable",
                        "error": str(error),
                    }
                )
                continue
            if result.returncode == 0:
                resource_directories.append(
                    {
                        "path": candidate,
                        "status": "exists-and-readable",
                        "details": result.stdout.strip(),
                    }
                )
            else:
                resource_directories.append(
                    {
                        "path": candidate,
                        "status": "unavailable",
                        "error": (result.stderr or result.stdout).strip(),
                    }
                )
        manifest["resourceDirectories"] = resource_directories
        manifest["snapshotStatus"] = "complete"
        manifest["complete"] = True
        manifest["manifestGeneratedAt"] = datetime.now(TAIPEI_TIMEZONE).isoformat()
        write_manifest(snapshot_dir / "manifest.json", manifest)
    except AcquisitionError as error:
        errors = manifest["errors"]
        if isinstance(errors, list):
            errors.append(str(error))
        manifest["manifestGeneratedAt"] = datetime.now(TAIPEI_TIMEZONE).isoformat()
        write_manifest(snapshot_dir / "manifest.json", manifest)
        raise

    return snapshot_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", type=Path, required=True, help="absolute path to adb.exe")
    parser.add_argument("--serial", required=True, help="explicit emulator/device serial")
    parser.add_argument("--package", required=True, help="previously confirmed package name")
    parser.add_argument("--snapshot-id", help="unique ID; generated when omitted")
    args = parser.parse_args(argv)
    snapshot_id = args.snapshot_id or make_snapshot_id()
    adb = args.adb.resolve()
    try:
        output = acquire(adb, args.serial, args.package, snapshot_id)
    except AcquisitionError as error:
        print(f"Snapshot ID: {snapshot_id}", file=sys.stderr)
        print(f"Acquisition failed: {error}", file=sys.stderr)
        return 1
    print(f"Snapshot: {snapshot_id}")
    print(f"APK files and manifest: {output.relative_to(ROOT)}")
    print("Only APKs were exported; private application data was not read or copied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
