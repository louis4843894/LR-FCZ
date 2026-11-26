#!/usr/bin/env python3
"""Inventory raw game files and safely extract APK ZIP members."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import stat
import sys
import uuid
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw"
INVENTORY_ROOT = ROOT / "data" / "inventory"
EXTRACTED_ROOT = ROOT / "data" / "extracted"
MAX_FILES = 20_000
MAX_TOTAL_UNCOMPRESSED_BYTES = 1_073_741_824
MAX_SINGLE_FILE_BYTES = 536_870_912
MAX_TEXT_PARSE_BYTES = 16 * 1024 * 1024
SAMPLE_BYTES = 64 * 1024
ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
SQLITE_SIGNATURE = b"SQLite format 3\x00"
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


class UnsafeArchiveError(Exception):
    """Raised when an archive cannot be extracted within the safety policy."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_zip_file(path: Path) -> bool:
    with path.open("rb") as stream:
        return stream.read(4) in ZIP_SIGNATURES


def detect_format(path: Path) -> tuple[str, str]:
    size = path.stat().st_size
    with path.open("rb") as stream:
        head = stream.read(SAMPLE_BYTES)

    if head.startswith(ZIP_SIGNATURES):
        return "ZIP container", head[:16].hex()
    if head.startswith(SQLITE_SIGNATURE):
        return "SQLite", head[:16].hex()
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG image", head[:16].hex()
    if head.startswith(b"\xff\xd8\xff"):
        return "JPEG image", head[:16].hex()
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "GIF image", head[:16].hex()
    if head.startswith(b"BM"):
        return "BMP image", head[:16].hex()
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "WebP image", head[:16].hex()
    if head.startswith(b"dex\n"):
        return "DEX bytecode", head[:16].hex()
    if head.startswith(b"\x7fELF"):
        return "ELF binary", head[:16].hex()
    if head.startswith(b"OggS"):
        return "Ogg audio", head[:16].hex()
    if head.startswith(b"\x03\x00\x08\x00"):
        return "Android binary XML", head[:16].hex()
    if head.startswith(b"%PDF-"):
        return "PDF document", head[:16].hex()

    text_head = head.decode("utf-8-sig", errors="ignore").lstrip()
    if text_head.startswith(("{", "[")):
        if size <= MAX_TEXT_PARSE_BYTES:
            try:
                json.loads(path.read_text(encoding="utf-8-sig"))
                return "JSON", head[:16].hex()
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
        else:
            return "JSON-like text (over parse limit)", head[:16].hex()

    if text_head.startswith("<"):
        if size <= MAX_TEXT_PARSE_BYTES:
            try:
                ET.fromstring(path.read_bytes())
                return "XML", head[:16].hex()
            except (ET.ParseError, UnicodeDecodeError):
                pass
        else:
            return "XML-like text (over parse limit)", head[:16].hex()

    if b"\x00" not in head:
        try:
            text = head.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = ""
        if text:
            javascript_prefixes = (
                ";(function",
                "(function",
                "!function",
                "var ",
                "const ",
                "let ",
                "function ",
                "(()=>",
            )
            if text.startswith(javascript_prefixes) or "Object.defineProperty(" in text[:4096]:
                return "JavaScript text", head[:16].hex()
            try:
                dialect = csv.Sniffer().sniff(text[:16_384], delimiters=",\t;|")
                rows = list(csv.reader(text.splitlines()[:8], dialect))
                widths = {len(row) for row in rows if row}
                if len(rows) >= 2 and len(widths) == 1 and next(iter(widths), 0) >= 2:
                    return "CSV text (content heuristic)", head[:16].hex()
            except csv.Error:
                pass
            return "UTF-8 text", head[:16].hex()

    return "Other binary", head[:16].hex()


