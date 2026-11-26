import hashlib,json,struct,sys,unittest,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from parse_runtime_gear_values import scalar,enrich

class OrdinaryValueTests(unittest.TestCase):
    def raw(self):
        raw=bytearray(0x78);struct.pack_into('<IIII',raw,0x18,40001,2,0,1);struct.pack_into('<ff',raw,0x28,.74,.74)
        raw[0x30:0x36]=raw[0x48:0x4e]=b'\x08none\0';return raw
    def test_verified_native_formula_includes_current_enhancement_once(self):
        self.assertEqual(scalar(self.raw(),5,1)['value'],444)
        self.assertEqual(scalar(self.raw(),0,1)['value'],74)
    def test_special_dependency_and_item_selector_never_use_ordinary_formula(self):
        for offset in (0x68,0x70):
            raw=self.raw();struct.pack_into('<Q',raw,offset,0x1234);self.assertIsNone(scalar(raw,5,1))
        raw=self.raw();raw[0x31]=ord('x');self.assertIsNone(scalar(raw,5,1))
    def test_invalid_grade_is_rejected(self):
        raw=self.raw();struct.pack_into('<I',raw,0x20,3)
        with self.assertRaises(ValueError):scalar(raw,5,1)

    def test_calibration_reuses_formula_without_copying_another_players_values_or_review_flags(self):
        capture=ROOT/'data/research/runtime.private/guild-member-pvp-20261125T041326Z-0dad1d'
        calibration=ROOT/'data/research/runtime.private/member-defense-capture-20261125T023755Z-ee891f'
        factor=ROOT/'data/research/runtime.private/gear-factor-20261125T042702Z.private.json'
        if not capture.exists() or not factor.exists():self.skipTest('requires local actual calibration and target copies')
        args=[capture,factor,calibration/'ordinary-value-screen-review.private.json',ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so',ROOT/'data/extracted/lr_20261116T212608096_7b99bdd0/assets/res/tutorial_res/db/lang_equip/lang_equip.ndb',calibration,ROOT/'data/research/runtime.private/gear-factor-20261125T031832Z.private.json']
        result=enrich(*args)
        entries=[e for t in result['snapshots'] for m in t['members'] for g in m['equipment'].values() for e in (g.get('actualEffects') or {}).get('entries',[])]
        self.assertEqual(sum(e.get('value') is not None for e in entries),90)
        self.assertFalse(any(e.get('valueVisuallyVerified') for e in entries))
        self.assertFalse(result['captureEvidence']['ordinaryValues']['currentCaptureVisuallyVerified'])
        with tempfile.TemporaryDirectory() as folder:
            bad=Path(folder)/'factor.json';meta=json.loads(factor.read_text(encoding='utf8'));meta['coefficientRawHex']='00000000';bad.write_text(json.dumps(meta))
            args[1]=bad
            with self.assertRaisesRegex(ValueError,'factor bytes'):enrich(*args)

if __name__=='__main__':unittest.main()
