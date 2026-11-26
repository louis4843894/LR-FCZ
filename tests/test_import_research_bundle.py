import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import import_research_bundle as research_import  # noqa: E402


class FakeSupabaseRest:
    def __init__(self):
        self.snapshot = None
        self.records = []

    def request(
        self,
        method,
        endpoint,
        *,
        params=None,
        payload=None,
        prefer=None,
    ):
        if endpoint == "/rest/v1/ranger_research_snapshots" and method == "GET":
            if self.snapshot is None:
                return []
            return [self.snapshot]
        if endpoint == "/rest/v1/ranger_research_snapshots" and method == "POST":
            self.snapshot = dict(payload)
            return None
        if endpoint == "/rest/v1/ranger_research_records" and method == "POST":
            for record in payload:
                identity = record["source_record_identity"]
                existing = next(
                    (
                        item
                        for item in self.records
                        if item["source_record_identity"] == identity
                    ),
                    None,
                )
                if existing is None:
                    self.records.append(dict(record))
                else:
                    existing.update(record)
            return None
        if endpoint == "/rest/v1/ranger_research_records" and method == "GET":
            return [
                {
                    "source_record_identity": row["source_record_identity"],
                    "record_sha256": row["record_sha256"],
                }
                for row in self.records
            ]
        raise AssertionError(f"unexpected fake request: {method} {endpoint}")


class ResearchBundleImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory(dir=ROOT / "tests")
        self.addCleanup(self.temporary_directory.cleanup)
        self.workspace = Path(self.temporary_directory.name)
        self.snapshot_id = "test_research_snapshot"
        self.source_path = (
            self.workspace
            / "data"
            / "raw"
            / self.snapshot_id
            / "apk"
            / "source.bin"
        )
        self.source_path.parent.mkdir(parents=True)
        self.source_path.write_bytes(b"test-only source bytes")
        source_digest = hashlib.sha256(self.source_path.read_bytes()).hexdigest()
        self.manifest_path = (
            self.workspace / "data" / "raw" / self.snapshot_id / "manifest.json"
        )
        manifest = {
            "snapshotId": self.snapshot_id,
            "complete": True,
            "snapshotStatus": "complete",
            "files": [
                {
                    "path": f"data/raw/{self.snapshot_id}/apk/source.bin",
                    "bytes": self.source_path.stat().st_size,
                    "sha256": source_digest,
                }
            ],
        }
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        manifest_digest = hashlib.sha256(self.manifest_path.read_bytes()).hexdigest()
        self.bundle_path = self.workspace / "bundle.json"
        record = {
            "sourceRecordIdentity": {"sourceId": "test-row"},
            "sourceFile": f"data/raw/{self.snapshot_id}/apk/source.bin",
            "sourceFileSha256": source_digest,
            "sourceRecordLocator": "test-row-1",
            "rawRecord": {"value": "test-only"},
            "normalizedRecord": None,
            "validationStatus": "source-row-verified",
            "parseWarnings": [],
        }
        document = {
            "schemaVersion": 1,
            "bundleKind": "ranger-research-bundle",
            "snapshotId": self.snapshot_id,
            "module": "characters",
            "sourceKind": "static",
            "sourceVersion": "test-only",
            "capturedAt": "2026-01-01T00:00:00+00:00",
            "sourceManifestSha256": manifest_digest,
            "coverage": {
                "scope": "test-only",
                "complete": True,
                "sourceRecordCount": 1,
                "parsedRecordCount": 1,
            },
            "recordCount": 1,
            "records": [record],
        }
        self.bundle_path.write_text(
            json.dumps(document, ensure_ascii=False),
            encoding="utf-8",
        )
        self.root_patch = patch.object(research_import, "ROOT", self.workspace)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def test_valid_bundle_is_verified_and_hashes_source_rows(self):
        bundle = research_import.load_bundle(self.bundle_path)

        self.assertTrue(bundle.source_complete)
        self.assertEqual(len(bundle.rows), 1)
        self.assertEqual(len(bundle.content_sha256), 64)
        self.assertEqual(
            bundle.rows[0]["source_record_identity"],
            {"sourceId": "test-row"},
        )

    def test_duplicate_identity_is_rejected(self):
        document = json.loads(self.bundle_path.read_text(encoding="utf-8"))
        document["records"].append(document["records"][0])
        document["recordCount"] = 2
        document["coverage"]["sourceRecordCount"] = 2
        document["coverage"]["parsedRecordCount"] = 2
        self.bundle_path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaisesRegex(
            research_import.BundleValidationError, "duplicates a source identity"
        ):
            research_import.load_bundle(self.bundle_path)

    def test_sensitive_field_names_are_rejected_without_printing_values(self):
        document = json.loads(self.bundle_path.read_text(encoding="utf-8"))
        document["records"][0]["rawRecord"]["access_token"] = "test-only-secret"
        self.bundle_path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaisesRegex(
            research_import.BundleValidationError, "prohibited sensitive field name"
        ) as error:
            research_import.load_bundle(self.bundle_path)
        self.assertNotIn("test-only-secret", str(error.exception))

    def test_default_mode_is_local_only(self):
        output = io.StringIO()
        with patch("import_research_bundle.service_client") as service_client:
            with contextlib.redirect_stdout(output):
                result = research_import.main(["--input", str(self.bundle_path)])

        self.assertEqual(result, 0)
        service_client.assert_not_called()
        self.assertIn("Mode: DRY RUN", output.getvalue())

    def test_stage_is_idempotent_by_snapshot_and_source_identity(self):
        bundle = research_import.load_bundle(self.bundle_path)
        fake = FakeSupabaseRest()
        with patch("import_research_bundle.service_client", return_value=fake):
            with contextlib.redirect_stdout(io.StringIO()):
                research_import.stage_bundle(bundle)
                research_import.stage_bundle(bundle)

        self.assertEqual(len(fake.records), 1)
        self.assertEqual(fake.snapshot["status"], "draft")

    def test_incomplete_coverage_blocks_publish_before_network_access(self):
        document = json.loads(self.bundle_path.read_text(encoding="utf-8"))
        document["coverage"]["complete"] = False
        self.bundle_path.write_text(json.dumps(document), encoding="utf-8")
        bundle = research_import.load_bundle(self.bundle_path)

        with patch("import_research_bundle.service_client") as service_client:
            with self.assertRaisesRegex(
                research_import.BundleValidationError, "coverage"
            ):
                research_import.publish_bundle(bundle)

        service_client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