def safe_member_path(name: str, destination_root: Path) -> Path:
    if not name or "\x00" in name or "\\" in name or name.startswith("/"):
        raise UnsafeArchiveError(f"Unsafe archive path: {name!r}")

    parts = name.rstrip("/").split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise UnsafeArchiveError(f"Unsafe archive path: {name!r}")
    for part in parts:
        if ":" in part or part.endswith((".", " ")):
            raise UnsafeArchiveError(f"Unsafe Windows path component: {name!r}")
        if part.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
            raise UnsafeArchiveError(f"Reserved Windows path component: {name!r}")

    candidate = destination_root.joinpath(*parts).resolve()
    root_resolved = destination_root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise UnsafeArchiveError(f"Archive path escapes destination: {name!r}") from exc
    return candidate


def inspect_archive(archive_path: Path) -> tuple[list[zipfile.ZipInfo], int]:
    infos: list[zipfile.ZipInfo] = []
    seen: set[str] = set()
    total_bytes = 0

    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            safe_member_path(info.filename, Path("safe-root"))
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise UnsafeArchiveError(f"Symbolic link entry is not allowed: {info.filename!r}")
            if info.is_dir():
                continue
            if info.flag_bits & 0x1:
                raise UnsafeArchiveError(f"Encrypted ZIP member is not extracted: {info.filename!r}")
            if info.file_size < 0 or info.file_size > MAX_SINGLE_FILE_BYTES:
                raise UnsafeArchiveError(
                    f"Member exceeds per-file limit ({MAX_SINGLE_FILE_BYTES}): {info.filename!r}"
                )
            normalized = info.filename.casefold()
            if normalized in seen:
                raise UnsafeArchiveError(f"Duplicate archive path: {info.filename!r}")
            seen.add(normalized)
            total_bytes += info.file_size
            infos.append(info)

    if len(infos) > MAX_FILES:
        raise UnsafeArchiveError(f"Archive exceeds file-count limit ({MAX_FILES})")
    if total_bytes > MAX_TOTAL_UNCOMPRESSED_BYTES:
        raise UnsafeArchiveError(
            f"Archive exceeds expanded-size limit ({MAX_TOTAL_UNCOMPRESSED_BYTES} bytes)"
        )
    return infos, total_bytes


def hash_existing_tree(root: Path) -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise UnsafeArchiveError(f"Symlink found in extraction directory: {path}")
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            result[relative] = (path.stat().st_size, sha256_file(path))
    return result


def extract_archive(
    archive_path: Path,
    infos: list[zipfile.ZipInfo],
    destination: Path,
) -> tuple[dict[str, tuple[int, str]], bool]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    expected_names = {info.filename for info in infos}
    if destination.exists():
        existing = hash_existing_tree(destination)
        if set(existing) - expected_names:
            raise UnsafeArchiveError(
                f"Unexpected file in extraction directory; not overwriting: {destination}"
            )
    else:
        existing = {}
        destination.mkdir(parents=True)

    all_present = set(existing) == expected_names
    with zipfile.ZipFile(archive_path) as archive:
        for info in infos:
            target = safe_member_path(info.filename, destination)
            if info.filename in existing:
                size, digest = existing[info.filename]
                if size != info.file_size:
                    raise UnsafeArchiveError(
                        f"Existing extracted size differs from archive: {info.filename}"
                    )
                with archive.open(info) as source:
                    expected = hashlib.sha256()
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        expected.update(chunk)
                if digest != expected.hexdigest():
                    raise UnsafeArchiveError(
                        f"Existing extracted hash differs from archive: {info.filename}"
                    )
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise UnsafeArchiveError(
                    f"Unexpected existing path in extraction tree: {target}"
                )
            digest = hashlib.sha256()
            written = 0
            created = False
            try:
                with archive.open(info) as source:
                    with target.open("xb") as output:
                        created = True
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            written += len(chunk)
                            if written > info.file_size or written > MAX_SINGLE_FILE_BYTES:
                                raise UnsafeArchiveError(
                                    f"Actual member size exceeds declaration: {info.filename!r}"
                                )
                            digest.update(chunk)
                            output.write(chunk)
            except (OSError, RuntimeError, zipfile.BadZipFile, UnsafeArchiveError):
                if created and target.exists():
                    target.unlink()
                raise
            if written != info.file_size:
                target.unlink()
                raise UnsafeArchiveError(
                    f"Extracted size differs from declaration: {info.filename!r}"
                )
            existing[info.filename] = (written, digest.hexdigest())

    verified = hash_existing_tree(destination)
    if set(verified) != expected_names:
        raise UnsafeArchiveError(
            f"Extraction is incomplete; rerun to resume safely: {destination}"
        )
    return verified, all_present


