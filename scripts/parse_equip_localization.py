"""Export verified equipment-domain localization rows from the game snapshot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
TABLE = "lang_equip"
SOURCE_SUFFIX = Path("assets/res/tutorial_res/db/lang_equip/lang_equip.ndb")
REQUIRED_COLUMNS = {"dataCode", "language", "msgType", "msg"}
PRIMARY_KEY = ("dataCode", "language")
WARNING = (
    "此為 lang_equip 翻譯記錄，不是裝備主檔；未提供裝備 ID、裝備名稱、"
    "星數、數值或圖片對應。"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_row(
    row: dict[str, Any],
    *,
    snapshot_id: str,
    extracted_path: str,
    apk_member: str,
    source_sha256: str,
) -> dict[str, Any]:
    data_code = row.get("dataCode")
    language = row.get("language")
    if not isinstance(data_code, str) or not data_code:
        raise ValueError("lang_equip row has a missing or invalid dataCode")
    if not isinstance(language, str) or not language:
        raise ValueError("lang_equip row has a missing or invalid language")

    msg_type = row.get("msgType")
    message = row.get("msg")
    if msg_type is not None and not isinstance(msg_type, str):
        raise ValueError("lang_equip row has an unexpected msgType type")
    if message is not None and not isinstance(message, str):
        raise ValueError("lang_equip row has an unexpected msg type")

    return {
        "gameId": None,
        "name": None,
        "language": language,
        "confirmedCategory": None,
        "starCount": None,
        "rawNumericValues": None,
        "rawEffectParameters": None,
        "confirmedDisplayValues": None,
        "imageMapping": None,
        "sourceText": {
            "dataCode": data_code,
            "msgType": msg_type,
            "text": message,
        },
        "snapshotId": snapshot_id,
        "sourceFile": extracted_path,
        "sourceArchiveMember": apk_member,
        "sourceFileSha256": source_sha256,
        "sourceRecordIdentity": {
            "dataCode": data_code,
            "language": language,
        },
        "validationStatus": "source-row-verified",
        "parseWarnings": [WARNING],
    }


def ensure_unique_record_ids(records: Iterable[dict[str, Any]]) -> None:
    seen: set[tuple[str, str]] = set()
    for record in records:
        identity = record["sourceRecordIdentity"]
        key = (identity["dataCode"], identity["language"])
        if key in seen:
            raise ValueError(f"duplicate lang_equip source record identity: {key!r}")
        seen.add(key)


def read_source(
    snapshot_id: str, language: str, limit: int | None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", snapshot_id):
        raise ValueError("snapshot ID contains unsupported characters")
    if not language:
        raise ValueError("language must not be empty")
    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than zero")

    manifest_path = ROOT / "data" / "raw" / snapshot_id / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"snapshot manifest not found: {manifest_path}")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    if manifest.get("snapshotId") != snapshot_id:
        raise ValueError("snapshot ID does not match manifest")

    extracted_path = Path("data") / "extracted" / snapshot_id / SOURCE_SUFFIX
    expected_manifest_path = extracted_path.as_posix()
    source_entry = next(
        (
            entry
            for entry in manifest.get("files", [])
            if entry.get("path") == expected_manifest_path
        ),
        None,
    )
    if source_entry is None:
        raise ValueError("lang_equip source is not recorded in the snapshot manifest")

    source_path = ROOT / extracted_path
    if not source_path.is_file():
        raise FileNotFoundError(f"extracted lang_equip database not found: {source_path}")
    actual_size = source_path.stat().st_size
    actual_sha256 = sha256_file(source_path)
    if actual_size != source_entry.get("bytes"):
        raise ValueError("lang_equip source size does not match the manifest")
    if actual_sha256.lower() != str(source_entry.get("sha256", "")).lower():
        raise ValueError("lang_equip source SHA-256 does not match the manifest")

    connection = sqlite3.connect(source_path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(f"lang_equip SQLite integrity check failed: {integrity}")

        table_info = connection.execute(f"PRAGMA table_info({TABLE})").fetchall()
        columns = {column["name"] for column in table_info}
        if not REQUIRED_COLUMNS.issubset(columns):
            raise ValueError(f"unexpected {TABLE} columns: {sorted(columns)!r}")
        primary_key = tuple(
            column["name"]
            for column in sorted(table_info, key=lambda item: item["pk"])
            if column["pk"]
        )
        if primary_key != PRIMARY_KEY:
            raise ValueError(f"unexpected {TABLE} primary key: {primary_key!r}")

        duplicate = connection.execute(
            f"""
            SELECT dataCode, language
            FROM {TABLE}
            WHERE language = ?
            GROUP BY dataCode, language
            HAVING COUNT(*) > 1
            LIMIT 1
            """,
            (language,),
        ).fetchone()
        if duplicate is not None:
            raise ValueError(
                "duplicate lang_equip source record identity: "
                f"{(duplicate['dataCode'], duplicate['language'])!r}"
            )

        language_row_count = connection.execute(
            f"SELECT COUNT(*) FROM {TABLE} WHERE language = ?",
            (language,),
        ).fetchone()[0]
        query = f"""
            SELECT dataCode, language, msgType, msg
            FROM {TABLE}
            WHERE language = ?
            ORDER BY dataCode
        """
        parameters: tuple[Any, ...] = (language,)
        if limit is not None:
            query += " LIMIT ?"
            parameters = (language, limit)
        source_rows = connection.execute(query, parameters).fetchall()
        if limit is not None and len(source_rows) < limit:
            raise ValueError(
                f"requested {limit} rows for {language}, found only {len(source_rows)}"
            )

        archive_member = source_entry.get("source")
        if not isinstance(archive_member, str) or not archive_member:
            raise ValueError("manifest source archive member is missing")

        records = [
            normalize_row(
                dict(row),
                snapshot_id=snapshot_id,
                extracted_path=expected_manifest_path,
                apk_member=archive_member,
                source_sha256=actual_sha256,
            )
            for row in source_rows
        ]
        ensure_unique_record_ids(records)
        metadata = {
            "path": expected_manifest_path,
            "archiveMember": archive_member,
            "bytes": actual_size,
            "sha256": actual_sha256,
            "table": TABLE,
            "columns": [column["name"] for column in table_info],
            "primaryKey": list(primary_key),
            "integrityCheck": integrity,
            "languageRowCount": language_row_count,
            "parsedRows": len(records),
            "complete": len(source_rows) == language_row_count,
            "sourceManifestSha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "snapshotStatus": manifest.get("snapshotStatus", "legacy-unspecified"),
        }
        return records, metadata
    finally:
        connection.close()


def write_outputs(
    snapshot_id: str,
    run_id: str,
    language: str,
    records: list[dict[str, Any]],
    source: dict[str, Any],
) -> tuple[Path, Path, Path]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", run_id):
        raise ValueError("run ID contains unsupported characters")

    output_dir = ROOT / "data" / "normalized" / snapshot_id / "runs" / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    json_path = output_dir / "equip_localization.json"
    review_path = output_dir / "equip_localization_review.csv"
    run_manifest_path = output_dir / "run-manifest.json"
    generated_at = datetime.now(timezone.utc).isoformat()
    source_complete = source["complete"] is True

    document = {
        "schemaVersion": 1,
        "datasetKind": "equipment-domain-localization-not-equipment-items",
        "snapshotId": snapshot_id,
        "runId": run_id,
        "language": language,
        "generatedAt": generated_at,
        "source": source,
        "coverage": {
            "scope": f"{TABLE}:{language}",
            "complete": source_complete,
            "sourceRowCount": source["languageRowCount"],
            "parsedRowCount": len(records),
            "snapshotStatus": source["snapshotStatus"],
        },
        "recordCount": len(records),
        "records": records,
        "notes": [
            "These rows are actual lang_equip localization records, not equipment item records.",
            "No equipment IDs, item names, grades, numeric stats, effect parameters, "
            "image mappings, or numeric conversions were inferred.",
        ],
    }
    json_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    fieldnames = [
        "snapshot_id",
        "source_data_code",
        "language",
        "source_msg_type",
        "source_text",
        "game_id",
        "item_name",
        "stars",
        "raw_values",
        "raw_effect_parameters",
        "display_values",
        "image_mapping",
        "validation_status",
        "parse_warnings",
    ]
    with review_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            source_text = record["sourceText"]
            writer.writerow(
                {
                    "snapshot_id": record["snapshotId"],
                    "source_data_code": source_text["dataCode"],
                    "language": record["language"],
                    "source_msg_type": source_text["msgType"],
                    "source_text": source_text["text"],
                    "game_id": "unknown",
                    "item_name": "unknown",
                    "stars": "unknown",
                    "raw_values": "unknown",
                    "raw_effect_parameters": "unknown",
                    "display_values": "unknown",
                    "image_mapping": "unknown",
                    "validation_status": record["validationStatus"],
                    "parse_warnings": " | ".join(record["parseWarnings"]),
                }
            )
    output_files = []
    for path in (json_path, review_path):
        output_files.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    run_manifest = {
        "schemaVersion": 1,
        "runId": run_id,
        "snapshotId": snapshot_id,
        "datasetKind": document["datasetKind"],
        "generatedAt": generated_at,
        "status": "complete" if source_complete else "partial",
        "sourceManifestSha256": source["sourceManifestSha256"],
        "source": source,
        "coverage": document["coverage"],
        "recordCount": len(records),
        "files": output_files,
    }
    run_manifest_path.write_text(
        json.dumps(run_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return json_path, review_path, run_manifest_path


def new_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"equip_{timestamp}_{uuid.uuid4().hex[:8]}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export real lang_equip localization rows. This does not decode "
            "the equipment-item database."
        )
    )
    parser.add_argument("--snapshot", required=True, help="snapshot ID to read")
    parser.add_argument("--language", default="zh-Hant", help="source language")
    parser.add_argument(
        "--limit",
        type=int,
        help="optional row limit; omit to export every row for this language",
    )
    parser.add_argument(
        "--run-id",
        help="unique output run ID; generated automatically when omitted",
    )
    args = parser.parse_args()

    try:
        records, source = read_source(args.snapshot, args.language, args.limit)
        run_id = args.run_id or new_run_id()
        json_path, review_path, run_manifest_path = write_outputs(
            args.snapshot, run_id, args.language, records, source
        )
    except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))

    print(f"Exported {len(records)} actual localization rows ({args.language}).")
    print(f"JSON: {json_path.relative_to(ROOT)}")
    print(f"Review CSV: {review_path.relative_to(ROOT)}")
    print(f"Run manifest: {run_manifest_path.relative_to(ROOT)}")
    print("Equipment item fields remain unknown; no numeric conversions were applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
