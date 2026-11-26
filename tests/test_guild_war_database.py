import copy,json,sqlite3,sys,tempfile,unittest,shutil
from contextlib import closing
from datetime import datetime,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from guild_war_database import parse_directory,accept_directory,units_from_json,battle_number
SOURCE=ROOT/'data/research/runtime.private/guildwar-bootstrap-20261125T142824Z-e3cf3c'
TOWERS=ROOT/'data/research/runtime.private/guildwar-main-20261125T233439Z-71ffb8'

@unittest.skipUnless((SOURCE/'bootstrap.private.json').exists(),'saved reviewed response required')
class GuildWarTests(unittest.TestCase):
 def source(self):return json.loads((SOURCE/'bootstrap.private.json').read_bytes())
 def test_saved_configuration_is_not_deployed_and_has_actual_twenty_positions(self):
  docs=parse_directory(SOURCE);overview=[r for r in docs if r['kind']=='overview'];deck=next(r for r in docs if r['kind']=='saved_configuration')
  self.assertEqual([len(r['towers']) for r in overview],[10,10]);self.assertTrue(all(t['defenders'] is None for r in overview for t in r['towers']))
  self.assertEqual(deck['deploymentState'],'unconfirmed');units=deck['teams'][0]['units'];self.assertEqual([u['position'] for u in units],list(range(20)))
  raw=json.loads(self.source()['savedDeck']['deckInfoJson'])['playerUnitTeams']['1']
  for unit,source in zip(units,raw):
   for native,slot in [('WEAPON','weapon'),('ARMOR','armor'),('ACC','accessory')]:
    e=unit['equipment'][slot];self.assertEqual(e['enhancement'],source['equipMap'][native]['currentEnchant'])
    self.assertTrue(all(a['value'] is None for a in e['actualEffects']['entries']))
 def test_same_template_instances_are_kept_and_duplicate_instance_or_owner_is_rejected(self):
  raw=json.loads(self.source()['savedDeck']['deckInfoJson'])['playerUnitTeams']['1'];units=units_from_json(raw,1)
  gear=[e for u in units for e in u['equipment'].values() if e['state']=='equipped'];self.assertEqual(len(gear),60)
  self.assertLess(len({e['equipmentId'] for e in gear}),60);self.assertEqual(len({e['equipmentInstanceIdentity']['value'] for e in gear}),60)
  altered=copy.deepcopy(raw);altered[1]['equipMap']['WEAPON']['invenId']=altered[0]['equipMap']['WEAPON']['invenId']
  with self.assertRaisesRegex(ValueError,'owner/duplicate'):units_from_json(altered,1)
  altered=copy.deepcopy(raw);altered[0]['equipMap']['WEAPON']['unitInvenId']+=1
  with self.assertRaisesRegex(ValueError,'owner/duplicate'):units_from_json(altered,1)
 def test_unknown_equipment_map_and_empty_slot_remain_different(self):
  raw=json.loads(self.source()['savedDeck']['deckInfoJson'])['playerUnitTeams']['1'][:2]
  del raw[0]['equipMap'];del raw[1]['equipMap']['WEAPON']
  units=units_from_json(raw,1);self.assertEqual(units[0]['equipment']['weapon']['state'],'unknown');self.assertEqual(units[1]['equipment']['weapon']['state'],'not_equipped')
 def test_additive_idempotent_storage_preserves_instance_count(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
   database=Path(folder)/'fixture.sqlite';accept_directory(SOURCE,database);accept_directory(SOURCE,database)
   with closing(sqlite3.connect(database)) as db:
    self.assertEqual(db.execute('SELECT count(*) FROM guild_war_sources').fetchone()[0],3)
    self.assertEqual(db.execute('SELECT count(*) FROM guild_war_equipment_instances').fetchone()[0],60)
    self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
 def test_only_proven_statuses_make_request_battle_number(self):
  for status,value in [('first_battle',1),('first_standby',1),('second_battle',2),('third_battle',3),('register',None),('unknown',None)]:self.assertEqual(battle_number(status),value)
 @unittest.skipUnless((TOWERS/'main.private.json').exists(),'saved fortress responses required')
 def test_more_recent_history_read_cannot_replace_later_current_battle(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
   folder=Path(folder);database=folder/'fixture.sqlite';current=accept_directory(TOWERS,database)
   own=next(d for d in current if d['kind']=='overview');prior=self.source();prior['capturedAt']='2099-01-01T00:00:00+00:00'
   history=folder/'history';history.mkdir();(history/'bootstrap.private.json').write_text(json.dumps(prior),encoding='utf8')
   accept_directory(history,database)
   with closing(sqlite3.connect(database)) as db:
    source=db.execute("SELECT source_id FROM current_guild_war_sources WHERE guild_id=? AND kind='overview'",(own['guildId'],)).fetchone()[0]
    self.assertEqual(source,own['sourceId'])
 @unittest.skipUnless((TOWERS/'main.private.json').exists(),'saved fortress responses required')
 def test_real_tower_deployments_and_partial_refresh_preserve_complete(self):
  docs=parse_directory(TOWERS);deployed=next(d for d in docs if d['kind']=='deployed_defense')
  defenders=[d for t in deployed['towers'] for d in t['defenders']];units=[u for d in defenders for t in d['teams'] for u in t['units']]
  self.assertEqual((len(deployed['towers']),len(defenders),len(units)),(10,25,500));self.assertTrue(all(not d['isAI'] for d in defenders))
  self.assertEqual(sum(e['state']=='equipped' for u in units for e in u['equipment'].values()),1499)
  self.assertEqual(sum(e['state']=='not_equipped' for u in units for e in u['equipment'].values()),1)
  with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
   folder=Path(folder);database=folder/'fixture.sqlite';accept_directory(TOWERS,database)
   partial=folder/'partial';partial.mkdir()
   for name in ('main.private.json','tower-ally-11.private.json'):shutil.copyfile(TOWERS/name,partial/name)
   source=partial/'tower-ally-11.private.json';newer=json.loads(source.read_bytes());newer['capturedAt']=(datetime.fromisoformat(deployed['capturedAt'])+timedelta(minutes=1)).isoformat();source.write_text(json.dumps(newer),encoding='utf8')
   result=accept_directory(partial,database);latest=next(d for d in result if d['kind']=='deployed_defense');self.assertEqual(latest['status'],'partial')
   with closing(sqlite3.connect(database)) as db:
    current=db.execute("SELECT source_id FROM current_guild_war_sources WHERE kind='deployed_defense'").fetchone()[0]
    self.assertEqual(current,deployed['sourceId']);self.assertEqual(db.execute('SELECT count(*) FROM guild_war_sources WHERE status=\'partial\'').fetchone()[0],1)

if __name__=='__main__':unittest.main()
