"""Validate normalized data against its source SQLite rows without network access."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from import_supabase import load_and_validate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="report a partial legacy/sample file without making it publishable",
    )
    args = parser.parse_args(argv)
    input_path = args.input if args.input.is_absolute() else ROOT / args.input

    bundle, errors = load_and_validate(input_path)
    if errors:
        print(f"Validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 2
    if bundle is None:
        print("Validation failed: no usable dataset.", file=sys.stderr)
        return 2
    if not bundle.source_complete:
        print(
            "Source-row checks passed, but coverage is partial or unconfirmed; "
            "this dataset cannot be published."
        )
        if not args.allow_partial:
            return 1
    else:
        print("Source coverage is complete for the declared table and language.")
    print(
        f"Validated {len(bundle.records)} rows from "
        f"{bundle.document['source']['table']} ({bundle.document['language']}); "
        f"snapshot={bundle.snapshot_id}."
    )
    print("No game-item IDs, values, units, or image mappings were inferred.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
