import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from parse_equip_localization import ensure_unique_record_ids, normalize_row


class EquipLocalizationParserTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "snapshot_id": "test_snapshot",
            "extracted_path": "data/extracted/test_snapshot/lang_equip.ndb",
            "apk_member": "base.apk!/assets/res/tutorial_res/db/lang_equip/lang_equip.ndb",
            "source_sha256": "a" * 64,
        }

    def test_preserves_original_translation_key_without_claiming_equipment_id(self):
        record = normalize_row(
            {
                "dataCode": "FIX_AVD_PROB_MUL_nm",
                "language": "zh-Hant",
                "msgType": "EQUIP",
                "msg": "普通攻擊無效機率",
            },
            **self.source,
        )

        self.assertEqual(
            record["sourceRecordIdentity"],
            {"dataCode": "FIX_AVD_PROB_MUL_nm", "language": "zh-Hant"},
        )
        self.assertEqual(record["sourceText"]["dataCode"], "FIX_AVD_PROB_MUL_nm")
        self.assertIsNone(record["gameId"])
        self.assertEqual(record["sourceText"]["text"], "普通攻擊無效機率")

    def test_unavailable_item_fields_stay_null_without_numeric_conversion(self):
        record = normalize_row(
            {
                "dataCode": "SOME_LABEL",
                "language": "zh-Hant",
                "msgType": "EQUIP",
                "msg": "原始文字 50%",
            },
            **self.source,
        )

        for field in (
            "gameId",
            "name",
            "confirmedCategory",
            "starCount",
            "rawNumericValues",
            "rawEffectParameters",
            "confirmedDisplayValues",
            "imageMapping",
        ):
            self.assertIsNone(record[field], field)
        self.assertEqual(record["sourceText"]["text"], "原始文字 50%")

    def test_missing_source_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "dataCode"):
            normalize_row(
                {
                    "dataCode": None,
                    "language": "zh-Hant",
                    "msgType": "EQUIP",
                    "msg": "標籤",
                },
                **self.source,
            )

    def test_duplicate_composite_source_identity_is_rejected(self):
        record = normalize_row(
            {
                "dataCode": "SAME_LABEL",
                "language": "zh-Hant",
                "msgType": "EQUIP",
                "msg": "標籤",
            },
            **self.source,
        )
        duplicate = dict(record)

        with self.assertRaisesRegex(ValueError, "duplicate"):
            ensure_unique_record_ids([record, duplicate])

    def test_same_data_code_in_different_languages_is_not_a_duplicate(self):
        records = []
        for language in ("zh-Hant", "en"):
            records.append(
                normalize_row(
                    {
                        "dataCode": "SAME_LABEL",
                        "language": language,
                        "msgType": "EQUIP",
                        "msg": "label",
                    },
                    **self.source,
                )
            )

        ensure_unique_record_ids(records)


if __name__ == "__main__":
    unittest.main()
