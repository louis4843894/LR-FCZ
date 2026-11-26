"""Traversal fault tests use copies of genuine captures, without contacting ADB."""
import json,struct,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts/runtime'))
from bounded_equipment_reader import Reader
CAP=ROOT/'data/research/runtime.private/objects'
@unittest.skipUnless((CAP/'capture.json').exists(),'requires real local baseline')
class BoundedTraversalTests(unittest.TestCase):
 def fake(self,next_kind='null',wrong_vtable=False,changed=False):
  meta=json.loads((CAP/'capture.json').read_text(encoding='utf8'));item=meta['records'][0];node=item['entryAddress'];record=bytearray((CAP/item['rawFile']).read_bytes());entry=bytearray((CAP/item['rawFile'].replace('record-','entry-')).read_bytes())
  nxt={'null':0,'cycle':node,'invalid':0x123}[next_kind];struct.pack_into('<Q',entry,0x120,nxt)
  if wrong_vtable:record[0]^=1
  g=(CAP/item['gradeFile']).read_bytes();st=(CAP/item['gradeStringFile']).read_bytes();global_address=meta['moduleBase']+0x1ed5270
  regions={global_address:struct.pack('<Q',meta['managerAddress']),meta['managerAddress']:(CAP/'manager.bin').read_bytes(),meta['dictionaryAddress']:(CAP/'dictionary.bin').read_bytes(),node:bytes(entry),item['objectAddress']:bytes(record),struct.unpack_from('<Q',record,0x50)[0]:g,struct.unpack_from('<Q',g,0x20)[0]:st}
  r=Reader.__new__(Reader);r.pid=meta['pid'];r.base=meta['moduleBase'];r.read_count=0;r.read_bytes=0
  def read(address,count):
   r.read_count+=1;r.read_bytes+=count
   if changed and address==meta['dictionaryAddress']+0x18:return struct.pack('<Q',node+8)
   for start,blob in regions.items():
    if start<=address and address+count<=start+len(blob):return blob[address-start:address-start+count]
   raise ValueError('invalid pointer')
  r.read=read
  return r
 def capture(self,reader,limit=10):
  with tempfile.TemporaryDirectory(dir=CAP.parent) as directory:return reader.capture(limit,Path(directory)/'run')
 def test_cycle_stops_and_is_not_full_coverage(self):
  result=self.capture(self.fake('cycle'));self.assertEqual(result['traversal']['stopReason'],'cycle');self.assertEqual(len(result['records']),1);self.assertFalse(result['complete'])
 def test_limit_is_distinct_from_tail(self):
  result=self.capture(self.fake('cycle'),1);self.assertEqual(result['traversal']['stopReason'],'node_limit');self.assertFalse(result['traversal']['loadedListEnded'])
 def test_invalid_pointer_is_recorded(self):
  result=self.capture(self.fake('invalid'));self.assertEqual(result['traversal']['stopReason'],'node_read_failure');self.assertTrue(result['traversal']['errors'])
 def test_wrong_type_is_not_captured(self):
  result=self.capture(self.fake(wrong_vtable=True));self.assertEqual(result['records'],[]);self.assertTrue(result['traversal']['errors'])
 def test_container_change_invalidates_snapshot(self):
  result=self.capture(self.fake(changed=True));self.assertEqual(result['traversal']['stopReason'],'container_changed');self.assertFalse(result['traversal']['consistentSnapshot'])
 def test_time_budget_precedes_remote_read(self):
  reader=Reader.__new__(Reader);reader.started=time.monotonic()-5;reader.max_seconds=1
  with self.assertRaises(TimeoutError):reader.read(0,8)
if __name__=='__main__':unittest.main()
