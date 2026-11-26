import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from diff_data import compare_files, compare_records  # noqa: E402


class SnapshotDiffTests(unittest.TestCase):
    def test_file_changes_keep_missing_distinct_from_deletion(self):
        changes = compare_files(
            {
                "same.apk": {"path": "old/same.apk", "sha256": "a" * 64, "bytes": 1},
                "changed.db": {
                    "path": "old/changed.db",
                    "sha256": "b" * 64,
                    "bytes": 2,
                },
                "missing.zip": {
                    "path": "old/missing.zip",
                    "sha256": "c" * 64,
                    "bytes": 3,
                },
            },
            {
                "same.apk": {"path": "new/same.apk", "sha256": "a" * 64, "bytes": 1},
                "changed.db": {
                    "path": "new/changed.db",
                    "sha256": "d" * 64,
                    "bytes": 4,
                },
                "added.ndb": {
                    "path": "new/added.ndb",
                    "sha256": "e" * 64,
                    "bytes": 5,
                },
            },
        )

        self.assertEqual(changes["counts"], {
            "added": 1,
            "modified": 1,
            "unchanged": 1,
            "missingFromNew": 1,
        })
        self.assertIn("not-official-deletion", changes["missingFromNew"][0]["classification"])

    def test_record_comparison_reports_text_and_numeric_fields_without_inference(self):
        old_record = {
            "gameId": "test-item",
            "language": "zh-Hant",
            "name": "測試名稱",
            "value": 10,
            "sourceFileSha256": "a" * 64,
        }
        new_record = {
            "gameId": "test-item",
            "language": "zh-Hant",
            "name": "測試名稱修正",
            "value": 12,
            "sourceFileSha256": "b" * 64,
        }
        old_records = {
            '{"gameId": "test-item", "language": "zh-Hant"}': old_record,
        }
        new_records = {
            '{"gameId": "test-item", "language": "zh-Hant"}': new_record,
        }
        old_document = {
            "_identityLabels": {
                '{"gameId": "test-item", "language": "zh-Hant"}':
                    '{"gameId": "test-item", "language": "zh-Hant"}'
            },
            "coverage": {"complete": False},
        }
        new_document = {
            "_identityLabels": old_document["_identityLabels"],
            "coverage": {"complete": True},
            "datasetKind": "test-only",
        }

        result = compare_records(
            old_records,
            old_document,
            new_records,
            new_document,
        )

        self.assertEqual(result["counts"]["changedRecords"], 1)
        self.assertEqual(result["textChangeCount"], 1)
        self.assertEqual(result["numericFieldChangeCount"], 1)
        self.assertFalse(result["missingMeansOfficialDeletion"])


if __name__ == "__main__":
    unittest.main()
