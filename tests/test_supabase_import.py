import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from import_supabase import (  # noqa: E402
    ImportInputError,
    SupabaseApiError,
    apply_bundle,
    database_row,
    expected_version,
    fetch_public_localization_rows,
    format_dry_run,
    load_and_validate,
    main,
    publish_bundle,
)


INPUT = (
    ROOT
    / "data"
    / "normalized"
    / "lr_20261116T212608096_7b99bdd0"
    / "equip_localization.json"
)


class FakeSupabaseRest:
    def __init__(self, bundle, include_rows=True):
        self.bundle = bundle
        self.include_rows = include_rows
        self.publish_called = False

    def request(
        self,
        method,
        endpoint,
        *,
        params=None,
        payload=None,
        prefer=None,
    ):
        if endpoint.endswith("ranger_ensure_equip_localization_draft"):
            return "draft"
        if endpoint == "/rest/v1/ranger_equip_localizations" and method == "POST":
            return None
        if endpoint == "/rest/v1/ranger_dataset_versions":
            version = expected_version(self.bundle)
            return [
                {
                    "snapshot_id": version["snapshot_id"],
                    "content_sha256": version["content_sha256"],
                    "record_count": version["record_count"],
                    "status": "draft",
                }
            ]
        if endpoint == "/rest/v1/ranger_equip_localizations" and method == "GET":
            if not self.include_rows:
                return []
            return [
                database_row(self.bundle.snapshot_id, row)
                for row in self.bundle.records
            ]
        if endpoint.endswith("ranger_publish_equip_localization_snapshot"):
            self.publish_called = True
            return "published"
        raise AssertionError(f"unexpected fake request: {method} {endpoint}")


