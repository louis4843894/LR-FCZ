import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'scripts/runtime')]
import collect_guild_pvp
import update_local_game_data

class GuildPvpCacheTests(unittest.TestCase):
    def test_ranking_first_selection_blocks_legacy_guild_pvp_collection(self):
        with patch.object(sys,'argv',['collect_guild_pvp.py']),patch.object(collect_guild_pvp,'get_collection_target',return_value='rankings'),patch.object(collect_guild_pvp,'command') as device:
            with self.assertRaisesRegex(RuntimeError,'ranking-first'):collect_guild_pvp.main()
            device.assert_not_called()
    def test_on_demand_update_also_requires_ranking_context(self):
        with patch.object(update_local_game_data,'get_collection_target',return_value='rankings'):
            with self.assertRaisesRegex(ValueError,'ranking context'):update_local_game_data.capture_visible('pvp')
    def test_observed_single_team_does_not_require_invented_B_team(self):
        roster={'capturedAt':'2026-11-25T00:00:00Z','members':[{'playerId':'fixture'}]}
        row={'playerId':'fixture','purpose':'pvp_defense','status':'success','retrievedAt':'2026-11-25T01:00:00Z','teamId':'pvpteam/1','unobservedPositionIndices':[]}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=root/'data/normalized';p.mkdir(parents=True)
            file=p/'defense-teams.private.json';file.write_text(json.dumps({'snapshots':[row]}))
            with patch.object(collect_guild_pvp,'ROOT',root):
                self.assertEqual(collect_guild_pvp.valid_cached_owners(roster),{'fixture'})
                row['unobservedPositionIndices']=[3];file.write_text(json.dumps({'snapshots':[row]}))
                self.assertEqual(collect_guild_pvp.valid_cached_owners(roster),set())
                row.update(unobservedPositionIndices=[],retrievedAt='2026-11-24T23:00:00Z');file.write_text(json.dumps({'snapshots':[row]}))
                self.assertEqual(collect_guild_pvp.valid_cached_owners(roster),set())

if __name__=='__main__':unittest.main()
