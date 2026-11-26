"""Regression checks against actual private equipment captures, never invented records."""
import base64,copy,json,shutil,struct,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from parse_runtime_equipment import decode_grade,parse_capture
CAPTURE=ROOT/'data/research/runtime.private/objects'
@unittest.skipUnless((CAPTURE/'capture.json').exists(),'requires a real local equipment capture')
class RuntimeEquipmentTests(unittest.TestCase):
 def setUp(self):
  self.meta=json.loads((CAPTURE/'capture.json').read_text(encoding='utf8'))
  r=self.meta['records'][0];self.wrapper=(CAPTURE/r['gradeFile']).read_bytes();self.encoded=(CAPTURE/r['gradeCipherFile']).read_bytes()
 def test_real_target_and_independent_seven_grade(self):
  records={r['itemCode']:r for r in parse_capture(CAPTURE)['records']}
  self.assertEqual(records['eq_2202_amr_06']['equipGrade'],6)
  self.assertEqual(records['eq_2202_amr_06']['equipType'],'ARMOR')
  self.assertEqual(records['eq_2202_amr_06']['starCount'],6)
  self.assertEqual(records['eq_2202_wpn_17']['starCount'],7)
  self.assertEqual(records['eq_2202_wpn_17']['equipGrade'],7)
  self.assertTrue(all(r['validation']['gradeChecksumVerified'] for r in records.values()))
 def test_bad_checksum_is_rejected_instead_of_native_fallback(self):
  w=bytearray(self.wrapper);w[0x2c]^=1
  with self.assertRaisesRegex(ValueError,'checksum'):decode_grade(bytes(w),self.encoded)
 def test_invalid_encoding_and_partial_integer_rejected(self):
  for encoded in (b'!',base64.b64encode(b'12junk')):
   with self.subTest(encoded=encoded),self.assertRaises(ValueError):decode_grade(self.wrapper,encoded)
 def test_dictionary_identity_mismatch_rejected(self):
  with tempfile.TemporaryDirectory(dir=CAPTURE.parent) as directory:
   p=Path(directory)
   for f in CAPTURE.iterdir():
    if f.is_file():shutil.copyfile(f,p/f.name)
   m=json.loads((p/'capture.json').read_text(encoding='utf8'));m['records'][0]['key']='different-identity'
   (p/'capture.json').write_text(json.dumps(m),encoding='utf8')
   with self.assertRaisesRegex(ValueError,'key differs'):parse_capture(p)

 def test_duplicate_same_id_deduplicates_without_losing_source_count(self):
  with tempfile.TemporaryDirectory(dir=CAPTURE.parent) as directory:
   p=Path(directory)
   for f in CAPTURE.iterdir():
    if f.is_file():shutil.copyfile(f,p/f.name)
   meta=copy.deepcopy(self.meta);meta['records'].append(copy.deepcopy(meta['records'][0]))
   (p/'capture.json').write_text(json.dumps(meta),encoding='utf8')
   result=parse_capture(p)
   self.assertEqual(result['recordParsing']['capturedRecordCount'],6)
   self.assertEqual(len(result['records']),5)
   self.assertEqual(result['recordParsing']['duplicates'],[meta['records'][0]['key']])

 def test_conflicting_same_id_is_excluded_and_strict_mode_rejects(self):
  with tempfile.TemporaryDirectory(dir=CAPTURE.parent) as directory:
   p=Path(directory)
   for f in CAPTURE.iterdir():
    if f.is_file():shutil.copyfile(f,p/f.name)
   meta=copy.deepcopy(self.meta);entry=copy.deepcopy(meta['records'][0])
   raw=bytearray((p/entry['rawFile']).read_bytes());struct.pack_into('<I',raw,0x74,6)
   entry['rawFile']='fault-injected-conflict.bin';(p/entry['rawFile']).write_bytes(raw)
   meta['records'].append(entry);(p/'capture.json').write_text(json.dumps(meta),encoding='utf8')
   with self.assertRaisesRegex(ValueError,'conflicting itemCode'):parse_capture(p)
   result=parse_capture(p,strict=False)
   self.assertNotIn(entry['key'],[r['itemCode'] for r in result['records']])
   self.assertEqual(result['recordParsing']['conflicts'],[entry['key']])
   self.assertEqual(len(result['records']),4)
if __name__=='__main__':unittest.main()

