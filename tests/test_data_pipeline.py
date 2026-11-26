import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import data_pipeline  # noqa: E402


class DataPipelineCommandTests(unittest.TestCase):
    def test_acquire_requires_explicit_device_and_package(self):
        with patch("data_pipeline.run_script", return_value=0) as run_script:
            result = data_pipeline.main(
                [
                    "acquire",
                    "--adb",
                    r"C:\LDPlayer\LDPlayer9\adb.exe",
                    "--serial",
                    "emulator-5554",
                    "--package",
                    "com.linecorp.LGRGS",
                    "--snapshot-id",
                    "test_snapshot",
                ]
            )

        self.assertEqual(result, 0)
        run_script.assert_called_once_with(
            "acquire_apk_snapshot.py",
            [
                "--adb",
                r"C:\LDPlayer\LDPlayer9\adb.exe",
                "--serial",
                "emulator-5554",
                "--package",
                "com.linecorp.LGRGS",
                "--snapshot-id",
                "test_snapshot",
            ],
        )

    def test_import_default_is_dry_run_and_publish_is_separate(self):
        with patch("data_pipeline.run_script", return_value=0) as run_script:
            data_pipeline.main(["import", "--input", "data\\normalized\\test.json"])
            data_pipeline.main(
                ["publish", "--input", "data\\normalized\\test.json", "--apply"]
            )

        self.assertEqual(run_script.call_args_list[0].args, (
            "import_supabase.py",
            ["--input", "data\\normalized\\test.json"],
        ))
        self.assertEqual(run_script.call_args_list[1].args, (
            "import_supabase.py",
            ["--input", "data\\normalized\\test.json", "--publish", "--apply"],
        ))

    def test_research_import_uses_private_bundle_adapter(self):
        with patch("data_pipeline.run_script", return_value=0) as run_script:
            data_pipeline.main(
                ["import", "--research", "--input", "bundle.json", "--apply"]
            )
            data_pipeline.main(
                ["publish", "--research", "--input", "bundle.json"]
            )

        self.assertEqual(run_script.call_args_list[0].args, (
            "import_research_bundle.py",
            ["--input", "bundle.json", "--apply"],
        ))
        self.assertEqual(run_script.call_args_list[1].args, (
            "import_research_bundle.py",
            ["--input", "bundle.json", "--publish"],
        ))


if __name__ == "__main__":
    unittest.main()
