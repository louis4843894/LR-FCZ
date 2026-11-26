import copy,sqlite3,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from build_native_gear_labels import resolve,save
from native_layouts import NEW_SHA

class NativeGearLabelsTests(unittest.TestCase):
 def test_conflicting_ids_are_withheld_instead_of_using_a_majority(self):
  names={34:{'code':'ALL_ATK_MUL','label':'總攻擊力 (%)'},21:{'code':'PRD','label':'產生時間 (%)'}}
  records,conflicts=resolve([{'attributeId':1,'typeEnum':34,'sha256':'a'*64},{'attributeId':1,'typeEnum':34,'sha256':'b'*64},{'attributeId':1,'typeEnum':21,'sha256':'c'*64},{'attributeId':2,'typeEnum':34,'sha256':'d'*64}],names)
  self.assertEqual(conflicts,[1]);self.assertEqual([r['attributeId'] for r in records],[2]);self.assertIsNone(records[0]['numericValue'])
 def test_unknown_types_do_not_get_invented_names(self):
  records,conflicts=resolve([{'attributeId':1,'typeEnum':999,'sha256':'a'*64}],{})
  self.assertEqual((records,conflicts),([],[]))
 def test_immutable_label_storage_is_idempotent_and_does_not_replace_on_conflict(self):
  doc={'sourceId':'isolated-fixture-labels','moduleSha256':NEW_SHA,'records':[{'attributeId':2,'typeEnum':34,'code':'ALL_ATK_MUL','label':'總攻擊力 (%)'}]}
  with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
   folder=Path(folder);database=folder/'fixture.sqlite'
   with patch('build_native_gear_labels.ROOT',folder):
    save(doc,database);save(doc,database);bad=copy.deepcopy(doc);bad['records'][0]['label']='fixture changed'
    with self.assertRaisesRegex(ValueError,'immutable'):save(bad,database)
   with closing(sqlite3.connect(database)) as db:
    self.assertEqual(db.execute('SELECT count(*) FROM gear_attribute_labels').fetchone()[0],1)
    self.assertEqual(db.execute('SELECT label FROM gear_attribute_labels').fetchone()[0],'總攻擊力 (%)')
    self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

if __name__=='__main__':unittest.main()
