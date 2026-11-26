"""Only isolated fixtures; never imported as real character records."""
import copy,hashlib,json,sqlite3,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import closing
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_character_details as module
from sync_character_details_supabase import public_details


class CharacterDetails(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='lr-character-details-fixture-');self.root=Path(self.tmp.name)
  self.assertEqual(self.root.resolve().parent,Path(tempfile.gettempdir()).resolve());self.addCleanup(self.tmp.cleanup)
  self.folder=self.root/'reference';self.folder.mkdir();self.native=self.root/'native.json';self.lang=self.root/'lang.sqlite'
  self.effect={'effectCode':'fixture','magnitude':{'kind':'statPercent','stat':'ATK','operator':'MULTIPLY','percent':4500},'duration':{'kind':'fixed','seconds':4},'rangePoints':350,'availableIn':{'events':False,'guardian':True},'effectTrigger':{'kind':'chance','percent':100},'targetLimit':{'kind':'limited','maxTargets':5}}
  self.skill={'skillCode':'sk_fixture','nameKey':'SKILL:sk_fixture_nm','descriptionKey':'SKILL:sk_fixture_desc','activationRate':30,'cooldownSeconds':12,'trigger':{'type':'SELF'},'effects':[self.effect]}
  self.ranger={'rangerCode':'fixture','starGrade':9,'roleType':'STR','elementType':'NONE','skillSet':[self.skill],'abilityCodes':['ab_fixture'],'awakeningAbilities':[{'abilityCode':'ab_fixture','chancePercent':10}],'talents':None,'stats':{'hp':100},'evolution':'NORMAL','releaseDate':'2026-01-01'}
  self.base={'characterId':'fixture','starCount':9,'unitCategory':'STR','unitElement':'none','primarySkillCode':'sk_fixture','primaryAbilityCode':'ab_fixture'}
  self.ability={'abilityCode':'ab_fixture','nameKey':'ABILITY:ab_fixture_nm','descriptionKey':'ABILITY:ab_fixture_desc','triggerEffects':[]}
  self.catalog=[{'key':key,'zh_TW':text} for key,text in [('SKILL:sk_fixture_nm','測試技能'),('SKILL:sk_fixture_desc','測試敘述'),('ABILITY:ab_fixture_nm','測試能力'),('ABILITY:ab_fixture_desc','能力敘述'),('CUSTOM:fixture','測試效果')]]
  with closing(sqlite3.connect(self.lang)) as db:
   db.execute('CREATE TABLE lang_unit(dataCode TEXT,language TEXT,msg TEXT)');db.executemany('INSERT INTO lang_unit VALUES (?,?,?)',[(r['key'].split(':')[1],'zh-Hant',r['zh_TW']) for r in self.catalog if not r['key'].startswith('CUSTOM:')])
   db.commit()
 def build(self,reference=None,native=None):
  files={'rangers.json':{'schemaVersion':2,'rangers':reference if reference is not None else [self.ranger]},'abilities.json':{'schemaVersion':2,'abilities':[self.ability]},'official-locales.json':self.catalog,'custom-locales.json':[]};manifest=[]
  for name,data in files.items():
   raw=json.dumps(data).encode();(self.folder/name).write_bytes(raw);manifest.append({'file':name,'sha256':hashlib.sha256(raw).hexdigest()})
  (self.folder/'datasets-source.json').write_text(json.dumps({'sourceKind':'external-user-confirmed','localVerification':False,'retrievedAt':'2026-11-26T00:00:00Z','files':manifest}))
  self.native.write_text(json.dumps({'sourceKind':'verified-character-template','localVerification':True,'records':native if native is not None else [self.base],'gameVersion':'fixture'}))
  with patch.object(module,'ROOT',self.root):return module.build(self.folder,self.native,self.lang)
 def test_effect_units_local_text_and_candidates_remain_separate(self):
  d=self.build();r=d['records'][0];e=r['skills'][0]['effects'][0]
  self.assertEqual(e['magnitudeText'],'攻擊力的 4500%');self.assertEqual(e['durationText'],'4 秒');self.assertFalse(e['availableEvents']);self.assertTrue(e['availableGuardian'])
  self.assertEqual(r['skills'][0]['textSource'],'local-translation');self.assertEqual(r['awakeningAbilities'][0]['candidateProbabilityRaw'],10);self.assertEqual(r['awakeningAbilities'][0]['probabilityMeaning'],'unverified')
  self.assertFalse(d['localNumericVerification']);self.assertTrue(d['templateOnly'])
 def test_missing_reference_is_unknown_while_explicit_empty_list_is_retained(self):
  material={**self.base,'characterId':'material','primarySkillCode':None,'primaryAbilityCode':None};reference={**self.ranger,'rangerCode':'material','skillSet':[],'abilityCodes':[],'awakeningAbilities':[]}
  d=self.build([reference],[self.base,material]);self.assertIsNone(d['records'][0]['skills']);self.assertEqual(d['records'][1]['skills'],[])
  self.assertIsNone(d['index']['fixture']['skillCount']);self.assertEqual(d['index']['material']['skillCount'],0)
 def test_mismatched_skill_id_or_star_never_borrows_another_template(self):
  for changed in [{'starGrade':8},{'skillSet':[{**self.skill,'skillCode':'other'}]}]:
   d=self.build([{**self.ranger,**changed}]);self.assertEqual(d['records'][0]['status'],'identity_conflict');self.assertIsNone(d['records'][0]['skills'])
 def test_description_conflict_withholds_reference_numbers(self):
  self.catalog[1]['zh_TW']='不同版本';d=self.build();s=d['records'][0]['skills'][0]
  self.assertEqual(s['description'],'測試敘述');self.assertEqual(s['status'],'description_conflict');self.assertIsNone(s['activationRatePercent']);self.assertEqual(s['effects'],[])
 def test_level_formulas_and_null_effects_are_not_evaluated_with_guessed_player_level(self):
  self.assertEqual(module.magnitude({'kind':'levelFormula','levelSource':'LEVEL','operator':'MULTIPLY','amount':70,'unit':'FLAT'}),'角色等級 × 70')
  self.assertIsNone(module.magnitude(None));self.assertIsNone(module.magnitude({'kind':'unsupported'}))
  with self.assertRaises(ValueError):module.numeric(float('nan'))
 def test_duplicate_character_ids_rejected(self):
  with self.assertRaises(ValueError):self.build([self.ranger,copy.deepcopy(self.ranger)])
 def test_explicit_absence_is_preserved_with_its_actual_source_fields(self):
  row={**self.ranger,'skillSet':[],'abilityCodes':[],'awakeningAbilities':[],'talents':None};native={**self.base,'primarySkillCode':None,'primaryAbilityCode':None}
  d=self.build([row],[native]);r=d['records'][0]
  self.assertEqual(r['availability'],dict.fromkeys(['skills','abilities','awakening','talents'],'absent'))
  self.assertEqual(public_details(r)['availability'],r['availability']);self.assertEqual(d['summary']['skills_absent'],1)
 def test_missing_optional_properties_do_not_become_absence(self):
  row=copy.deepcopy(self.ranger);row.pop('awakeningAbilities');row.pop('talents')
  r=self.build([row])['records'][0]
  self.assertEqual(r['availability']['awakening'],'unknown');self.assertEqual(r['availability']['talents'],'unknown');self.assertIsNone(r['awakeningAbilities'])
  self.assertEqual(self.build([])['records'][0]['availability'],dict.fromkeys(['skills','abilities','awakening','talents'],'unknown'))
 def test_cloud_output_drops_unverified_candidate_chance_and_unknown_stats_fields(self):
  d=self.build();row=d['records'][0];row['stats']['rawMemory']='private-sentinel';public=public_details(row);serialized=json.dumps(public)
  self.assertNotIn('candidateProbabilityRaw',serialized);self.assertNotIn('probabilityMeaning',serialized);self.assertNotIn('private-sentinel',serialized)
  self.assertTrue(public['awakeningCandidatesAreNotPlayerAwakening']);self.assertFalse(public['localNumericVerification'])


if __name__=='__main__':unittest.main()
