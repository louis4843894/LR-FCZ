"""Compare the saved, actual public source with the attributed local preview."""
import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_equipment_reference_preview import ReferenceLabels
SOURCE = ROOT / 'data/research/external-reference'

@unittest.skipUnless((SOURCE / 'official-locales.json').exists(), 'requires saved public-source research copies')
class ReferencePreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalogs = {}
        for file in ['official-locales.json', 'custom-locales.json']:
            for r in json.loads((SOURCE / file).read_text(encoding='utf8')):
                catalogs[r['key']] = r.get('zh_TW') or r.get('en') or r['key']
        cls.labels = ReferenceLabels(catalogs)
        cls.source = json.loads((SOURCE / 'equipment.json').read_text(encoding='utf8'))['equipment']
        preview = json.loads((ROOT / 'data/normalized/equipment-reference-preview.json').read_text(encoding='utf8'))
        cls.preview = {r['itemCode']: r for r in preview['records']}

    def test_actual_catalog_newlines_and_bound_spec_description(self):
        self.assertEqual(self.labels.render('EQUIP:GEAR_FILTER_PRD_SPE_MUL_nm'), 'Ranger\n重新產生時間 (%)')
        source = next(r for r in self.source if r['equipCode'] == 'eq_2607_acc_29')['specPlus']['specialOptions'][0]
        text = self.labels.render({'key': source['descriptionKey'], 'bindings': source['descriptionBindings']})
        self.assertEqual(text, '使用增益技能時，將以超高機率在3秒內爆擊傷害量增加50～60%')
        with self.assertRaisesRegex(ValueError, 'Unbound native'):
            self.labels.render({'key': source['descriptionKey'], 'bindings': {}})

    def test_target_values_remain_external_and_preserve_units(self):
        target = self.preview['eq_2202_amr_06']
        self.assertEqual([e['range'] for e in target['normalOptions']], [
            {'min': 5.0, 'max': 8.0, 'unit': 'PERCENT'},
            {'min': 5.0, 'max': 8.0, 'unit': 'PERCENT'},
            {'min': 1.5, 'max': 3.0, 'unit': 'PERCENT'}])
        self.assertTrue(all(e['attributeId'] is None for e in target['normalOptions']))

    def test_spec_steps_and_structured_condition_identity_are_preserved(self):
        e = self.preview['eq_2607_acc_29']['specPlus']['specialOptions'][0]
        self.assertEqual(e['magnitudeUpgrade'], 6)
        self.assertEqual(e['chanceUpgrade'], 0)
        self.assertEqual(e['durationUpgradeSeconds'], 0)
        self.assertEqual(json.loads(e['conditions'][0]['key']), {'templateKey': 'CUSTOM:TALENT_TEXT_TLT_SKILL_BUFF_COUNT', 'args': [1]})
        self.assertEqual(e['conditions'][0]['label'], '使用1次增益技能時')
