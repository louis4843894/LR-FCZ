"""Compare immutable snapshot manifests and normalized records."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
PROVENANCE_FIELDS = {
    "snapshotId",
    "sourceFile",
    "sourceArchiveMember",
    "sourceFileSha256",
    "sourceRecordIdentity",
    "validationStatus",
    "parseWarnings",
}


class DiffInputError(Exception):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DiffInputError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise DiffInputError(f"{path} root must be a JSON object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_file_path(path: str, snapshot_id: str) -> str:
    normalized = path.replace("\\", "/").lstrip("./")
    for root in ("data/raw/", "data/extracted/"):
        prefix = f"{root}{snapshot_id}/"
        if normalized.startswith(prefix):
            return f"{root}{{snapshot-id}}/{normalized[len(prefix):]}"
    return normalized


def file_entries(manifest_path: Path, snapshot_id: str) -> dict[str, dict[str, Any]]:
    manifest = read_json(manifest_path)
    if manifest.get("snapshotId") != snapshot_id:
        raise DiffInputError(f"snapshot ID in {manifest_path} does not match argument")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise DiffInputError(f"{manifest_path} has no files array")

    result: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise DiffInputError(f"{manifest_path} files[{index}] is not an object")
        path = entry.get("path")
        digest = entry.get("sha256")
        if not isinstance(path, str) or not path:
            raise DiffInputError(f"{manifest_path} files[{index}] has no path")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest):
            raise DiffInputError(f"{manifest_path} files[{index}] has invalid SHA-256")
        relative = PurePosixPath(path.replace("\\", "/"))
        if relative.is_absolute() or any(
            part in ("", ".", "..") for part in relative.parts
        ):
            raise DiffInputError(f"{manifest_path} files[{index}] has an unsafe path")
        source_path = (ROOT / Path(*relative.parts)).resolve()
        if ROOT.resolve() not in source_path.parents:
            raise DiffInputError(f"{manifest_path} files[{index}] escapes workspace")
        try:
            actual_sha = sha256_file(source_path)
        except OSError as error:
            raise DiffInputError(
                f"cannot read manifest file {path!r}: {error}"
            ) from error
        if actual_sha.lower() != digest.lower():
            raise DiffInputError(f"file SHA-256 no longer matches manifest: {path}")
        expected_bytes = entry.get("bytes")
        if (
            isinstance(expected_bytes, int)
            and not isinstance(expected_bytes, bool)
            and source_path.stat().st_size != expected_bytes
        ):
            raise DiffInputError(f"file size no longer matches manifest: {path}")
        key = canonical_file_path(path, snapshot_id)
        if key in result:
            raise DiffInputError(f"duplicate canonical file path: {key}")
        result[key] = {"path": path, "sha256": digest.lower(), "bytes": entry.get("bytes")}
    return result


def compare_files(
    old_files: dict[str, dict[str, Any]],
    new_files: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    added: list[dict[str, Any]] = []
    modified: list[dict[str, Any]] = []
    unchanged: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for key in sorted(old_files.keys() | new_files.keys()):
        old = old_files.get(key)
        new = new_files.get(key)
        if old is None:
            added.append({"key": key, "new": new})
        elif new is None:
            missing.append(
                {
                    "key": key,
                    "old": old,
                    "classification": "missing-from-new-acquisition-not-official-deletion",
                }
            )
        elif old["sha256"] == new["sha256"]:
            unchanged.append({"key": key, "old": old, "new": new})
        else:
            modified.append({"key": key, "old": old, "new": new})
    return {
        "added": added,
        "modified": modified,
        "unchanged": unchanged,
        "missingFromNew": missing,
        "counts": {
            "added": len(added),
            "modified": len(modified),
            "unchanged": len(unchanged),
            "missingFromNew": len(missing),
        },
    }


def record_key(record: dict[str, Any], index: int) -> tuple[str, str]:
    game_id = record.get("gameId")
    if isinstance(game_id, str) and game_id:
        identity = {"gameId": game_id, "language": record.get("language")}
    else:
        identity = record.get("sourceRecordIdentity")
        if not isinstance(identity, dict) or not identity:
            raise DiffInputError(f"records[{index}] has no confirmed source identity")
    return json.dumps(identity, ensure_ascii=False, sort_keys=True), json.dumps(
        identity, ensure_ascii=False, sort_keys=True
    )


def read_records(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    document = read_json(path)
    records = document.get("records")
    if not isinstance(records, list):
        raise DiffInputError(f"{path} has no records array")
    if document.get("recordCount") != len(records):
        raise DiffInputError(f"{path} recordCount does not match records length")
    keyed: dict[str, dict[str, Any]] = {}
    labels: dict[str, str] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise DiffInputError(f"{path} records[{index}] is not an object")
        key, label = record_key(record, index)
        if key in keyed:
            raise DiffInputError(f"{path} has duplicate normalized identity {label}")
        keyed[key] = record
        labels[key] = label
    document["_identityLabels"] = labels
    return keyed, document


def leaf_changes(
    old: Any,
    new: Any,
    prefix: str = "",
) -> list[dict[str, Any]]:
    if isinstance(old, dict) and isinstance(new, dict):
        changes: list[dict[str, Any]] = []
        for field in sorted(old.keys() | new.keys()):
            if not prefix and field in PROVENANCE_FIELDS:
                continue
            child_path = f"{prefix}.{field}" if prefix else field
            if field not in old:
                changes.append({"field": child_path, "old": None, "new": new[field]})
            elif field not in new:
                changes.append({"field": child_path, "old": old[field], "new": None})
            else:
                changes.extend(leaf_changes(old[field], new[field], child_path))
        return changes
    if old != new:
        return [{"field": prefix, "old": old, "new": new}]
    return []


def compare_records(
    old_records: dict[str, dict[str, Any]],
    old_document: dict[str, Any],
    new_records: dict[str, dict[str, Any]],
    new_document: dict[str, Any],
) -> dict[str, Any]:
    old_labels = old_document["_identityLabels"]
    new_labels = new_document["_identityLabels"]
    old_complete = (
        isinstance(old_document.get("coverage"), dict)
        and old_document["coverage"].get("complete") is True
    )
    new_complete = (
        isinstance(new_document.get("coverage"), dict)
        and new_document["coverage"].get("complete") is True
    )
    newly_observed = [
        {"identity": new_labels[key]}
        for key in sorted(new_records.keys() - old_records.keys())
    ]
    missing_from_new = [
        {
            "identity": old_labels[key],
            "classification": "not-observed-in-new-not-official-deletion",
        }
        for key in sorted(old_records.keys() - new_records.keys())
    ]
    changed: list[dict[str, Any]] = []
    for key in sorted(old_records.keys() & new_records.keys()):
        changes = leaf_changes(old_records[key], new_records[key])
        if changes:
            changed.append({"identity": new_labels[key], "fields": changes})
    text_changes = sum(
        "text" in change["field"].lower() or "name" in change["field"].lower()
        for record in changed
        for change in record["fields"]
    )
    numeric_changes = sum(
        isinstance(change["old"], (int, float))
        and not isinstance(change["old"], bool)
        or isinstance(change["new"], (int, float))
        and not isinstance(change["new"], bool)
        for record in changed
        for change in record["fields"]
    )
    return {
        "datasetKind": new_document.get("datasetKind"),
        "identityRule": "gameId + language when gameId is confirmed; otherwise sourceRecordIdentity",
        "oldCoverageComplete": old_complete,
        "newCoverageComplete": new_complete,
        "newlyObserved": newly_observed,
        "changed": changed,
        "missingFromNew": missing_from_new,
        "missingMeansOfficialDeletion": False,
        "textChangeCount": text_changes,
        "numericFieldChangeCount": numeric_changes,
        "counts": {
            "newlyObserved": len(newly_observed),
            "changedRecords": len(changed),
            "missingFromNew": len(missing_from_new),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    files = report["files"]
    rows = report.get("records")
    lines = [
        "# 快照差異報告",
        "",
        f"- 舊快照：`{report['oldSnapshotId']}`",
        f"- 新快照：`{report['newSnapshotId']}`",
        f"- 產生時間：`{report['generatedAt']}`",
        "",
        "## 檔案 SHA-256",
        "",
        "| 分類 | 筆數 |",
        "|---|---:|",
        f"| 新增 | {files['counts']['added']} |",
        f"| 修改 | {files['counts']['modified']} |",
        f"| 未變動 | {files['counts']['unchanged']} |",
        f"| 新快照未見 | {files['counts']['missingFromNew']} |",
        "",
        "「新快照未見」只表示本次 manifest 沒有該路徑，不代表官方刪除。",
    ]
    if rows is not None:
        lines.extend(
            [
                "",
                "## 正規化記錄差異",
                "",
                f"- 資料種類：`{rows['datasetKind']}`",
                f"- 新觀察到：{rows['counts']['newlyObserved']}",
                f"- 欄位改變記錄：{rows['counts']['changedRecords']}",
                f"- 新快照未見：{rows['counts']['missingFromNew']}",
                f"- 文字欄位改變：{rows['textChangeCount']}",
                f"- 數值欄位改變：{rows['numericFieldChangeCount']}",
                "- 缺少項目不解讀為官方刪除。",
                "",
                "欄位改變細節列於同目錄的 JSON 報告；原始值未做單位換算。",
            ]
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-snapshot", required=True)
    parser.add_argument("--new-snapshot", required=True)
    parser.add_argument("--old-records", type=Path)
    parser.add_argument("--new-records", type=Path)
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    for snapshot_id in (args.old_snapshot, args.new_snapshot):
        if not SNAPSHOT_ID_RE.fullmatch(snapshot_id):
            parser.error(f"invalid snapshot ID: {snapshot_id}")
    if (args.old_records is None) != (args.new_records is None):
        parser.error("--old-records and --new-records must be supplied together")

    run_id = args.run_id or (
        f"diff_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_"
        f"{uuid.uuid4().hex[:8]}"
    )
    if not RUN_ID_RE.fullmatch(run_id):
        parser.error("--run-id contains unsupported characters")

    try:
        old_manifest = file_entries(
            ROOT / "data" / "raw" / args.old_snapshot / "manifest.json",
            args.old_snapshot,
        )
        new_manifest = file_entries(
            ROOT / "data" / "raw" / args.new_snapshot / "manifest.json",
            args.new_snapshot,
        )
        report: dict[str, Any] = {
            "schemaVersion": 1,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "oldSnapshotId": args.old_snapshot,
            "newSnapshotId": args.new_snapshot,
            "files": compare_files(old_manifest, new_manifest),
        }
        if args.old_records is not None and args.new_records is not None:
            old_records, old_document = read_records(args.old_records)
            new_records, new_document = read_records(args.new_records)
            report["records"] = compare_records(
                old_records,
                old_document,
                new_records,
                new_document,
            )
        output_dir = ROOT / "reports" / "diffs" / run_id
        output_dir.mkdir(parents=True, exist_ok=False)
        json_path = output_dir / "diff.json"
        markdown_path = output_dir / "diff.md"
        encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        json_path.write_text(encoded, encoding="utf-8")
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
    except (DiffInputError, OSError, json.JSONDecodeError) as error:
        print(f"Diff failed: {error}")
        return 2

    print(f"JSON: {json_path.relative_to(ROOT)}")
    print(f"Markdown: {markdown_path.relative_to(ROOT)}")
    print(
        "File changes: "
        f"{report['files']['counts']['added']} added, "
        f"{report['files']['counts']['modified']} modified, "
        f"{report['files']['counts']['unchanged']} unchanged, "
        f"{report['files']['counts']['missingFromNew']} missing from new."
    )
    if "records" in report:
        counts = report["records"]["counts"]
        print(
            "Record changes: "
            f"{counts['newlyObserved']} newly observed, "
            f"{counts['changedRecords']} changed, "
            f"{counts['missingFromNew']} not observed in new."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
