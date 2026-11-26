"""Regression against five actual native copies; these are GUARDIAN, not RANGERS."""
import copy,hashlib,json,shutil,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from parse_runtime_characters import parse_capture
from export_characters_website import export
CAPTURE=ROOT/'data/research/runtime.private/character-capture-20261118T171553Z-7ab268'
LOCALIZATION=ROOT/'data/research/runtime.private/character-team-session/lang_unit.ndb'
@unittest.skipUnless((CAPTURE/'capture.json').exists() and LOCALIZATION.exists(),'requires actual saved native unit copies and local translation')
class NativeCharactersTests(unittest.TestCase):
    def test_actual_ordinary_rangers_and_native_website_export(self):
        capture=ROOT/'data/research/runtime.private/character-capture-20261118T175648Z-641e5a'
        d=parse_capture(capture,LOCALIZATION)
        self.assertEqual([r['characterId'] for r in d['records']],['u001e-bella','u002e-bella','u009e-clara','u022e-sindy','u023e-sindy'])
        self.assertEqual({r['unitCategory'] for r in d['records']},{'STR','AGI','INT'})
        self.assertTrue(all(r['unitIdentity']=='RANGERS' and r['starCount'] is None for r in d['records']))
        self.assertEqual(d['records'][-1]['primarySkillCode'],'usk004_sindy1')
        self.assertTrue(all(r['skills'] is None for r in d['records']))
    def test_old_copy_cannot_be_read_using_new_version_layout(self):
        with tempfile.TemporaryDirectory(dir=CAPTURE.parent) as directory:
            p=Path(directory)
            for file in CAPTURE.iterdir():
                if file.is_file():shutil.copyfile(file,p/file.name)
            meta=json.loads((p/'capture.json').read_text());meta['moduleSha256']='1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0';(p/'capture.json').write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,'record type mismatch'):parse_capture(p)
    def test_actual_unit_fields_and_names_are_independently_checked(self):
        d=parse_capture(CAPTURE,LOCALIZATION);self.assertEqual(len(d['records']),5)
        self.assertEqual([r['gradeRaw'] for r in d['records']],[1,2,3,1,2])
        self.assertEqual([r['name'] for r in d['records']],['索妮亞','索妮亞','索妮亞','威爾森','威爾森'])
        self.assertEqual(d['records'][0]['unitType'],'ATTACK');self.assertEqual(d['records'][0]['unitCategory'],'AGI')
        self.assertEqual(d['records'][3]['unitCategory'],'INT');self.assertEqual(d['records'][3]['unitElement'],'water')
    def test_guardians_are_not_rangers_and_grade_is_not_promoted_to_stars(self):
        d=parse_capture(CAPTURE,LOCALIZATION)
        self.assertTrue(all(r['unitIdentity']=='GUARDIAN' and r['recordScope']=='unit-definition' and r['starCount'] is None for r in d['records']))
        self.assertFalse(d['coverageComplete'])
    def test_unknown_names_and_skills_remain_unknown_without_local_translation(self):
        d=parse_capture(CAPTURE)
        self.assertTrue(all(r['name'] is None and r['skills'] is None and r['imageMapping'] is None for r in d['records']))
    def test_modified_capture_hash_rejected(self):
        with tempfile.TemporaryDirectory(dir=CAPTURE.parent) as directory:
            p=Path(directory)
            for file in CAPTURE.iterdir():
                if file.is_file():shutil.copyfile(file,p/file.name)
            meta=json.loads((p/'capture.json').read_text(encoding='utf8'));file=p/meta['records'][0]['files']['record']['file'];raw=bytearray(file.read_bytes());raw[0x6fc]^=1;file.write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'hash mismatch'):parse_capture(p,LOCALIZATION)
    def test_empty_or_guardian_source_does_not_replace_website_characters(self):
        with tempfile.TemporaryDirectory(dir=CAPTURE.parent) as directory:
            p=Path(directory);source=p/'units.json';output=p/'website.json';output.write_text('previous-valid-data',encoding='utf8')
            source.write_text(json.dumps(parse_capture(CAPTURE,LOCALIZATION)),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'no verified RANGERS'):export(source,output)
            self.assertEqual(output.read_text(encoding='utf8'),'previous-valid-data')
