"""New 12.4.2 templates and corrected behavior: real-source regressions."""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from native_elf import NativeELF
from native_layouts import NEW_SHA
from parse_runtime_characters import verified_star_count
SOURCE=ROOT/'data/research/rangers-native-2405.json'
@unittest.skipUnless(SOURCE.exists(),'requires actual expanded source')
class ExpandedCharactersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=json.loads(SOURCE.read_text(encoding='utf8'))
    def test_native_fields_and_unknown_coverage(self):
        rows=self.data['records'];self.assertEqual(len(rows),2405);self.assertEqual(len({r['characterId'] for r in rows}),2405)
        self.assertEqual(sum(r['name'] is not None for r in rows),2385)
        self.assertEqual(sum(r['primarySkillCode'] is not None for r in rows),1903)
        self.assertEqual(sum(r['primaryAbilityCode'] is not None for r in rows),1750)
        self.assertTrue(all(r['starCount']==r['gradeRaw'] and 1<=r['starCount']<=9 for r in rows))
        self.assertTrue(all(r['fieldStatus']['starCount']=='verified-native-ui-relation' for r in rows))
        self.assertTrue(all(r['skills'] is None and r['imageMapping'] is None for r in rows))
        self.assertTrue(all(r['unitIdentity']=='RANGERS' and r['recordScope']=='character-template' for r in rows))
        self.assertTrue(self.data['loadedContainerTraversalEnded']);self.assertFalse(self.data['coverageComplete'])
    def test_existing_fifteen_semantics_are_preserved(self):
        old=json.loads((ROOT/'data/research/rangers-native-fifteen.json').read_text(encoding='utf8'))
        current={r['characterId']:r for r in self.data['records']}
        for row in old['records']:
            for key in ['name','unitCategory','unitType','unitElement','primarySkillCode']:self.assertEqual(row[key],current[row['characterId']][key],(row['characterId'],key))
    def test_corrected_behavior_is_never_flight(self):
        self.assertNotIn('FLIGHT',{r['unitType'] for r in self.data['records']})
        self.assertEqual(sum(r['unitType']=='ATTACK' for r in self.data['records']),321)
        self.assertEqual(sum(r['unitType']=='SPLASH' for r in self.data['records']),1131)
    def test_current_module_rtti_distinguishes_excluded_source(self):
        e=NativeELF(ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so')
        self.assertEqual(e.sha256,NEW_SHA);self.assertEqual(e.type_name(0x1e4f790),'21ProhibitedWordManager')
        self.assertEqual(e.type_name(0x1eadb48),'14GuildInfoModel');self.assertEqual(e.type_name(0x1f6a7f8),'N7cocos2d7CCArrayE')
    def test_star_evidence_is_limited_to_exact_module_kind_and_range(self):
        for grade in range(1,10):self.assertEqual(verified_star_count(grade,'RANGERS',NEW_SHA),grade)
        for grade in [0,10,-1,True,8.0,'8',None]:self.assertIsNone(verified_star_count(grade,'RANGERS',NEW_SHA))
        self.assertIsNone(verified_star_count(8,'GUARDIAN',NEW_SHA))
        self.assertIsNone(verified_star_count(8,'RANGERS','unverified-module'))
    def test_star_builder_cast_and_getter_match_captured_unit_type(self):
        e=NativeELF(ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so')
        self.assertEqual(e.ptr(0x1fb98f0),e.ptr(0x1e35410-8))
        self.assertEqual(e.ptr(0x1e35410+0xb0),0xc147cc)
        self.assertEqual(e.type_name(0x1e35410),'8UnitData')