def sqlite_summary(path: Path) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type=? ORDER BY name", ("table",)
        )
        for (table_name,) in tables:
            escaped_name = table_name.replace('"', '""')
            columns = connection.execute(
                f'PRAGMA table_info("{escaped_name}")'
            )
            column_names = [row[1] for row in columns]
            row_count = connection.execute(
                f'SELECT COUNT(*) FROM "{escaped_name}"'
            ).fetchone()[0]
            summary.append(
                {"table": table_name, "columns": column_names, "rows": row_count}
            )
    finally:
        connection.close()
    return summary


def relative_workspace_path(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventory files in data/raw and safely extract APK contents."
    )
    parser.add_argument(
        "--snapshot",
        help="Process only this immediate data/raw subdirectory (default: all snapshots).",
    )
    parser.add_argument(
        "--run-id",
        help="unique output run ID; generated automatically when omitted.",
    )
    args = parser.parse_args()

    if not RAW_ROOT.is_dir():
        parser.error(f"Raw-data directory does not exist: {RAW_ROOT}")
    run_id = args.run_id or (
        f"inventory_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_"
        f"{uuid.uuid4().hex[:8]}"
    )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", run_id):
        parser.error("--run-id contains unsupported characters")

    raw_files = [
        path
        for path in RAW_ROOT.rglob("*")
        if path.is_file() and not path.is_symlink() and path.name != ".gitkeep"
    ]
    if args.snapshot:
        snapshot_root = (RAW_ROOT / args.snapshot).resolve()
        try:
            snapshot_root.relative_to(RAW_ROOT.resolve())
        except ValueError:
            parser.error("--snapshot must name a directory under data/raw")
        raw_files = [
            path
            for path in raw_files
            if path.resolve().is_relative_to(snapshot_root)
        ]
    raw_files.sort()
    if not raw_files:
        parser.error("No regular files found in the selected data/raw scope.")

    snapshots = sorted({path.relative_to(RAW_ROOT).parts[0] for path in raw_files})
    plans: list[dict[str, Any]] = []
    raw_records: list[dict[str, Any]] = []
    for path in raw_files:
        file_format, header_hex = detect_format(path)
        record: dict[str, Any] = {
            "path": relative_workspace_path(path),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "format": file_format,
            "headerHex": header_hex,
        }
        raw_records.append(record)
        if path.suffix.lower() == ".apk" and is_zip_file(path):
            infos, expanded_bytes = inspect_archive(path)
            plans.append(
                {
                    "path": path,
                    "snapshot": path.relative_to(RAW_ROOT).parts[0],
                    "infos": infos,
                    "expanded_bytes": expanded_bytes,
                }
            )

    total_files = sum(len(plan["infos"]) for plan in plans)
    total_expanded_bytes = sum(plan["expanded_bytes"] for plan in plans)
    if total_files > MAX_FILES:
        raise UnsafeArchiveError(
            f"APK set exceeds total file-count limit ({MAX_FILES}); nothing extracted."
        )
    if total_expanded_bytes > MAX_TOTAL_UNCOMPRESSED_BYTES:
        raise UnsafeArchiveError(
            "APK set exceeds total expanded-size limit "
            f"({MAX_TOTAL_UNCOMPRESSED_BYTES} bytes); nothing extracted."
        )

    extracted_records: list[dict[str, Any]] = []
    archive_records: list[dict[str, Any]] = []
    for plan in plans:
        archive_path: Path = plan["path"]
        snapshot = str(plan["snapshot"])
        destination = (
            EXTRACTED_ROOT
            / snapshot
            / "apk_contents"
            / archive_path.stem
        )
        extracted, already_present = extract_archive(
            archive_path, plan["infos"], destination
        )
        archive_records.append(
            {
                "path": relative_workspace_path(archive_path),
                "entryCount": len(plan["infos"]),
                "uncompressedBytes": plan["expanded_bytes"],
                "extractionDirectory": relative_workspace_path(destination),
                "status": "verified-existing" if already_present else "extracted",
            }
        )
        with zipfile.ZipFile(archive_path) as archive:
            for info in plan["infos"]:
                output_path = destination.joinpath(*PurePosixPath(info.filename).parts)
                file_format, header_hex = detect_format(output_path)
                record = {
                    "path": relative_workspace_path(output_path),
                    "bytes": info.file_size,
                    "sha256": extracted[info.filename][1],
                    "format": file_format,
                    "headerHex": header_hex,
                    "source": (
                        f"{relative_workspace_path(archive_path)}!/{info.filename}"
                    ),
                }
                if (
                    file_format == "SQLite"
                    and info.filename.startswith("assets/res/")
                ):
                    try:
                        record["sqlite"] = sqlite_summary(output_path)
                    except (OSError, sqlite3.Error, ValueError) as exc:
                        record["sqliteError"] = str(exc)
                extracted_records.append(record)

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for snapshot in snapshots:
        snapshot_raw_records = [
            record
            for record in raw_records
            if f"data/raw/{snapshot}/" in record["path"]
        ]
        snapshot_extracted_records = [
            record
            for record in extracted_records
            if f"data/extracted/{snapshot}/" in record["path"]
        ]
        snapshot_records = snapshot_raw_records + snapshot_extracted_records
        format_counts = Counter(record["format"] for record in snapshot_records)
        output_dir = INVENTORY_ROOT / snapshot / "runs" / run_id
        try:
            output_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            raise UnsafeArchiveError(
                f"Inventory run already exists; refusing to overwrite: {output_dir}"
            ) from None
        report = {
            "schemaVersion": 1,
            "runId": run_id,
            "generatedAt": generated_at,
            "snapshotId": snapshot,
            "limits": {
                "maxFilesAcrossApks": MAX_FILES,
                "maxTotalUncompressedBytes": MAX_TOTAL_UNCOMPRESSED_BYTES,
                "maxSingleFileBytes": MAX_SINGLE_FILE_BYTES,
            },
            "archives": [
                record
                for record in archive_records
                if f"data/raw/{snapshot}/" in record["path"]
            ],
            "formatCounts": dict(sorted(format_counts.items())),
            "files": snapshot_records,
        }
        output_path = output_dir / "inventory.json"
        temporary_path = output_dir / f".inventory-{uuid.uuid4().hex}.tmp"
        try:
            temporary_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(output_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        print(
            f"{snapshot}: {len(report['files'])} file records; "
            f"{len(report['archives'])} APK archive(s); run={run_id}; "
            f"report={relative_workspace_path(output_path)}"
        )
    print(
        f"Limits: files={MAX_FILES}, expanded_bytes={MAX_TOTAL_UNCOMPRESSED_BYTES}, "
        f"single_file_bytes={MAX_SINGLE_FILE_BYTES}"
    )
    print("Formats: " + json.dumps(dict(sorted(format_counts.items())), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, zipfile.BadZipFile, UnsafeArchiveError) as exc:
        print(f"inventory failed safely: {exc}", file=sys.stderr)
        raise SystemExit(2)
