import json,sqlite3,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'scripts/runtime')]
from pvp_scope_policy import LABELS,matches_scope,migrate_current_scopes
from fetch_ranked_pvp_response import normal_json,fetch,AcquisitionStopped
from activate_completed_pvp_scopes import phase_ready

class ScopePolicyTests(unittest.TestCase):
 def test_each_subdivision_is_distinct_and_lower_groups_are_excluded(self):
  self.assertEqual(len(LABELS),10)
  for group in ['大師','鑽石','黃金']:
   self.assertEqual([s for s in LABELS if matches_scope(s,group)],[group+str(i) for i in (1,2,3)])
  for old in ['白銀','青銅']:self.assertFalse(matches_scope(old,'all'))
  self.assertTrue(matches_scope('鑽石','鑽石3'));self.assertFalse(matches_scope('鑽石','鑽石1'))
 def test_cutoff_removes_only_current_pointers_preserving_history(self):
  with sqlite3.connect(':memory:') as db:
   db.executescript('CREATE TABLE ranking_snapshots(snapshot_id TEXT PRIMARY KEY);CREATE TABLE current_rankings(scope_label TEXT PRIMARY KEY,snapshot_id TEXT REFERENCES ranking_snapshots);')
   db.executemany('INSERT INTO ranking_snapshots VALUES (?)',[(x,) for x in ['master-old','silver-old','bronze-old']])
   db.executemany('INSERT INTO current_rankings VALUES (?,?)',[('大師','master-old'),('白銀','silver-old'),('青銅','bronze-old')]);migrate_current_scopes(db)
   self.assertEqual(db.execute('SELECT * FROM current_rankings').fetchall(),[('大師3','master-old')]);self.assertEqual(db.execute('SELECT count(*) FROM ranking_snapshots').fetchone()[0],3)
 def test_excluded_scopes_cannot_make_ranking_or_defense_requests(self):
  class Session:base_url='https://rangers-api.line-apps.com/v12.4'
  with patch('fetch_ranked_pvp_response.urllib.request.build_opener') as network:
   for path in ['/pvp/league/rank/SILVER_3','/pvp/league/rank/BRONZE']:
    with self.assertRaisesRegex(AcquisitionStopped,'unverified_normal_path'):normal_json(Session(),path)
   with self.assertRaisesRegex(AcquisitionStopped,'scope_excluded_by_user'):fetch(Session(),{'scope':{'label':'白銀'}},{'playerId':'fixture'})
   network.assert_not_called()
 def test_each_phase_requires_every_terminal_response_and_latest_failure_blocks_activation(self):
  with sqlite3.connect(':memory:') as db:
   db.execute('CREATE TABLE ranking_defense_attempts(ranking_snapshot_id TEXT,player_id TEXT,status TEXT,attempted_at TEXT)')
   db.execute('INSERT INTO ranking_defense_attempts VALUES (?,?,?,?)',('scope','a','success','1'))
   doc={'players':[{'playerId':'a'},{'playerId':'b'}]};self.assertFalse(phase_ready(db,'scope',doc)[0])
   db.execute('INSERT INTO ranking_defense_attempts VALUES (?,?,?,?)',('scope','b','unavailable','2'));self.assertTrue(phase_ready(db,'scope',doc)[0])
   db.execute('INSERT INTO ranking_defense_attempts VALUES (?,?,?,?)',('scope','a','failed','3'));self.assertFalse(phase_ready(db,'scope',doc)[0]);self.assertFalse(phase_ready(db,'scope',{'players':[]})[0])

if __name__=='__main__':unittest.main()