class SupabaseImportTests(unittest.TestCase):
    def setUp(self):
        self.bundle, errors = load_and_validate(INPUT)
        self.assertEqual(errors, [])
        self.assertIsNotNone(self.bundle)

    def write_test_document(self, document):
        temporary_directory = tempfile.TemporaryDirectory(dir=ROOT / "tests")
        self.addCleanup(temporary_directory.cleanup)
        path = Path(temporary_directory.name) / "normalized-test-input.json"
        path.write_text(
            json.dumps(document, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_real_normalized_file_passes_local_source_validation(self):
        self.assertEqual(len(self.bundle.records), 10)
        self.assertEqual(self.bundle.package_name, "com.linecorp.LGRGS")
        self.assertEqual(self.bundle.source_version, "12.4.0")
        self.assertEqual(len(self.bundle.content_sha256), 64)
        self.assertFalse(self.bundle.source_complete)

    def test_duplicate_source_identity_is_rejected(self):
        document = copy.deepcopy(self.bundle.document)
        duplicate = document["records"][1]
        first = document["records"][0]
        duplicate["sourceText"]["dataCode"] = first["sourceText"]["dataCode"]
        duplicate["sourceRecordIdentity"]["dataCode"] = first["sourceText"]["dataCode"]

        _, errors = load_and_validate(self.write_test_document(document))

        self.assertTrue(any("duplicates source identity" in error for error in errors))

    def test_missing_source_identity_is_rejected(self):
        document = copy.deepcopy(self.bundle.document)
        document["records"][0]["sourceRecordIdentity"] = None

        _, errors = load_and_validate(self.write_test_document(document))

        self.assertTrue(any("sourceText or sourceRecordIdentity" in error for error in errors))

    def test_unavailable_item_fields_cannot_be_filled_by_guess(self):
        document = copy.deepcopy(self.bundle.document)
        document["records"][0]["starCount"] = 7

        _, errors = load_and_validate(self.write_test_document(document))

        self.assertTrue(any(".starCount must remain null" in error for error in errors))

    def test_normalized_text_must_match_the_manifest_verified_database(self):
        document = copy.deepcopy(self.bundle.document)
        document["records"][0]["sourceText"]["text"] = "not the source value"

        _, errors = load_and_validate(self.write_test_document(document))

        self.assertTrue(
            any("does not match the source SQLite row" in error for error in errors)
        )

    def test_database_payload_preserves_provenance_without_game_id(self):
        record = self.bundle.records[0]
        payload = database_row(self.bundle.snapshot_id, record)

        self.assertEqual(
            payload["data_code"],
            record["sourceRecordIdentity"]["dataCode"],
        )
        self.assertEqual(payload["source_record_identity"], record["sourceRecordIdentity"])
        self.assertEqual(payload["raw_record"], record)
        self.assertNotIn("game_id", payload)

    def test_default_dry_run_makes_no_http_requests(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True):
            with patch("import_supabase.SupabaseRest.request") as request:
                with contextlib.redirect_stdout(output):
                    result = main([])

        self.assertEqual(result, 0)
        request.assert_not_called()
        self.assertIn("Mode: DRY RUN", output.getvalue())
        self.assertIn("publication is blocked", output.getvalue())
        self.assertIn("Remote insert/update delta is unknown", output.getvalue())

    def test_dry_run_reports_changes_without_claiming_remote_state(self):
        output = format_dry_run(self.bundle)

        self.assertIn("upsert 10 localization rows", output)
        self.assertIn("Remote insert/update delta is unknown", output)
        self.assertIn("no network requests", output)

    def test_apply_stages_and_verifies_without_publishing(self):
        fake = FakeSupabaseRest(self.bundle)
        with patch("import_supabase.service_client", return_value=fake):
            with contextlib.redirect_stdout(io.StringIO()):
                apply_bundle(self.bundle)

        self.assertFalse(fake.publish_called)

    def test_publish_rejects_unconfirmed_source_coverage(self):
        fake = FakeSupabaseRest(self.bundle)
        with patch("import_supabase.service_client", return_value=fake):
            with self.assertRaisesRegex(ImportInputError, "coverage"):
                publish_bundle(self.bundle)

        self.assertFalse(fake.publish_called)

    def test_publish_occurs_only_after_remote_rows_verify(self):
        complete_bundle = copy.copy(self.bundle)
        complete_bundle.source_complete = True
        fake = FakeSupabaseRest(complete_bundle)
        with patch("import_supabase.service_client", return_value=fake):
            with contextlib.redirect_stdout(io.StringIO()):
                publish_bundle(complete_bundle)

        self.assertTrue(fake.publish_called)

    def test_remote_validation_failure_does_not_publish(self):
        complete_bundle = copy.copy(self.bundle)
        complete_bundle.source_complete = True
        fake = FakeSupabaseRest(complete_bundle, include_rows=False)
        with patch("import_supabase.service_client", return_value=fake):
            with self.assertRaises(SupabaseApiError):
                publish_bundle(complete_bundle)

        self.assertFalse(fake.publish_called)

    def test_public_row_verification_fetches_all_pages(self):
        class PaginatedClient:
            def __init__(self):
                self.offsets = []

            def request(self, method, endpoint, *, params=None, payload=None, prefer=None):
                self.assert_request(method, endpoint, params)
                offset = int(params["offset"])
                limit = int(params["limit"])
                self.offsets.append(offset)
                return [
                    {"row": index}
                    for index in range(offset, min(offset + limit, 1346))
                ]

            def assert_request(self, method, endpoint, params):
                if (
                    method != "GET"
                    or endpoint != "/rest/v1/ranger_equip_localizations"
                    or params is None
                ):
                    raise AssertionError("unexpected public row query")

        client = PaginatedClient()

        rows = fetch_public_localization_rows(
            client,
            "test_snapshot",
            1346,
        )

        self.assertEqual(len(rows), 1346)
        self.assertEqual(client.offsets, [0, 500, 1000])

    def test_publish_flag_without_apply_is_a_local_dry_run(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True):
            with patch("import_supabase.SupabaseRest.request") as request:
                with contextlib.redirect_stdout(output):
                    result = main(["--publish"])

        self.assertEqual(result, 0)
        request.assert_not_called()
        self.assertIn("PUBLISH DRY RUN", output.getvalue())

    def test_publish_apply_rejects_incomplete_legacy_input(self):
        with patch.dict(os.environ, {}, clear=True):
            result = main(["--publish", "--apply"])

        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
