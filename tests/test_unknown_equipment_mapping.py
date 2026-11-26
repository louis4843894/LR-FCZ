import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from audit_equipment_reference import build_audit
from equipment_unknown_mapping import map_unknown

class UnknownMappingTests(unittest.TestCase):
    def test_all_actual_unknowns_classified_without_filling_instance_values(self):
        folder=ROOT/'data/research/external-reference/audit-20261125T075450Z-051be1'
        if not folder.exists():self.skipTest('requires saved actual source copies')
        report,export=build_audit(folder)
        self.assertEqual(report['externalMappingSummary'],{'exact_attribute_id':216,'template_candidates_only':123,'same_equipment_key_and_base_range':34})
        unknown=[c for c in report['attributeChecks'] if c['status']=='unparsed_native']
        self.assertEqual(len(unknown),373)
        self.assertTrue(all(c['nativeValue'] is None and c['externalMapping']['actualValueVerified'] is False for c in unknown))
        row=next(c for c in unknown if c['itemCode']=='eq_wpn_evt_138' and c['attributeId']==120018)
        self.assertEqual(row['externalMapping']['condition']['label'],'敏捷型Ranger')
        self.assertEqual(row['externalMapping']['candidates'][0]['upgradeStep'],-2)
        zero=[c for c in unknown if c['attributeId']==0]
        self.assertEqual(len(zero),123)
        self.assertTrue(all(c['externalMapping']['status']=='template_candidates_only' for c in zero))

    def test_cross_id_key_and_condition_conflicts_are_not_accepted(self):
        entry={'attributeId':120018,'attributeCode':'PRD_SPE_MUL'}
        native={'attributeSha256':'a'*64,'hasDependency68':False,'hasDependency70':False,'selector30':'none','selector48':'AGI','baseStart':-.062,'baseEnd':-.08}
        source={'url':'fixture','sha256':'b'*64}
        ref={'advanced':{'condition':{'key':'CUSTOM:EQUIP_RANGER_TYPE_AGI','label':'fixture'},'defaultOption':{'optionKey':'EQUIP:GEAR_FILTER_PRD_SPE_MUL_nm','range':{'min':-6.2,'max':-8.,'unit':'PERCENT'}},'switchOptions':[]}}
        self.assertEqual(map_unknown(entry,ref,{120018:{'optionKey':'wrong'}},native,source)['status'],'conflict')
        ref['advanced']['condition']['key']='CUSTOM:EQUIP_RANGER_TYPE_FIRE'
        self.assertEqual(map_unknown(entry,ref,{120018:{'optionKey':'EQUIP:GEAR_FILTER_PRD_SPE_MUL_nm'}},native,source)['status'],'conflict')

if __name__=='__main__':unittest.main()
