import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20261117000000_ranger_multimodule_research.sql"
)


class ResearchMigrationContractTests(unittest.TestCase):
    def test_all_research_tables_are_private_and_have_rls_enabled(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        table_names = re.findall(
            r"create table if not exists public\.(ranger_[a-z_]+)",
            sql,
            flags=re.IGNORECASE,
        )
        self.assertGreaterEqual(len(table_names), 12)
        for table_name in table_names:
            self.assertRegex(
                sql,
                rf"revoke all on public\.{table_name} from public, anon, authenticated;",
            )
            self.assertRegex(
                sql,
                rf"alter table public\.{table_name} enable row level security;",
            )
        self.assertNotRegex(
            sql,
            r"grant\s+select\s+on\s+public\.ranger_.*\s+to\s+(public|anon|authenticated)",
        )

    def test_publish_gate_checks_coverage_counts_and_preserves_scope_version(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("if not target.is_complete then", sql)
        self.assertIn("research snapshot row counts do not match expected counts", sql)
        self.assertIn("research snapshot contains unverified source records", sql)
        self.assertIn("set status = 'archived'", sql)
        self.assertIn("set status = 'published', published_at = now()", sql)
        self.assertIn("ranger_publish_research_snapshot(text, text)", sql)


if __name__ == "__main__":
    unittest.main()
