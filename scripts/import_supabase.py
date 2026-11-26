"""Dry-run or explicitly apply verified normalized data to Supabase."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DATASET_KIND = "equipment-domain-localization-not-equipment-items"
EXPECTED_SOURCE_SUFFIX = (
    "assets/res/tutorial_res/db/lang_equip/lang_equip.ndb"
)
EXPECTED_COLUMNS = ["dataCode", "language", "msgType", "msg"]
PUBLIC_LOCALIZATION_COLUMNS = "snapshot_id,data_code,language,msg_type,message"
PUBLIC_VERIFICATION_PAGE_SIZE = 500
PRIVATE_LOCALIZATION_COLUMNS = (
    "source_file,source_archive_member,source_file_sha256,"
    "source_record_identity,parse_warnings,raw_record"
)
LOCALIZATION_SELECT_COLUMNS = (
    "snapshot_id,data_code,language,msg_type,message,source_file,"
    "source_archive_member,source_file_sha256,source_record_identity,"
    "validation_status,parse_warnings,raw_record"
)
UNKNOWN_ITEM_FIELDS = (
    "gameId",
    "name",
    "confirmedCategory",
    "starCount",
    "rawNumericValues",
    "rawEffectParameters",
    "confirmedDisplayValues",
    "imageMapping",
)


class ImportInputError(Exception):
    pass


class SupabaseApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass
class ValidatedInput:
    document: dict[str, Any]
    manifest: dict[str, Any]
    source_path: str
    source_archive_member: str
    source_file_sha256: str
    source_manifest_sha256: str
    package_name: str
    source_version: str
    content_sha256: str
    source_complete: bool

    @property
    def snapshot_id(self) -> str:
        return self.document["snapshotId"]

    @property
    def records(self) -> list[dict[str, Any]]:
        return self.document["records"]


def json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_and_validate(input_path: Path) -> tuple[ValidatedInput | None, list[str]]:
    errors: list[str] = []
    try:
        document = json.loads(input_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        return None, [f"cannot read normalized JSON: {error}"]

    if not isinstance(document, dict):
        return None, ["normalized JSON root must be an object"]
    snapshot_id = document.get("snapshotId")
    if not isinstance(snapshot_id, str) or not SNAPSHOT_ID_RE.fullmatch(snapshot_id):
        errors.append("snapshotId is missing or invalid")
        return None, errors
    if document.get("datasetKind") != DATASET_KIND:
        errors.append(
            "unsupported datasetKind; this importer accepts only verified "
            "lang_equip localization rows, not equipment items"
        )

    language = document.get("language")
    if not isinstance(language, str) or not language:
        errors.append("language is missing or invalid")
    records = document.get("records")
    if not isinstance(records, list) or not records:
        errors.append("records must be a non-empty array")
        records = []
    if document.get("recordCount") != len(records):
        errors.append("recordCount does not match records array length")
    coverage = document.get("coverage")
    source_complete = False
    if coverage is not None:
        if not isinstance(coverage, dict):
            errors.append("coverage metadata must be an object")
        else:
            if not isinstance(coverage.get("complete"), bool):
                errors.append("coverage.complete must be a boolean")
            if coverage.get("parsedRowCount") != len(records):
                errors.append("coverage.parsedRowCount does not match records")
            source_row_count = coverage.get("sourceRowCount")
            if (
                not isinstance(source_row_count, int)
                or isinstance(source_row_count, bool)
                or source_row_count < len(records)
            ):
                errors.append("coverage.sourceRowCount is missing or invalid")
            source_complete = (
                coverage.get("complete") is True
                and source_row_count == len(records)
            )

    source = document.get("source")
    if not isinstance(source, dict):
        errors.append("source metadata is missing")
        source = {}
    if source.get("table") != "lang_equip":
        errors.append("source table must be lang_equip")
    if source.get("columns") != EXPECTED_COLUMNS:
        errors.append(f"source columns must be {EXPECTED_COLUMNS!r}")
    if source.get("primaryKey") != ["dataCode", "language"]:
        errors.append("source primary key must be (dataCode, language)")
    if source.get("integrityCheck") != "ok":
        errors.append("source SQLite integrity check is not marked ok")

    record_keys: set[tuple[str, str]] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"records[{index}] must be an object")
            continue
        prefix = f"records[{index}]"
        if record.get("snapshotId") != snapshot_id:
            errors.append(f"{prefix}.snapshotId does not match document snapshot")
        if record.get("language") != language:
            errors.append(f"{prefix}.language does not match document language")
        if record.get("validationStatus") != "source-row-verified":
            errors.append(f"{prefix}.validationStatus is not source-row-verified")
        for field in UNKNOWN_ITEM_FIELDS:
            if record.get(field) is not None:
                errors.append(f"{prefix}.{field} must remain null for this dataset")

        source_text = record.get("sourceText")
        identity = record.get("sourceRecordIdentity")
        if not isinstance(source_text, dict) or not isinstance(identity, dict):
            errors.append(f"{prefix} is missing sourceText or sourceRecordIdentity")
            continue
        data_code = source_text.get("dataCode")
        record_language = record.get("language")
        if not isinstance(data_code, str) or not data_code:
            errors.append(f"{prefix}.sourceText.dataCode is missing or invalid")
            continue
        if identity.get("dataCode") != data_code:
            errors.append(f"{prefix} source identity dataCode does not match")
        if identity.get("language") != record_language:
            errors.append(f"{prefix} source identity language does not match")
        if source_text.get("msgType") is not None and not isinstance(
            source_text.get("msgType"), str
        ):
            errors.append(f"{prefix}.sourceText.msgType has an invalid type")
        if source_text.get("text") is not None and not isinstance(
            source_text.get("text"), str
        ):
            errors.append(f"{prefix}.sourceText.text has an invalid type")

        key = (data_code, str(record_language))
        if key in record_keys:
            errors.append(f"{prefix} duplicates source identity {key!r}")
        record_keys.add(key)

        if record.get("sourceFile") != source.get("path"):
            errors.append(f"{prefix}.sourceFile does not match source metadata")
        if record.get("sourceArchiveMember") != source.get("archiveMember"):
            errors.append(
                f"{prefix}.sourceArchiveMember does not match source metadata"
            )
        if record.get("sourceFileSha256") != source.get("sha256"):
            errors.append(f"{prefix}.sourceFileSha256 does not match source metadata")
        if not isinstance(record.get("parseWarnings"), list) or not all(
            isinstance(warning, str) for warning in record.get("parseWarnings", [])
        ):
            errors.append(f"{prefix}.parseWarnings must be an array of strings")

    source_path_value = source.get("path")
    archive_member = source.get("archiveMember")
    source_file_sha256 = source.get("sha256")
    if not isinstance(source_path_value, str) or not isinstance(
        archive_member, str
    ):
        errors.append("source path or archive member is missing")
    expected_source_path = (
        f"data/extracted/{snapshot_id}/{EXPECTED_SOURCE_SUFFIX}"
    )
    if source_path_value != expected_source_path:
        errors.append("source path is not the verified lang_equip database path")
    if not isinstance(source_file_sha256, str) or not SHA256_RE.fullmatch(
        source_file_sha256.lower()
    ):
        errors.append("source SHA-256 is missing or invalid")

    if errors:
        return None, errors

    manifest_path = ROOT / "data" / "raw" / snapshot_id / "manifest.json"
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        return None, [f"cannot read snapshot manifest: {error}"]

    if not isinstance(manifest, dict) or manifest.get("snapshotId") != snapshot_id:
        return None, ["snapshot manifest ID does not match normalized JSON"]
    matching_files = [
        item
        for item in manifest.get("files", [])
        if isinstance(item, dict) and item.get("path") == source_path_value
    ]
    if len(matching_files) != 1:
        return None, ["source file is not uniquely recorded in the manifest"]
    manifest_source = matching_files[0]
    if str(manifest_source.get("sha256", "")).lower() != source_file_sha256.lower():
        return None, ["source SHA-256 does not match the manifest"]
    if manifest_source.get("source") != archive_member:
        return None, ["source archive member does not match the manifest"]

    relative_source = PurePosixPath(source_path_value)
    if relative_source.is_absolute() or ".." in relative_source.parts:
        return None, ["source path must be a safe project-relative path"]
    local_source = (ROOT / Path(*relative_source.parts)).resolve()
    try:
        local_source.relative_to(ROOT.resolve())
    except ValueError:
        return None, ["source path escapes the workspace"]
    if not local_source.is_file():
        return None, ["manifest-recorded source file is missing locally"]
    if local_source.stat().st_size != manifest_source.get("bytes"):
        return None, ["local source file size does not match the manifest"]
    if sha256_file(local_source).lower() != source_file_sha256.lower():
        return None, ["local source file SHA-256 does not match the manifest"]

    try:
        connection = sqlite3.connect(
            local_source.as_uri() + "?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA query_only = ON")
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                return None, [f"source SQLite integrity check failed: {integrity}"]
            table_info = connection.execute("PRAGMA table_info(lang_equip)").fetchall()
            actual_columns = [column["name"] for column in table_info]
            actual_primary_key = [
                column["name"]
                for column in sorted(table_info, key=lambda item: item["pk"])
                if column["pk"]
            ]
            if actual_columns != EXPECTED_COLUMNS:
                return None, ["local source SQLite columns do not match normalized metadata"]
            if actual_primary_key != ["dataCode", "language"]:
                return None, ["local source SQLite primary key is unexpected"]

            for index, record in enumerate(records):
                source_text = record["sourceText"]
                rows = connection.execute(
                    """
                    SELECT msgType, msg
                    FROM lang_equip
                    WHERE dataCode = ? AND language = ?
                    """,
                    (
                        source_text["dataCode"],
                        record["sourceRecordIdentity"]["language"],
                    ),
                ).fetchall()
                if len(rows) != 1:
                    return None, [
                        f"records[{index}] source identity resolves to {len(rows)} "
                        "SQLite rows"
                    ]
                if (
                    rows[0]["msgType"] != source_text["msgType"]
                    or rows[0]["msg"] != source_text["text"]
                ):
                    return None, [
                        f"records[{index}] text does not match the source SQLite row"
                    ]
        finally:
            connection.close()
    except sqlite3.Error as error:
        return None, [f"cannot verify source SQLite rows: {error}"]

    package = manifest.get("package")
    if not isinstance(package, dict):
        return None, ["snapshot manifest package metadata is missing"]
    package_name = package.get("name")
    source_version = package.get("versionName")
    if not isinstance(package_name, str) or not package_name:
        return None, ["snapshot manifest package name is missing"]
    if not isinstance(source_version, str) or not source_version:
        return None, ["snapshot manifest package version is missing"]

    ordered_records = sorted(
        records,
        key=lambda item: (
            item["sourceRecordIdentity"]["dataCode"],
            item["sourceRecordIdentity"]["language"],
        ),
    )
    return (
        ValidatedInput(
            document=document,
            manifest=manifest,
            source_path=source_path_value,
            source_archive_member=archive_member,
            source_file_sha256=source_file_sha256.lower(),
            source_manifest_sha256=sha256_bytes(manifest_bytes),
            package_name=package_name,
            source_version=source_version,
            content_sha256=sha256_bytes(json_bytes(ordered_records)),
            source_complete=source_complete,
        ),
        [],
    )


def database_row(snapshot_id: str, record: dict[str, Any]) -> dict[str, Any]:
    source_text = record["sourceText"]
    return {
        "snapshot_id": snapshot_id,
        "data_code": source_text["dataCode"],
        "language": record["language"],
        "msg_type": source_text["msgType"],
        "message": source_text["text"],
        "source_file": record["sourceFile"],
        "source_archive_member": record["sourceArchiveMember"],
        "source_file_sha256": record["sourceFileSha256"].lower(),
        "source_record_identity": record["sourceRecordIdentity"],
        "validation_status": record["validationStatus"],
        "parse_warnings": record["parseWarnings"],
        "raw_record": record,
    }


def format_dry_run(bundle: ValidatedInput) -> str:
    return "\n".join(
        [
            "Mode: DRY RUN (no network requests; no database changes)",
            f"Snapshot: {bundle.snapshot_id}",
            f"Source version: {bundle.source_version}",
            f"Source records validated: {len(bundle.records)}",
            (
                "Source coverage: complete for this table/language"
                if bundle.source_complete
                else "Source coverage: partial or unconfirmed; publication is blocked"
            ),
            "Local validation errors: 0",
            "Planned: stage one unpublished snapshot version (idempotent by snapshot_id).",
            (
                "Planned: upsert "
                f"{len(bundle.records)} localization rows by "
                "(snapshot_id, data_code, language)."
            ),
            "Publication is a separate command and requires --publish --apply.",
            "Remote insert/update delta is unknown until --apply queries Supabase.",
            "Images: none found in this dataset; no Storage upload planned.",
        ]
    )


def format_publish_dry_run(bundle: ValidatedInput) -> str:
    return "\n".join(
        [
            "Mode: PUBLISH DRY RUN (no network requests; no database changes)",
            f"Snapshot: {bundle.snapshot_id}",
            f"Source records locally verified: {len(bundle.records)}",
            (
                "Source coverage: complete for this table/language"
                if bundle.source_complete
                else "Source coverage: partial or unconfirmed; publication will be rejected"
            ),
            "Planned: verify the staged remote rows, then publish only if all checks pass.",
            "Without --apply, no Supabase request is made.",
        ]
    )


def get_supabase_url() -> str:
    value = os.environ.get("SUPABASE_URL") or os.environ.get(
        "NEXT_PUBLIC_SUPABASE_URL"
    )
    if not value:
        raise ImportInputError(
            "set SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL in the process environment"
        )
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username:
        raise ImportInputError("Supabase URL must be a valid HTTPS URL")
    return value.rstrip("/")


def redact_message(message: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return message


class SupabaseRest:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, str] | None = None,
        payload: Any = None,
        prefer: str | None = None,
    ) -> Any:
        url = f"{self.base_url}{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params, safe="(),.*")
        headers = {
            "apikey": self.api_key,
            "Accept": "application/json",
            "User-Agent": "ranger-atlas-data-importer/1.0",
        }
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if prefer:
            headers["Prefer"] = prefer
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            message = redact_message(body[:1200], [self.api_key])
            raise SupabaseApiError(
                error.code,
                f"Supabase API returned HTTP {error.code}: {message}",
            ) from None
        except urllib.error.URLError as error:
            raise SupabaseApiError(
                0, f"Supabase connection failed: {error.reason}"
            ) from None
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError as error:
            raise SupabaseApiError(
                0, f"Supabase returned invalid JSON: {error}"
            ) from None


def service_client() -> SupabaseRest:
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not key:
        raise ImportInputError("SUPABASE_SECRET_KEY is not set")
    return SupabaseRest(get_supabase_url(), key)


def anon_client() -> SupabaseRest:
    key = os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
    if not key:
        raise ImportInputError("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY is not set")
    return SupabaseRest(get_supabase_url(), key)


def rpc(client: SupabaseRest, name: str, parameters: dict[str, Any]) -> Any:
    return client.request(
        "POST",
        f"/rest/v1/rpc/{name}",
        payload=parameters,
    )


def expected_version(bundle: ValidatedInput) -> dict[str, Any]:
    return {
        "snapshot_id": bundle.snapshot_id,
        "package_name": bundle.package_name,
        "source_version": bundle.source_version,
        "source_manifest_sha256": bundle.source_manifest_sha256,
        "source_file": bundle.source_path,
        "source_file_sha256": bundle.source_file_sha256,
        "content_sha256": bundle.content_sha256,
        "record_count": len(bundle.records),
    }


def stage_snapshot(client: SupabaseRest, bundle: ValidatedInput) -> str:
    version = expected_version(bundle)
    result = rpc(
        client,
        "ranger_ensure_equip_localization_draft",
        {
            f"p_{key}": value
            for key, value in version.items()
        },
    )
    if result not in ("draft", "published"):
        raise SupabaseApiError(0, "stage RPC returned an unexpected status")
    return result


def upsert_rows(client: SupabaseRest, bundle: ValidatedInput) -> None:
    endpoint = "/rest/v1/ranger_equip_localizations"
    params = {"on_conflict": "snapshot_id,data_code,language"}
    for offset in range(0, len(bundle.records), 250):
        rows = [
            database_row(bundle.snapshot_id, row)
            for row in bundle.records[offset : offset + 250]
        ]
        client.request(
            "POST",
            endpoint,
            params=params,
            payload=rows,
            prefer="resolution=merge-duplicates,return=minimal",
        )


def fetch_service_rows(client: SupabaseRest, snapshot_id: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = client.request(
            "GET",
            "/rest/v1/ranger_equip_localizations",
            params={
                "select": LOCALIZATION_SELECT_COLUMNS,
                "snapshot_id": f"eq.{snapshot_id}",
                "order": "data_code.asc,language.asc",
                "limit": "1000",
                "offset": str(offset),
            },
        )
        if not isinstance(page, list):
            raise SupabaseApiError(0, "row verification response is not an array")
        results.extend(page)
        if len(page) < 1000:
            return results
        offset += len(page)


def verify_service_rows(client: SupabaseRest, bundle: ValidatedInput) -> str:
    version_rows = client.request(
        "GET",
        "/rest/v1/ranger_dataset_versions",
        params={
            "select": "snapshot_id,content_sha256,status,record_count",
            "snapshot_id": f"eq.{bundle.snapshot_id}",
        },
    )
    if not isinstance(version_rows, list) or len(version_rows) != 1:
        raise SupabaseApiError(0, "staged dataset version is missing or ambiguous")
    version = version_rows[0]
    if (
        version.get("content_sha256") != bundle.content_sha256
        or version.get("record_count") != len(bundle.records)
    ):
        raise SupabaseApiError(0, "staged version metadata does not match input")
    status = version.get("status")
    if status not in ("draft", "published"):
        raise SupabaseApiError(0, "staged version has an invalid publication status")

    actual_rows = fetch_service_rows(client, bundle.snapshot_id)
    if len(actual_rows) != len(bundle.records):
        raise SupabaseApiError(
            0,
            f"remote row count mismatch: expected {len(bundle.records)}, "
            f"found {len(actual_rows)}",
        )
    expected_by_key = {
        (
            item["sourceRecordIdentity"]["dataCode"],
            item["sourceRecordIdentity"]["language"],
        ): database_row(bundle.snapshot_id, item)
        for item in bundle.records
    }
    actual_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in actual_rows:
        key = (row.get("data_code"), row.get("language"))
        if key in actual_by_key:
            raise SupabaseApiError(0, f"duplicate remote source identity: {key!r}")
        actual_by_key[key] = row
    if set(actual_by_key) != set(expected_by_key):
        raise SupabaseApiError(0, "remote source identities do not match input")

    for key, expected in expected_by_key.items():
        actual = actual_by_key[key]
        for field, expected_value in expected.items():
            if actual.get(field) != expected_value:
                raise SupabaseApiError(
                    0, f"remote row {key!r} differs at field {field}"
                )
    return status


def apply_bundle(bundle: ValidatedInput) -> None:
    client = service_client()
    status = stage_snapshot(client, bundle)
    if status == "draft":
        upsert_rows(client, bundle)
    verified_status = verify_service_rows(client, bundle)
    if verified_status != status:
        raise SupabaseApiError(0, "staged version status changed during import")
    print(
        f"Supabase import verified: snapshot={bundle.snapshot_id}, "
        f"rows={len(bundle.records)}, status={verified_status}."
    )
    print("The snapshot remains unpublished until the separate publish command.")


def publish_bundle(bundle: ValidatedInput) -> None:
    if not bundle.source_complete:
        raise ImportInputError(
            "source coverage is incomplete or unconfirmed; refusing to publish"
        )

    client = service_client()
    status = verify_service_rows(client, bundle)
    if status == "published":
        print(f"Snapshot is already published: {bundle.snapshot_id}.")
        return
    publish_status = rpc(
        client,
        "ranger_publish_equip_localization_snapshot",
        {"p_snapshot_id": bundle.snapshot_id},
    )
    if publish_status != "published":
        raise SupabaseApiError(0, "publish RPC did not confirm published status")
    print(
        f"Supabase import verified and published: snapshot={bundle.snapshot_id}, "
        f"rows={len(bundle.records)}."
    )
    print("The prior published snapshot, if any, is retained as archived.")


def expect_forbidden(
    client: SupabaseRest,
    endpoint: str,
    *,
    params: dict[str, str] | None = None,
    method: str = "GET",
    payload: Any = None,
) -> None:
    try:
        client.request(method, endpoint, params=params, payload=payload)
    except SupabaseApiError as error:
        if error.status in (401, 403):
            return
        raise
    raise SupabaseApiError(
        0, f"public API unexpectedly allowed protected request: {method} {endpoint}"
    )


def fetch_public_localization_rows(
    client: SupabaseRest,
    snapshot_id: str,
    expected_count: int,
) -> list[Any]:
    rows: list[Any] = []
    for offset in range(0, expected_count, PUBLIC_VERIFICATION_PAGE_SIZE):
        page = client.request(
            "GET",
            "/rest/v1/ranger_equip_localizations",
            params={
                "select": PUBLIC_LOCALIZATION_COLUMNS,
                "snapshot_id": f"eq.{snapshot_id}",
                "order": "data_code.asc,language.asc",
                "limit": str(PUBLIC_VERIFICATION_PAGE_SIZE),
                "offset": str(offset),
            },
        )
        if not isinstance(page, list):
            raise SupabaseApiError(
                0, "anonymous published rows have an invalid response format"
            )
        rows.extend(page)
    return rows


def verify_anonymous_access(bundle: ValidatedInput) -> None:
    client = anon_client()
    snapshot_id = bundle.snapshot_id

    access_check = rpc(client, "ranger_assert_public_data_access", {})
    if access_check is not True:
        raise SupabaseApiError(0, "database public-access assertion did not pass")

    versions = client.request(
        "GET",
        "/rest/v1/ranger_dataset_versions",
        params={
            "select": "snapshot_id,package_name,source_version,record_count,status",
            "snapshot_id": f"eq.{snapshot_id}",
            "status": "eq.published",
        },
    )
    if not isinstance(versions, list) or len(versions) != 1:
        raise SupabaseApiError(
            0, "anonymous client cannot read the expected published version"
        )
    if versions[0].get("record_count") != len(bundle.records):
        raise SupabaseApiError(0, "published version count differs from local input")

    public_rows = fetch_public_localization_rows(
        client,
        snapshot_id,
        len(bundle.records),
    )
    if len(public_rows) != len(bundle.records):
        raise SupabaseApiError(
            0, "anonymous published-row count differs from local input"
        )
    expected_public = {
        (row["sourceText"]["dataCode"], row["language"]): {
            "snapshot_id": snapshot_id,
            "data_code": row["sourceText"]["dataCode"],
            "language": row["language"],
            "msg_type": row["sourceText"]["msgType"],
            "message": row["sourceText"]["text"],
        }
        for row in bundle.records
    }
    actual_public = {
        (row.get("data_code"), row.get("language")): row for row in public_rows
    }
    if actual_public != expected_public:
        raise SupabaseApiError(0, "anonymous published rows differ from local input")

    hidden_versions = client.request(
        "GET",
        "/rest/v1/ranger_dataset_versions",
        params={
            "select": "snapshot_id",
            "status": "neq.published",
        },
    )
    if hidden_versions != []:
        raise SupabaseApiError(0, "anonymous API exposed an unpublished version")

    expect_forbidden(
        client,
        "/rest/v1/ranger_equip_localizations",
        params={
            "select": PRIVATE_LOCALIZATION_COLUMNS,
            "snapshot_id": f"eq.{snapshot_id}",
        },
    )
    expect_forbidden(
        client,
        "/rest/v1/ranger_dataset_versions",
        params={
            "select": "source_manifest_sha256,source_file_sha256",
            "snapshot_id": f"eq.{snapshot_id}",
        },
    )
    print(
        "Anonymous access verified: published rows readable; unpublished versions "
        "and private provenance denied; database assertion confirms no public "
        "write privileges or non-SELECT RLS policies."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and import the normalized lang_equip localization dataset. "
            "Import and publication are separate; the default is local-only."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "data/normalized/lr_20261116T212608096_7b99bdd0/"
            "equip_localization.json"
        ),
        help="normalized JSON input path",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="stage and remotely verify the dataset as unpublished",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="request publication; combine with --apply to make the change",
    )
    verification = parser.add_mutually_exclusive_group()
    verification.add_argument(
        "--verify-anon",
        action="store_true",
        help="verify public anonymous read-only access after migration/import",
    )
    verification.add_argument(
        "--dry-run",
        action="store_true",
        help="explicitly select the default local-only mode",
    )
    args = parser.parse_args(argv)
    if args.verify_anon and (args.apply or args.publish):
        parser.error("--verify-anon cannot be combined with --apply or --publish")

    bundle, errors = load_and_validate(args.input)
    if errors:
        print(f"Input validation errors: {len(errors)}")
        for error in errors:
            print(f"- {error}")
        return 2
    if bundle is None:
        print("Input validation failed without a usable dataset.", file=sys.stderr)
        return 2

    if args.apply and args.publish:
        try:
            publish_bundle(bundle)
        except (ImportInputError, SupabaseApiError) as error:
            print(
                f"Publication failed; prior published version is unchanged: {error}",
                file=sys.stderr,
            )
            return 1
        return 0

    if args.publish:
        print(format_publish_dry_run(bundle))
        return 0

    if args.apply:
        try:
            apply_bundle(bundle)
        except (ImportInputError, SupabaseApiError) as error:
            print(f"Import failed; no version was published: {error}", file=sys.stderr)
            return 1
        return 0

    if args.verify_anon:
        try:
            verify_anonymous_access(bundle)
        except (ImportInputError, SupabaseApiError) as error:
            print(f"Anonymous access verification failed: {error}", file=sys.stderr)
            return 1
        return 0

    print(format_dry_run(bundle))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
