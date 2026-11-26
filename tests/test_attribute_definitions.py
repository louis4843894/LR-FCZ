import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from parse_equipment_attribute_definitions import parse
CAP=ROOT/'data/research/runtime.private/unit-equip-attribute-observation'
@unittest.skipUnless((CAP/'capture.json').exists(),'requires actual private definitions')
class DefinitionTests(unittest.TestCase):
 def test_captured_types_and_ids_with_unknown_units_preserved(self):
  result=parse(CAP);self.assertEqual(result['recordCount'],10)
  self.assertEqual(len({x['attrNo'] for x in result['records']}),10)
  self.assertTrue(all(x['unit'] is None and x['equipmentAssociations'] is None for x in result['records']))
  self.assertEqual(result['equipmentRelationStatus'],'not-established')
if __name__=='__main__':unittest.main()
