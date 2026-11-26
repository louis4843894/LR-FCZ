import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from export_equipment_website import export
SOURCE=ROOT/'data/research/equipment-runtime-loaded953.json'
@unittest.skipUnless(SOURCE.exists(),'requires verified local parsed snapshot')
class ExportTests(unittest.TestCase):
 def setUp(self):self.doc=json.loads(SOURCE.read_text(encoding='utf8'));self.doc['records']=self.doc['records'][:1]
 def run_export(self,doc):
  with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as directory:
   source=Path(directory)/'input.json';output=Path(directory)/'output.json';source.write_text(json.dumps(doc),encoding='utf8');export(source,output);return json.loads(output.read_text(encoding='utf8'))
 def test_whitelist_preserves_unknown_and_rejects_private_fields(self):
  self.doc['records'][0].update(objectAddress='private-value',rawMemory='private-value')
  result=self.run_export(self.doc);text=json.dumps(result)
  self.assertNotIn('private-value',text);self.assertNotIn('rawRecordSha256',text)
  self.assertIsNone(result['records'][0]['effects']);self.assertEqual(result['records'][0]['effectsStatus'],'unparsed')
 def test_conflicting_records_rejected_instead_of_first_wins(self):
  other=copy.deepcopy(self.doc['records'][0]);other['starCount']=8;self.doc['records'].append(other)
  with self.assertRaisesRegex(ValueError,'conflicting itemCode'):self.run_export(self.doc)
 def test_inconsistent_capture_rejected(self):
  self.doc['traversal']['consistentSnapshot']=False
  with self.assertRaisesRegex(ValueError,'inconsistent capture'):self.run_export(self.doc)
 def test_original_sample_without_traversal_is_supported(self):
  self.doc['traversal']=None;self.assertEqual(self.run_export(self.doc)['recordCount'],1)
