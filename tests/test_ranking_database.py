import json,sqlite3,sys,tempfile,unittest
from contextlib import closing
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from ranking_database import save_snapshot,save_failure,latest_attempts
FULL=ROOT/'data/research/runtime.private/pvp-ranking-20261125T092412Z-1f35f3'
PARTIAL=ROOT/'data/research/runtime.private/pvp-ranking-20261125T091720Z-3c92a1'
BRONZE=ROOT/'data/research/runtime.private/pvp-ranking-20261125T091619Z-f40206'

@unittest.skipUnless(FULL.exists(),'requires actual local ranking copies')
class RankingStorageTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.database=Path(self.temp.name)/'isolated.sqlite'
 def tearDown(self):self.temp.cleanup()
 def test_real_source_is_idempotent_and_partial_does_not_replace_complete(self):
  full=save_snapshot(FULL,self.database);save_snapshot(FULL,self.database);save_snapshot(PARTIAL,self.database)
  with closing(sqlite3.connect(self.database)) as db:
   self.assertEqual(db.execute('SELECT count(*) FROM ranking_snapshots').fetchone()[0],2)
   self.assertEqual(db.execute("SELECT snapshot_id FROM current_rankings WHERE scope_label='傳奇'").fetchone()[0],full['snapshotId'])
   self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
  self.assertEqual(len(full['players']),200);self.assertEqual(len({p['rank'] for p in full['players']}),200)
 def test_leagues_remain_separate_and_only_real_sources_are_loaded(self):
  legend=save_snapshot(FULL,self.database);bronze=save_snapshot(BRONZE,self.database)
  self.assertFalse({p['playerId'] for p in legend['players']}&{p['playerId'] for p in bronze['players']})
  with closing(sqlite3.connect(self.database)) as db:self.assertEqual(db.execute('SELECT count(*) FROM current_rankings').fetchone()[0],2)
 def test_failure_is_not_an_empty_team_and_unknown_owner_cannot_be_recorded(self):
  source=save_snapshot(FULL,self.database);uid=source['players'][0]['playerId']
  save_failure(source['snapshotId'],uid,'isolated_test_failure',self.database)
  row=latest_attempts(source['snapshotId'],self.database)[uid]
  self.assertEqual(row['status'],'failed');self.assertIsNone(row['defenseRetrievedAt'])
  with self.assertRaisesRegex(ValueError,'outside ranking'):save_failure(source['snapshotId'],'unrelated-test-owner','isolated_test_failure',self.database)
  with self.assertRaisesRegex(ValueError,'non-sensitive'):save_failure(source['snapshotId'],uid,'unsafe dynamic message',self.database)

if __name__=='__main__':unittest.main()
