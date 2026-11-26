"""Validate, stage, and optionally publish a provenance-backed research bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from import_supabase import (  # noqa: E402
    ImportInputError,
    SupabaseApiError,
    SupabaseRest,
    rpc,
    service_client,
)


MODULES = {"characters", "equipment", "abilities", "pvp", "guild"}
SOURCE_KINDS = {"static", "dynamic"}
VALIDATION_STATUSES = {
    "source-row-verified",
    "source-record-verified",
    "schema-validated",
    "unverified",
}
SENSITIVE_KEY_PARTS = {
    "password",
    "passwd",
    "token",
    "cookie",
    "authorization",
    "secret",
    "credential",
}
SHA256_RE = re.compile(r"[a-fA-F0-9]{64}\Z")


class BundleValidationError(Exception):
    pass


@dataclass(frozen=True)
class ResearchBundle:
    document: dict[str, Any]
    snapshot_manifest: dict[str, Any]
    rows: list[dict[str, Any]]
    content_sha256: str
    source_complete: bool

    @property
    def snapshot_id(self) -> str:
        return self.document["snapshotId"]

    @property
    def module(self) -> str:
        return self.document["module"]


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_sensitive_keys(value: Any, path: str = "bundle") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z]", "", str(key).lower())
            if any(part in normalized for part in SENSITIVE_KEY_PARTS):
                raise BundleValidationError(
                    f"{path} contains a prohibited sensitive field name: {key}"
                )
            reject_sensitive_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_sensitive_keys(child, f"{path}[{index}]")


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BundleValidationError(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise BundleValidationError(f"{label} root must be a JSON object")
    return value


def resolve_source_file(snapshot_id: str, source_file: str) -> Path:
    normalized = source_file.replace("\\", "/")
    relative = PurePosixPath(normalized)
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise BundleValidationError("sourceFile must be a safe workspace-relative path")
    candidate = (ROOT / Path(*relative.parts)).resolve()
    allowed_roots = (
        (ROOT / "data" / "raw" / snapshot_id).resolve(),
        (ROOT / "data" / "extracted" / snapshot_id).resolve(),
    )
    if not any(candidate == root or root in candidate.parents for root in allowed_roots):
        raise BundleValidationError(
            "sourceFile must stay within the matching raw or extracted snapshot"
        )
    return candidate


def expected_counts(module: str, research_record_count: int) -> dict[str, int]:
    common = {"research_records": research_record_count}
    if module == "characters":
        return {**common, "characters": 0}
    if module == "equipment":
        return {**common, "equipment": 0}
    if module == "abilities":
        return {**common, "abilities": 0}
    if module == "pvp":
        return {
            **common,
            "pvp_rankings": 0,
            "team_snapshots": 0,
            "team_members": 0,
            "usage_stats": 0,
        }
    return {
        **common,
        "guilds": 0,
        "guild_roster_snapshots": 0,
        "guild_memberships": 0,
        "team_snapshots": 0,
        "team_members": 0,
        "usage_stats": 0,
    }


def load_bundle(input_path: Path) -> ResearchBundle:
    path = input_path if input_path.is_absolute() else ROOT / input_path
    document = load_json(path, "research bundle")
    reject_sensitive_keys(document)
    if document.get("schemaVersion") != 1:
        raise BundleValidationError("schemaVersion must be 1")
    if document.get("bundleKind") != "ranger-research-bundle":
        raise BundleValidationError("bundleKind must be ranger-research-bundle")

    snapshot_id = document.get("snapshotId")
    if (
        not isinstance(snapshot_id, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", snapshot_id)
    ):
        raise BundleValidationError("snapshotId is missing or invalid")
    module = document.get("module")
    if module not in MODULES:
        raise BundleValidationError("module must be characters, equipment, abilities, pvp, or guild")
    if document.get("sourceKind") not in SOURCE_KINDS:
        raise BundleValidationError("sourceKind must be static or dynamic")
    captured_at = document.get("capturedAt")
    if not isinstance(captured_at, str):
        raise BundleValidationError("capturedAt must be an ISO-8601 timestamp")
    try:
        parsed_timestamp = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise BundleValidationError("capturedAt must be an ISO-8601 timestamp") from error
    if parsed_timestamp.tzinfo is None:
        raise BundleValidationError("capturedAt must include a timezone")
    manifest_sha = document.get("sourceManifestSha256")
    if not isinstance(manifest_sha, str) or not SHA256_RE.fullmatch(manifest_sha):
        raise BundleValidationError("sourceManifestSha256 must be a SHA-256 digest")
    coverage = document.get("coverage")
    if not isinstance(coverage, dict):
        raise BundleValidationError("coverage metadata is missing")
    complete_flag = coverage.get("complete")
    if not isinstance(complete_flag, bool):
        raise BundleValidationError("coverage.complete must be a boolean")
    scope = coverage.get("scope")
    if not isinstance(scope, str) or not scope:
        raise BundleValidationError("coverage.scope must not be empty")

    records = document.get("records")
    if not isinstance(records, list):
        raise BundleValidationError("records must be an array")
    if document.get("recordCount") != len(records):
        raise BundleValidationError("recordCount does not match records")
    source_record_count = coverage.get("sourceRecordCount")
    parsed_record_count = coverage.get("parsedRecordCount")
    for label, count in (
        ("coverage.sourceRecordCount", source_record_count),
        ("coverage.parsedRecordCount", parsed_record_count),
    ):
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise BundleValidationError(f"{label} must be a non-negative integer")
    if parsed_record_count != len(records):
        raise BundleValidationError("coverage.parsedRecordCount does not match records")
    if complete_flag and source_record_count != len(records):
        raise BundleValidationError(
            "complete coverage must have matching source and parsed record counts"
        )

    raw_manifest_path = ROOT / "data" / "raw" / snapshot_id / "manifest.json"
    snapshot_manifest = load_json(raw_manifest_path, "raw snapshot manifest")
    if snapshot_manifest.get("snapshotId") != snapshot_id:
        raise BundleValidationError("raw manifest snapshotId does not match bundle")
    actual_manifest_sha = sha256_file(raw_manifest_path)
    if actual_manifest_sha.lower() != manifest_sha.lower():
        raise BundleValidationError("source manifest SHA-256 does not match the bundle")
    manifest_files = snapshot_manifest.get("files")
    if not isinstance(manifest_files, list):
        raise BundleValidationError("raw snapshot manifest has no files array")
    manifest_hashes = {
        str(item.get("path", "")).replace("\\", "/"): str(
            item.get("sha256", "")
        ).lower()
        for item in manifest_files
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }

    normalized_records: list[dict[str, Any]] = []
    seen_identities: set[bytes] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise BundleValidationError(f"records[{index}] must be an object")
        identity = record.get("sourceRecordIdentity")
        if identity is None or isinstance(identity, bool):
            raise BundleValidationError(
                f"records[{index}].sourceRecordIdentity is missing or invalid"
            )
        identity_bytes = canonical_json(identity)
        if identity_bytes in seen_identities:
            raise BundleValidationError(
                f"records[{index}] duplicates a source identity in this snapshot"
            )
        seen_identities.add(identity_bytes)

        source_file = record.get("sourceFile")
        source_sha = record.get("sourceFileSha256")
        if not isinstance(source_file, str) or not source_file:
            raise BundleValidationError(f"records[{index}].sourceFile is missing")
        if not isinstance(source_sha, str) or not SHA256_RE.fullmatch(source_sha):
            raise BundleValidationError(
                f"records[{index}].sourceFileSha256 is invalid"
            )
        source_path = resolve_source_file(snapshot_id, source_file)
        if not source_path.is_file():
            raise BundleValidationError(
                f"records[{index}] source file is missing: {source_file}"
            )
        actual_source_sha = sha256_file(source_path)
        if actual_source_sha.lower() != source_sha.lower():
            raise BundleValidationError(
                f"records[{index}] source file SHA-256 does not match"
            )
        if manifest_hashes.get(source_file.replace("\\", "/")) != source_sha.lower():
            raise BundleValidationError(
                f"records[{index}] source file is not SHA-256 verified by the manifest"
            )

        raw_record = record.get("rawRecord")
        normalized_record = record.get("normalizedRecord")
        if not isinstance(raw_record, dict):
            raise BundleValidationError(f"records[{index}].rawRecord must be an object")
        if normalized_record is not None and not isinstance(normalized_record, dict):
            raise BundleValidationError(
                f"records[{index}].normalizedRecord must be an object or null"
            )
        validation_status = record.get("validationStatus")
        if validation_status not in VALIDATION_STATUSES:
            raise BundleValidationError(
                f"records[{index}].validationStatus is not supported"
            )
        warnings = record.get("parseWarnings", [])
        if not isinstance(warnings, list) or any(
            not isinstance(warning, str) for warning in warnings
        ):
            raise BundleValidationError(
                f"records[{index}].parseWarnings must be an array of strings"
            )
        locator = record.get("sourceRecordLocator")
        if locator is not None and not isinstance(locator, str):
            raise BundleValidationError(
                f"records[{index}].sourceRecordLocator must be a string or null"
            )
        row_content = {
            "snapshot_id": snapshot_id,
            "module": module,
            "source_record_identity": identity,
            "source_file": source_file.replace("\\", "/"),
            "source_file_sha256": source_sha.lower(),
            "source_record_locator": locator,
            "raw_record": raw_record,
            "normalized_record": normalized_record,
            "validation_status": validation_status,
            "parse_warnings": warnings,
        }
        row_content["record_sha256"] = hashlib.sha256(
            canonical_json(row_content)
        ).hexdigest()
        normalized_records.append(row_content)

    normalized_records.sort(
        key=lambda row: canonical_json(row["source_record_identity"])
    )
    raw_manifest_complete = snapshot_manifest.get("complete") is not False
    records_verified = all(
        row["validation_status"]
        in {"source-row-verified", "source-record-verified"}
        for row in normalized_records
    )
    source_complete = (
        complete_flag is True
        and source_record_count == len(records)
        and raw_manifest_complete
        and snapshot_manifest.get("snapshotStatus") != "partial"
        and records_verified
    )
    content_sha = hashlib.sha256(
        canonical_json(
            {
                "module": module,
                "sourceKind": document["sourceKind"],
                "sourceVersion": document.get("sourceVersion"),
                "capturedAt": captured_at,
                "sourceManifestSha256": manifest_sha.lower(),
                "coverage": coverage,
                "records": [
                    {
                        "identity": row["source_record_identity"],
                        "record_sha256": row["record_sha256"],
                    }
                    for row in normalized_records
                ],
            }
        )
    ).hexdigest()
    return ResearchBundle(
        document=document,
        snapshot_manifest=snapshot_manifest,
        rows=normalized_records,
        content_sha256=content_sha,
        source_complete=source_complete,
    )


def snapshot_row(bundle: ResearchBundle) -> dict[str, Any]:
    document = bundle.document
    return {
        "snapshot_id": bundle.snapshot_id,
        "module": bundle.module,
        "source_kind": document["sourceKind"],
        "source_version": document.get("sourceVersion"),
        "captured_at": document["capturedAt"],
        "source_manifest_sha256": document["sourceManifestSha256"].lower(),
        "content_sha256": bundle.content_sha256,
        "record_count": len(bundle.rows),
        "source_metadata": {
            "coverageScope": document["coverage"]["scope"],
            "snapshotStatus": bundle.snapshot_manifest.get(
                "snapshotStatus", "legacy-unspecified"
            ),
        },
        "expected_counts": expected_counts(bundle.module, len(bundle.rows)),
        "is_complete": bundle.source_complete,
        "status": "draft",
    }


def verify_remote_bundle(
    client: SupabaseRest,
    bundle: ResearchBundle,
) -> str:
    version_rows = client.request(
        "GET",
        "/rest/v1/ranger_research_snapshots",
        params={
            "select": (
                "snapshot_id,module,source_manifest_sha256,content_sha256,"
                "record_count,status,is_complete,source_kind,source_version,"
                "captured_at,expected_counts"
            ),
            "snapshot_id": f"eq.{bundle.snapshot_id}",
            "module": f"eq.{bundle.module}",
        },
    )
    if not isinstance(version_rows, list) or len(version_rows) != 1:
        raise SupabaseApiError(0, "research snapshot is missing or ambiguous")
    version = version_rows[0]
    expected = snapshot_row(bundle)
    for field in (
        "snapshot_id",
        "module",
        "source_manifest_sha256",
        "content_sha256",
        "record_count",
        "is_complete",
        "source_kind",
        "source_version",
        "captured_at",
        "expected_counts",
    ):
        if version.get(field) != expected[field]:
            raise SupabaseApiError(0, f"remote research snapshot differs at {field}")
    status = version.get("status")
    if status not in ("draft", "published"):
        raise SupabaseApiError(0, "research snapshot has an invalid status")

    remote_records: dict[bytes, str] = {}
    offset = 0
    while True:
        page = client.request(
            "GET",
            "/rest/v1/ranger_research_records",
            params={
                "select": "source_record_identity,record_sha256",
                "snapshot_id": f"eq.{bundle.snapshot_id}",
                "module": f"eq.{bundle.module}",
                "limit": "1000",
                "offset": str(offset),
            },
        )
        if not isinstance(page, list):
            raise SupabaseApiError(0, "research row verification response is not an array")
        for row in page:
            identity = row.get("source_record_identity")
            digest = row.get("record_sha256")
            if not isinstance(digest, str):
                raise SupabaseApiError(0, "research row is missing its record digest")
            key = canonical_json(identity)
            if key in remote_records:
                raise SupabaseApiError(0, "duplicate remote research source identity")
            remote_records[key] = digest
        if len(page) < 1000:
            break
        offset += len(page)

    expected_records = {
        canonical_json(row["source_record_identity"]): row["record_sha256"]
        for row in bundle.rows
    }
    if remote_records != expected_records:
        raise SupabaseApiError(0, "remote research identities or record digests differ")
    return status


def stage_bundle(bundle: ResearchBundle) -> None:
    client = service_client()
    proposed = snapshot_row(bundle)
    existing = client.request(
        "GET",
        "/rest/v1/ranger_research_snapshots",
        params={
            "select": (
                "snapshot_id,module,source_manifest_sha256,content_sha256,"
                "record_count,status,is_complete,source_kind,source_version,"
                "captured_at,expected_counts"
            ),
            "snapshot_id": f"eq.{bundle.snapshot_id}",
            "module": f"eq.{bundle.module}",
        },
    )
    if not isinstance(existing, list):
        raise SupabaseApiError(0, "snapshot lookup response is not an array")
    if existing:
        version = existing[0]
        for field in (
            "source_manifest_sha256",
            "content_sha256",
            "record_count",
            "is_complete",
        ):
            if version.get(field) != proposed[field]:
                raise SupabaseApiError(
                    0, f"snapshot ID already exists with different {field}"
                )
        snapshot_status = version.get("status")
        if snapshot_status not in ("draft", "published"):
            raise SupabaseApiError(0, "snapshot is not eligible for idempotent import")
    else:
        client.request(
            "POST",
            "/rest/v1/ranger_research_snapshots",
            payload=proposed,
            prefer="return=minimal",
        )
        snapshot_status = "draft"

    if snapshot_status == "published":
        verify_remote_bundle(client, bundle)
        print(f"Research bundle is already published and verified: {bundle.snapshot_id}.")
        return
    if bundle.rows:
        for offset in range(0, len(bundle.rows), 250):
            client.request(
                "POST",
                "/rest/v1/ranger_research_records",
                params={
                    "on_conflict": (
                        "snapshot_id,module,source_record_identity"
                    )
                },
                payload=bundle.rows[offset : offset + 250],
                prefer="resolution=merge-duplicates,return=minimal",
            )
    status = verify_remote_bundle(client, bundle)
    if status != "draft":
        raise SupabaseApiError(0, "research bundle changed status during import")
    print(
        f"Research bundle staged and verified: module={bundle.module}, "
        f"records={len(bundle.rows)}, status=draft."
    )
    print("No public read access was granted; publication remains separate.")


def publish_bundle(bundle: ResearchBundle) -> None:
    if not bundle.source_complete:
        raise BundleValidationError(
            "source coverage is incomplete or unconfirmed; refusing to publish"
        )
    client = service_client()
    status = verify_remote_bundle(client, bundle)
    if status == "published":
        print(f"Research bundle is already published: {bundle.snapshot_id}.")
        return
    result = rpc(
        client,
        "ranger_publish_research_snapshot",
        {"p_snapshot_id": bundle.snapshot_id, "p_module": bundle.module},
    )
    if result != "published":
        raise SupabaseApiError(0, "research publish function did not confirm publication")
    status = verify_remote_bundle(client, bundle)
    if status != "published":
        raise SupabaseApiError(0, "published research status could not be verified")
    print(f"Research snapshot published: module={bundle.module}, id={bundle.snapshot_id}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="make the requested stage or publish operation against Supabase",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="verify and publish a staged research snapshot (separate from staging)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="validate locally without proposing a database operation",
    )
    args = parser.parse_args(argv)
    if args.validate_only and (args.apply or args.publish):
        parser.error("--validate-only cannot be combined with --apply or --publish")
    try:
        bundle = load_bundle(args.input)
    except (BundleValidationError, OSError) as error:
        print(f"Research bundle validation failed: {error}", file=sys.stderr)
        return 2

    print(
        f"Bundle: module={bundle.module}, snapshot={bundle.snapshot_id}, "
        f"records={len(bundle.rows)}, coverage="
        f"{'complete' if bundle.source_complete else 'partial-or-unconfirmed'}."
    )
    if args.validate_only:
        print("Mode: VALIDATION ONLY (no network requests; no database changes)")
        print(f"Content SHA-256: {bundle.content_sha256}")
        return 0
    if not args.apply:
        if args.publish:
            print("Mode: PUBLISH DRY RUN (no network requests; no database changes)")
            if not bundle.source_complete:
                print("Publication is blocked by incomplete or unconfirmed coverage.")
            else:
                print("Would verify staged rows and call the restricted publish function.")
        else:
            print("Mode: DRY RUN (no network requests; no database changes)")
            print("Would upsert immutable source identities as a private draft.")
        return 0

    try:
        if args.publish:
            publish_bundle(bundle)
        else:
            stage_bundle(bundle)
    except (BundleValidationError, ImportInputError, SupabaseApiError) as error:
        action = "Publication" if args.publish else "Import"
        print(
            f"{action} failed; the prior published snapshot is unchanged: {error}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
