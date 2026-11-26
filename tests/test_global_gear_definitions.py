import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'scripts/runtime')]
from parse_gear_definitions import parse
CAP=ROOT/'data/research/runtime.private/gear-definitions-20261126T042612Z-04ee0f'
@unittest.skipUnless((CAP/'capture.json').exists(),'requires actual private definition copies')
class GlobalGearDefinitionTests(unittest.TestCase):
 def sample(self,folder):
  meta=json.loads((CAP/'capture.json').read_bytes());meta['records']=meta['records'][:1];meta['traversal'].update(visitedNodes=1,maxNodes=1,stopReason='node_limit',loadedContainerEnded=False)
  for row in meta['records']:(folder/row['file']).write_bytes((CAP/row['file']).read_bytes())
  (folder/'capture.json').write_text(json.dumps(meta),encoding='utf8');return meta
 def test_a_valid_partial_container_is_not_claimed_complete_and_is_not_a_player_roll(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as path:
   folder=Path(path);self.sample(folder);doc=parse(folder)
   self.assertEqual(len(doc['records']),1);self.assertFalse(doc['loadedContainerEnded']);self.assertFalse(doc['wholeGameComplete']);self.assertFalse(doc['numericRollsDerived'])
 def test_tampered_bytes_and_inconsistent_traversal_are_rejected(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as path:
   folder=Path(path);meta=self.sample(folder);raw=folder/meta['records'][0]['file'];raw.write_bytes(b'0'*0x78)
   with self.assertRaisesRegex(ValueError,'hash/type/boundary'):parse(folder)
   meta=self.sample(folder);meta['traversal']['visitedNodes']=2;(folder/'capture.json').write_text(json.dumps(meta),encoding='utf8')
   with self.assertRaisesRegex(ValueError,'traversal coverage'):parse(folder)
if __name__=='__main__':unittest.main()
