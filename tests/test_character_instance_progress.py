import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from character_instance_progress import parse_progress,observation_key,instance_hash,match_progress
from character_skill_startup import startup_for


class InstanceProgressTests(unittest.TestCase):
 def test_actual_fields_and_zero_are_not_template_maxima(self):
  raw={'unitLevel':180,'maxLevel':160,'playerUnitMaxLevel':180,'leonardPoint':0,'maxLeonardPoint':100,'talentGrade':0,'maxTalentGrade':4}
  p=parse_progress(raw,{})
  self.assertEqual([p['level'],p['maxLevel'],p['leonardPoints'],p['talentGrade']],[180,180,0,0])
  missing=parse_progress({'maxLevel':240,'maxLeonardPoint':100,'maxTalentGrade':4},{})
  self.assertTrue(all(missing[k] is None for k in ['level','maxLevel','leonardPoints','talentGrade']))

 def test_actual_awakening_is_not_a_candidate_or_flag(self):
  labels={'aab223_guts5_nm':'毅力+','aab223_guts5_desc':'實際能力敘述'}
  p=parse_progress({'awakeAbilityCode':'aab223_guts5'},labels)
  self.assertEqual(p['awakening']['name'],'毅力+')
  self.assertEqual(parse_progress({'awakeYn':True,'abilityCode':'aab223_guts5'},labels)['awakening']['state'],'not_returned')
  self.assertEqual(parse_progress({'awakeAbilityCode':''},labels)['awakening']['state'],'empty_observed')
  self.assertIsNone(parse_progress({'awakeAbilityCode':'unknown_actual'},labels)['awakening']['name'])

 def test_identity_owner_template_and_time_are_bound(self):
  p=parse_progress({'unitLevel':100},{})|{'characterId':'u1','instanceHash':instance_hash('owner-a','10'),'retrievedAt':'2026-11-26T00:00:00Z','sourceFile':'private','secret':'never-export'}
  good=match_progress(p,'u1','owner-a','10',p['retrievedAt']);self.assertEqual(good['level'],100)
  self.assertNotIn('instanceHash',good);self.assertNotIn('secret',good);self.assertNotIn('sourceFile',good)
  for args in [('u2','owner-a','10',p['retrievedAt']),('u1','owner-b','10',p['retrievedAt']),('u1','owner-a','11',p['retrievedAt']),('u1','owner-a','10','changed')]:self.assertIsNone(match_progress(p,*args))
  self.assertNotEqual(observation_key('pvp','s','owner-a',1,0),observation_key('pvp','s','owner-b',1,0))
  self.assertNotEqual(observation_key('guildwar','s','owner-a',1,0,11),observation_key('guildwar','s','owner-a',1,0,12))

 def test_invalid_numeric_types_do_not_become_values(self):
  for key,value in [('unitLevel',True),('leonardPoint',-1),('talentGrade',2.5),('unitLevel',0)]:
   with self.assertRaises(ValueError):parse_progress({key:value},{})

 def test_startup_seconds_zero_missing_and_segment_semantics(self):
  v={'frames':0,'seconds':0.0,'meaning':'segment_duration','projectile_spawn_time':False,'segment':'s_attack_ready'}
  units={'u1':{'unit_id':'u1','startup':{'skill_1':v}}}
  self.assertEqual(startup_for(units,'u1',0)['seconds'],0)
  v.update(segment='s_action_attack_1',seconds=0.6,frames=18)
  self.assertEqual(startup_for(units,'u1',0)['seconds'],0.6)
  self.assertIsNone(startup_for(units,'u1',1));self.assertIsNone(startup_for(units,'u1',2))
  v['meaning']='projectile_hit';self.assertIsNone(startup_for(units,'u1',0))


if __name__=='__main__':unittest.main()
