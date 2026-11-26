import copy,sys,unittest,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from derive_guildwar_gear_values import observation_id,matching_value,observations
from derive_http_gear_values import instance_hash
from sync_guild_rankings_supabase import public_war_record
from native_gear_special_values import conditional_scalar,skill_scalar

class GuildWarRollTests(unittest.TestCase):
 def test_special_export_is_bound_and_never_exports_raw_parameters(self):
  doc,owner,t,g,e,r=self.sample();key=observation_id(doc,11,owner,t,t['units'][0],'armor')
  r['supplementarySpecial']={'state':'values_reconstructed','name':'光之盔甲','normalText':'降低傷害 +23.9%','description':'反射26.7%的物理傷害',
    'specialEnhancement':5,'enhancementIncluded':True,'valueVerified':True,'activationState':'not_verified','rawFields':{'secret':'fixture-private'},'descriptionParameters':{'0':.5}}
  public=public_war_record(doc,{key:r});extra=public['towers'][0]['defenders'][0]['teams'][0]['units'][0]['equipment']['armor']['supplementarySpecial']
  self.assertEqual(extra['name'],'光之盔甲');self.assertTrue(extra['numericalValuesVerified']);self.assertFalse(extra['valueVisuallyVerified'])
  self.assertNotIn('rawFields',str(public));self.assertNotIn('descriptionParameters',str(public));self.assertNotIn('fixture-private',str(public))
  r['sourceObservationSha256']='other-copy';public=public_war_record(doc,{key:r})
  self.assertNotIn('supplementarySpecial',public['towers'][0]['defenders'][0]['teams'][0]['units'][0]['equipment']['armor'])
 def test_skillplus_uses_its_own_id_grade_and_separate_upgrade_level(self):
  definition={'attributeId':200032,'groupId':200030,'minValue':1.0,'maxValue':2.0,'steps':10,'use':True,'applyTypeEnum':3,'targetFactorEnum':0}
  upgrades={'200032_1':{'value':.6},'200030_1':{'value':10.0}}
  self.assertEqual(skill_scalar(definition,9,1,upgrades)['value'],260)
  self.assertEqual(skill_scalar(definition,0,0,upgrades)['value'],100)
  self.assertEqual(skill_scalar({**definition,'applyTypeEnum':4},9,0,upgrades)['value'],-2)
  self.assertEqual(skill_scalar({**definition,'targetFactorEnum':1,'applyTypeEnum':1},9,0,upgrades)['unit'],'SECOND')
  self.assertIsNone(skill_scalar(definition,10,1,upgrades));self.assertIsNone(skill_scalar(definition,9,None,upgrades))
 def test_conditional_branch_uses_advanced_enchantment_addition_instead_of_ordinary_multiplier(self):
  raw=bytearray(0x78);struct.pack_into('<IIIIff',raw,0x18,110006,10,0,10,1.05,1.5)
  definition={'selector1':'none','selector2':'STR'};increments={f'STRFIXTURE{i}':{'selector':'STR','code':'FIXTURE','level':i,'value':.04} for i in range(1,6)}
  self.assertEqual(conditional_scalar(raw,definition,9,5,{10:'FIXTURE'},increments)['value'],170)
  self.assertEqual(conditional_scalar(raw,definition,9,0,{10:'FIXTURE'},increments)['value'],150)
  self.assertIsNone(conditional_scalar(raw,definition,10,5,{10:'FIXTURE'},increments))
  self.assertIsNone(conditional_scalar(raw,definition,9,None,{10:'FIXTURE'},increments))
 def sample(self):
  owner='fixture-private-owner';entry={'index':0,'attributeId':40001,'valueGradeRaw':1,'sourceField':'attr1No','value':None}
  gear={'state':'equipped','equipmentId':'eq_fixture','enhancement':5,'instanceGrade':9,'ownerAssociationStatus':'verified-native',
   'equipmentInstanceIdentity':{'namespace':'player-owned-equipment','value':'fixture-private-instance'},'actualEffects':{'status':'identifiers_only','entries':[entry]}}
  team={'teamNo':1,'units':[{'position':19,'characterId':'fixture-unit','characterInstanceId':'fixture-private-unit','level':180,'equipment':{'armor':gear}}]}
  doc={'sourceKind':'verified-guildwar-tower-deployments','kind':'deployed_defense','sourceId':'fixture-source','guildId':'fixture-private-guild',
   'parserVersion':'fixture','seasonNo':1,'battleNo':2,'seasonStatus':'second_battle','capturedAt':'2026-11-26T00:00:00Z','gameVersion':'12.4.2','status':'partial','sourceSha256':'fixture-copy-sha',
   'towers':[{'code':11,'readState':'success','defenders':[{'playerId':owner,'playerName':'fixture','retrievedAt':'2026-11-26T00:00:00Z','isAI':False,'withdrawal':False,'teams':[team]}]},
    {'code':12,'readState':'not_read','defenders':None},{'code':13,'readState':'success','defenders':[]}]}
  result={**entry,'value':-30,'unit':'PERCENT','enhancementIncluded':True,'valueVerified':True,'valueVisuallyVerified':False}
  record={'equipmentId':'eq_fixture','enhancement':5,'instanceGrade':9,'equipmentInstanceHash':instance_hash(owner,gear['equipmentInstanceIdentity']),
   'entries':[result],'sourceObservationSha256':'fixture-copy-sha','factorCapturedAt':'2026-11-26T04:00:00Z'}
  return doc,owner,team,gear,entry,record
 def test_twenty_positions_towers_sources_owners_and_team_namespaces_are_separate(self):
  doc,owner,t,g,e,r=self.sample();u=t['units'][0];key=observation_id(doc,11,owner,t,u,'armor')
  self.assertNotEqual(key,observation_id(doc,None,owner,t,u,'armor'))
  self.assertNotEqual(key,observation_id(doc,12,owner,t,u,'armor'))
  self.assertNotEqual(key,observation_id({**doc,'sourceId':'later'},11,owner,t,u,'armor'))
  self.assertNotEqual(key,observation_id(doc,11,'other',t,u,'armor'))
  self.assertNotEqual(key,observation_id(doc,11,owner,{**t,'teamNo':2},u,'armor'))
  self.assertEqual(len(list(observations(doc))),1) # unread and confirmed empty differ
 def test_matching_does_not_reuse_other_owner_instance_grade_or_skill_namespace(self):
  _,owner,_,g,e,r=self.sample();self.assertEqual(matching_value(r,owner,g,e)['value'],-30)
  for changed in [{'enhancement':4},{'instanceGrade':8},{'ownerAssociationStatus':'unknown'},
                  {'equipmentInstanceIdentity':{'namespace':'player-owned-equipment','value':'other'}}]:
   self.assertIsNone(matching_value(r,owner,{**g,**changed},e))
  self.assertIsNone(matching_value(r,'other',g,e))
  self.assertIsNone(matching_value(r,owner,g,{**e,'valueGradeRaw':2}))
  self.assertIsNone(matching_value(r,owner,g,{**e,'sourceField':'skillPlusAttr1No'}))
 def test_skillplus_export_keeps_its_namespace_units_and_chinese_template(self):
  doc,owner,t,g,e,r=self.sample();e['sourceField']='skillPlusAttr1No';r['entries'][0].update(sourceField='skillPlusAttr1No',calculationKind='native-skillplus',unit='SECOND',value=1.5,labelTemplate='持續 N 秒',modifierOperator='+')
  self.assertEqual(matching_value(r,owner,g,e)['value'],1.5)
  key=observation_id(doc,11,owner,t,t['units'][0],'armor');public=public_war_record(doc,{key:r})
  item=public['towers'][0]['defenders'][0]['teams'][0]['units'][0]['equipment']['armor']['actualEffects']['entries'][0]
  self.assertEqual(item['labelTemplate'],'持續 N 秒');self.assertEqual(item['unit'],'SECOND')
  self.assertFalse(item['valueVisuallyVerified']);self.assertIsNone(matching_value(r,owner,g,{**e,'sourceField':'attr1No'}))
 def test_cloud_export_keeps_unknowns_partial_towers_and_never_changes_original(self):
  doc,owner,t,g,e,r=self.sample();before=copy.deepcopy(doc);key=observation_id(doc,11,owner,t,t['units'][0],'armor')
  public=public_war_record(doc,{key:r});gear=public['towers'][0]['defenders'][0]['teams'][0]['units'][0]['equipment']['armor']
  self.assertEqual(gear['actualEffects']['entries'][0]['value'],-30);self.assertFalse(gear['actualEffects']['entries'][0]['valueVisuallyVerified'])
  self.assertIsNone(public['towers'][1]['defenders']);self.assertEqual(public['towers'][2]['defenders'],[])
  self.assertEqual(doc,before);self.assertNotIn('fixture-private',str(public))
  r['sourceObservationSha256']='wrong-copy';public=public_war_record(doc,{key:r})
  self.assertIsNone(public['towers'][0]['defenders'][0]['teams'][0]['units'][0]['equipment']['armor']['actualEffects']['entries'][0]['value'])

if __name__=='__main__':unittest.main()
