import copy,json,sqlite3,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'scripts/runtime')]
from guild_public_formations import accept,parse
from verify_guildwar_group_purpose import comparison
from collect_guild_public_formations import collect
from fetch_ranked_pvp_response import AcquisitionStopped
SOURCE=ROOT/'data/research/runtime.private/ranked-guild-war-group-20261126T063426Z-1a9498'

class FormationTests(unittest.TestCase):
 def test_comparison_does_not_mix_unit_and_equipment_maps(self):
  group={'1':[{'slot':0,'invenId':123,'unitCode':'fixture-unit','equipMap':{'ARMOR':{'invenId':11,'itemCode':'eq_fixture','currentEnchant':5}}}]}
  expected=comparison(group,copy.deepcopy(group));self.assertTrue(expected['exactMatch']);self.assertEqual(expected['sameUnitInstancesAtSameSlots'],1);self.assertEqual(expected['sameGearInstancesAndEnhancement'],1)
  changed=copy.deepcopy(group);changed['1'][0]['slot']=1
  result=comparison(group,changed);self.assertFalse(result['exactMatch']);self.assertEqual(result['overlappingUnitInstances'],1)
 def test_refusal_prevents_even_runtime_session_loading_on_repeat(self):
  from types import SimpleNamespace
  with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as tmp:
   root=Path(tmp);state=root/'data/research/runtime.private/guild-public-formations-session';state.mkdir(parents=True)
   (state/'progress.private.json').write_text(json.dumps({'stopReason':'http_access_denied'}))
   with patch('collect_guild_public_formations.ROOT',root),patch('collect_guild_public_formations.load_session') as session:
    with self.assertRaisesRegex(AcquisitionStopped,'manual_access_review'):collect(SimpleNamespace(max_guilds=1,max_members=50,max_seconds=30))
    session.assert_not_called()
 @unittest.skipUnless((SOURCE/'response.private.json').exists(),'reviewed source required')
 def test_saved_public_formation_never_becomes_deployed_or_saved_defense(self):
  doc=parse(SOURCE);self.assertEqual(doc['purpose'],'guildwar_attack_formation');self.assertFalse(doc['defenseVerified']);self.assertIsNone(doc['towerCode'])
  self.assertEqual(sum(len(t['units']) for t in doc['teams']),20)
  with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as tmp:
   database=Path(tmp)/'fixture.sqlite';db=sqlite3.connect(database);db.execute('CREATE TABLE guild_roster_sources(source_id TEXT,payload TEXT)')
   original=sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)
   row=original.execute('SELECT source_id,payload FROM guild_roster_sources WHERE source_id=?',(doc['rosterSourceId'],)).fetchone();original.close()
   db.execute('INSERT INTO guild_roster_sources VALUES (?,?)',row);db.commit();db.close()
   accept(SOURCE,database);accept(SOURCE,database)
   db=sqlite3.connect(database)
   self.assertEqual(db.execute('SELECT count(*) FROM guild_public_formation_sources').fetchone()[0],1)
   self.assertEqual(db.execute('SELECT count(*) FROM current_guild_public_formations').fetchone()[0],1)
   self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='current_guild_war_sources'").fetchone());db.close()

if __name__=='__main__':unittest.main()
