"""Manual command entry point for acquiring, validating, and publishing data."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run_script(script_name: str, arguments: list[str]) -> int:
    command = [sys.executable, str(SCRIPTS / script_name), *arguments]
    try:
        return subprocess.call(command, cwd=ROOT)
    except OSError as error:
        print(f"Cannot start {script_name}: {error}", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    acquire_parser = commands.add_parser("acquire", help="pull APKs from one selected device")
    acquire_parser.add_argument("--adb", type=Path, required=True)
    acquire_parser.add_argument("--serial", required=True)
    acquire_parser.add_argument("--package", required=True)
    acquire_parser.add_argument("--snapshot-id")

    inventory_parser = commands.add_parser("inventory", help="inventory and safely extract APKs")
    inventory_parser.add_argument("--snapshot", required=True)
    inventory_parser.add_argument("--run-id")

    parse_parser = commands.add_parser("parse", help="parse every row of a confirmed source")
    parse_parser.add_argument("--snapshot", required=True)
    parse_parser.add_argument("--language", default="zh-Hant")
    parse_parser.add_argument("--limit", type=int)
    parse_parser.add_argument("--run-id")

    validate_parser = commands.add_parser("validate", help="verify normalized rows against source")
    validate_parser.add_argument("--input", type=Path, required=True)
    validate_parser.add_argument("--allow-partial", action="store_true")
    validate_parser.add_argument(
        "--research",
        action="store_true",
        help="validate the generic multi-module research bundle envelope",
    )

    diff_parser = commands.add_parser("diff", help="compare two immutable snapshots and datasets")
    diff_parser.add_argument("--old-snapshot", required=True)
    diff_parser.add_argument("--new-snapshot", required=True)
    diff_parser.add_argument("--old-records", type=Path)
    diff_parser.add_argument("--new-records", type=Path)
    diff_parser.add_argument("--run-id")

    import_parser = commands.add_parser(
        "import",
        help="dry-run by default; --apply stages and verifies an unpublished version",
    )
    import_parser.add_argument("--input", type=Path, required=True)
    import_parser.add_argument("--apply", action="store_true")
    import_parser.add_argument(
        "--research",
        action="store_true",
        help="stage a generic research bundle privately instead of lang_equip translations",
    )

    publish_parser = commands.add_parser(
        "publish",
        help="dry-run by default; requires --apply to publish a verified complete version",
    )
    publish_parser.add_argument("--input", type=Path, required=True)
    publish_parser.add_argument("--apply", action="store_true")
    publish_parser.add_argument(
        "--research",
        action="store_true",
        help="publish a verified multi-module research snapshot",
    )

    args = parser.parse_args(argv)
    if args.command == "acquire":
        child_args = [
            "--adb",
            str(args.adb),
            "--serial",
            args.serial,
            "--package",
            args.package,
        ]
        if args.snapshot_id:
            child_args.extend(["--snapshot-id", args.snapshot_id])
        return run_script("acquire_apk_snapshot.py", child_args)
    if args.command == "inventory":
        child_args = ["--snapshot", args.snapshot]
        if args.run_id:
            child_args.extend(["--run-id", args.run_id])
        return run_script("inventory_game_files.py", child_args)
    if args.command == "parse":
        child_args = ["--snapshot", args.snapshot, "--language", args.language]
        if args.limit is not None:
            child_args.extend(["--limit", str(args.limit)])
        if args.run_id:
            child_args.extend(["--run-id", args.run_id])
        return run_script("parse_equip_localization.py", child_args)
    if args.command == "validate":
        if args.research:
            return run_script(
                "import_research_bundle.py",
                ["--input", str(args.input), "--validate-only"],
            )
        child_args = ["--input", str(args.input)]
        if args.allow_partial:
            child_args.append("--allow-partial")
        return run_script("validate_data.py", child_args)
    if args.command == "diff":
        child_args = [
            "--old-snapshot",
            args.old_snapshot,
            "--new-snapshot",
            args.new_snapshot,
        ]
        if args.old_records is not None and args.new_records is not None:
            child_args.extend(["--old-records", str(args.old_records)])
            child_args.extend(["--new-records", str(args.new_records)])
        elif args.old_records is not None or args.new_records is not None:
            parser.error("--old-records and --new-records must be supplied together")
        if args.run_id:
            child_args.extend(["--run-id", args.run_id])
        return run_script("diff_data.py", child_args)
    if args.command == "import":
        if args.research:
            child_args = ["--input", str(args.input)]
            if args.apply:
                child_args.append("--apply")
            return run_script("import_research_bundle.py", child_args)
        child_args = ["--input", str(args.input)]
        if args.apply:
            child_args.append("--apply")
        return run_script("import_supabase.py", child_args)
    if args.command == "publish":
        if args.research:
            child_args = ["--input", str(args.input), "--publish"]
            if args.apply:
                child_args.append("--apply")
            return run_script("import_research_bundle.py", child_args)
        child_args = ["--input", str(args.input), "--publish"]
        if args.apply:
            child_args.append("--apply")
        return run_script("import_supabase.py", child_args)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
