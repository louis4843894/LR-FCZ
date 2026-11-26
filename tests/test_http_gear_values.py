import sys,struct,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'scripts/runtime')]
from derive_http_gear_values import reconstruct,instance_hash,observation_id,matching_roll_entry
class HttpGearValueTests(unittest.TestCase):
 def raw(self):
  raw=bytearray(0x78);struct.pack_into('<IIII',raw,0x18,40001,2,0,1);struct.pack_into('<ff',raw,0x28,.74,.74);raw[0x30:0x36]=raw[0x48:0x4e]=b'\x08none\0';return raw
 def test_actual_grade_and_enhancement_are_applied_once_and_source_unchanged(self):
  raw=self.raw();before=bytes(raw);self.assertEqual(reconstruct(raw,0,5,1)['value'],444);self.assertEqual(reconstruct(raw,0,0,1)['value'],74);self.assertEqual(bytes(raw),before)
 def test_unknown_grade_dependencies_and_selector_are_withheld(self):
  self.assertIsNone(reconstruct(self.raw(),100,5,1));self.assertIsNone(reconstruct(self.raw(),False,5,1))
  raw=self.raw();struct.pack_into('<Q',raw,0x68,1234);self.assertIsNone(reconstruct(raw,0,5,1))
  raw=self.raw();raw[0x31]=ord('x');self.assertIsNone(reconstruct(raw,0,5,1))
 def test_duplicate_templates_do_not_collapse_owner_scoped_instances_or_slots(self):
  identity={'namespace':'player-owned-equipment','value':'1'};self.assertNotEqual(instance_hash('a',identity),instance_hash('b',identity))
  t={'snapshotId':'s','playerId':'a'};m={'memberIndex':0};self.assertNotEqual(observation_id(t,m,'weapon'),observation_id(t,m,'armor'))
 def test_cloud_join_cannot_take_a_value_from_another_instance_or_grade(self):
  identity={'namespace':'player-owned-equipment','value':'1'};t={'playerId':'a'};g={'equipmentId':'eq_fixture','enhancement':5,'instanceGrade':9,'equipmentInstanceIdentity':identity};entry={'index':0,'attributeId':1,'valueGradeRaw':2,'sourceField':'attr1No'}
  result={**entry,'value':-30,'unit':'PERCENT','valueVerified':True,'enhancementIncluded':True};record={'equipmentId':'eq_fixture','enhancement':5,'instanceGrade':9,'equipmentInstanceHash':instance_hash('a',identity),'entries':[result]}
  self.assertEqual(matching_roll_entry(record,t,{},'weapon',g,entry)['value'],-30)
  self.assertIsNone(matching_roll_entry(record,{'playerId':'b'},{},'weapon',g,entry));self.assertIsNone(matching_roll_entry(record,t,{},'weapon',g,{**entry,'valueGradeRaw':3}));self.assertIsNone(matching_roll_entry(record,t,{},'weapon',g,{**entry,'sourceField':'skillPlusAttr1No'}))
if __name__=='__main__':unittest.main()
