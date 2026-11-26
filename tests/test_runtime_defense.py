"""Regression against saved real native observations; never creates site fixtures."""
import json,shutil,sys,tempfile,unittest,struct,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from parse_runtime_defense import parse_capture
from import_defense_teams import normalize
CAPTURE=ROOT/'data/research/runtime.private/defense-capture-20261118T182700Z-3ea7a5'
@unittest.skipUnless((CAPTURE/'capture.json').exists(),'requires private actual native capture')
class RuntimeDefenseTests(unittest.TestCase):
    def test_both_observed_teams_keep_distinct_equipment_instances(self):
        doc=parse_capture(CAPTURE,all_teams=True)
        self.assertEqual([t['teamId'] for t in doc['snapshots']],['pvpteam/1','pvpteam/2'])
        gear=[e for t in doc['snapshots'] for m in t['members'] for e in m['equipment'].values()]
        self.assertEqual(len(gear),30);self.assertEqual(len({e['equipmentInstanceIdentity']['value'] for e in gear}),30)
        repeated=[e for e in gear if e['equipmentId']=='eq_amr_evt_117'];self.assertEqual(len(repeated),2)
        self.assertNotEqual(repeated[0]['equipmentInstanceIdentity']['value'],repeated[1]['equipmentInstanceIdentity']['value'])
        self.assertIsNone(doc['snapshots'][1]['verification']);self.assertTrue(all(e['ownerAssociationStatus']=='verified-native' for e in gear))
    def test_actual_enhancement_is_independent_of_template_maximum_and_owner_mismatch_rejected(self):
        with tempfile.TemporaryDirectory(dir=CAPTURE.parent) as folder:
            p=Path(folder)
            for file in CAPTURE.iterdir():
                if file.is_file():shutil.copyfile(file,p/file.name)
            meta=json.loads((p/'capture.json').read_text());record=meta['records'][0];item=record['files']['gear-1'];file=p/item['file'];raw=bytearray(file.read_bytes())
            struct.pack_into('<I',raw,0x74,123);file.write_bytes(raw);item['sha256']=hashlib.sha256(raw).hexdigest();(p/'capture.json').write_text(json.dumps(meta))
            team=parse_capture(p,all_teams=True)['snapshots'];self.assertTrue(all(e['enhancement']==5 for t in team for m in t['members'] for e in m['equipment'].values()))
            struct.pack_into('<Q',raw,0x98,int(record['instanceId'])+1);file.write_bytes(raw);item['sha256']=hashlib.sha256(raw).hexdigest();(p/'capture.json').write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,'unitInvenId'):parse_capture(p)
    def test_selected_real_team_and_instance_equipment(self):
        doc=parse_capture(CAPTURE);team=normalize(doc,'test-hash')['snapshots'][0]
        self.assertEqual(team['teamId'],'pvpteam/1')
        self.assertEqual([m['characterId'] for m in team['members']],['u1618e-ka','u1535e-brown','u1571e-qs','u1631e-sally','u1646e-jessica'])
        self.assertEqual(len({m['characterInstanceIdentity']['value'] for m in team['members']}),5)
        equipment=[e for m in team['members'] for e in m['equipment'].values()]
        self.assertEqual(len(equipment),15);self.assertTrue(all(e['enhancement']==5 and e['actualEffects'] is None for e in equipment))
        templates={r['itemCode'] for r in json.loads((ROOT/'data/normalized/verified-equipment.json').read_text(encoding='utf8'))['records']}
        self.assertTrue(all(e['equipmentId'] in templates for e in equipment))
    def test_new_actual_fields_require_native_field_evidence(self):
        doc=parse_capture(CAPTURE);gear=doc['snapshots'][0]['members'][0]['equipment']['weapon'];del gear['fieldEvidence']
        with self.assertRaisesRegex(ValueError,'unverified equipment'):normalize(doc,'test-hash')
    def test_wrong_group_or_modified_object_rejected(self):
        with tempfile.TemporaryDirectory(dir=CAPTURE.parent) as folder:
            p=Path(folder)
            for file in CAPTURE.iterdir():
                if file.is_file():shutil.copyfile(file,p/file.name)
            meta=json.loads((p/'capture.json').read_text());meta['groupKind']=12;(p/'capture.json').write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,'PVP group'):parse_capture(p)
            meta['groupKind']=5;(p/'capture.json').write_text(json.dumps(meta));gear_file=p/meta['records'][0]['files']['gear-1']['file'];raw=bytearray(gear_file.read_bytes());raw[0x68]^=1;gear_file.write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'hash mismatch'):parse_capture(p)
    def test_screenshot_presence_does_not_automatically_mean_visually_verified(self):
        with tempfile.TemporaryDirectory(dir=CAPTURE.parent) as folder:
            p=Path(folder)
            for file in CAPTURE.iterdir():
                if file.is_file():shutil.copyfile(file,p/file.name)
            (p/'screen-verification.private.json').unlink()
            self.assertIsNone(parse_capture(p)['snapshots'][0]['verification'])
