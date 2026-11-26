import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from merge_native_characters import merge
SOURCES=[ROOT/'data/research/rangers-runtime-five.json',ROOT/'data/research/rangers-defense-ten.json']
class CharacterMergeTests(unittest.TestCase):
    def test_two_real_captures_keep_fifteen_unique_templates(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
            result=merge(SOURCES,Path(folder)/'result.json')
            self.assertEqual(len({r['characterId'] for r in result['records']}),15);self.assertFalse(result['coverageComplete']);self.assertEqual(len(result['sourceCaptures']),2)
    def test_conflicting_id_does_not_replace_prior_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
            p=Path(folder);doc=json.loads(SOURCES[0].read_text(encoding='utf8'));altered=copy.deepcopy(doc);altered['records'][0]['unitCategory']='AGI'
            source=p/'conflict.json';source.write_text(json.dumps(altered));output=p/'result.json';output.write_text('previous-valid')
            with self.assertRaisesRegex(ValueError,'conflicting'):merge([SOURCES[0],source],output)
            self.assertEqual(output.read_text(),'previous-valid')
