"""Regression against the actual visible-player copies, separate from fixtures."""
import hashlib,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from parse_runtime_defense import parse_capture
from import_defense_teams import normalize
CAPTURE=ROOT/'data/research/runtime.private/member-defense-capture-20261125T021309Z-1fba2f'
@unittest.skipUnless((CAPTURE/'capture.json').exists(),'requires actual local capture')
class VisiblePlayerCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.doc=parse_capture(CAPTURE,all_teams=True)
    def test_two_teams_preserve_ten_character_and_thirty_equipment_instances(self):
        teams=self.doc['snapshots'];units=[m for t in teams for m in t['members']];gear=[e for m in units for e in m['equipment'].values()]
        self.assertEqual(len(teams),2);self.assertEqual(len(units),10);self.assertEqual(len(gear),30)
        self.assertEqual(len({m['characterInstanceIdentity']['value'] for m in units}),10)
        self.assertEqual(len({e['equipmentInstanceIdentity']['value'] for e in gear}),30)
        self.assertTrue(all(e['enhancement']==5 and e['ownerAssociationStatus']=='verified-native' for e in gear))
        self.assertTrue(teams[0]['verification']['purposeConfirmed']);self.assertIsNone(teams[1]['verification'])
    def test_unrelated_visible_player_does_not_become_old_guild_member(self):
        roster=json.loads((ROOT/'data/normalized/guild-roster.private.json').read_text(encoding='utf8'))
        self.assertNotIn(self.doc['snapshots'][0]['playerId'],{m['playerId'] for m in roster['members']})
        self.assertTrue(all(t['purpose']=='pvp_defense' and t.get('guildId') is None for t in self.doc['snapshots']))
        self.assertTrue(all(t['playerDisplayName']=='井上尚彌' for t in self.doc['snapshots']))
    def test_attribute_identifiers_are_not_numeric_effect_values(self):
        gear=[e for t in self.doc['snapshots'] for m in t['members'] for e in m['equipment'].values()]
        self.assertTrue(all(e['attributeReadState']=='captured' for e in gear))
        entries=[a for e in gear for a in e['actualEffects']['entries']]
        self.assertEqual(len(entries),183);self.assertEqual(len({a['attributeId'] for a in entries}),38)
        self.assertTrue(all(a['value'] is None and a['unit'] is None and 'attributeTypeRaw' in a and 'reinforceTypeRaw' not in a for a in entries))
        result=normalize(self.doc,hashlib.sha256((CAPTURE/'observations.private.json').read_bytes()).hexdigest())
        self.assertEqual(len(result['snapshots']),2)
        self.assertTrue(all(not e['actualEffects']['numericalValuesVerified'] for t in result['snapshots'] for m in t['members'] for e in m['equipment'].values()))
    def test_all_new_template_ids_join_existing_native_datasets(self):
        characters={r['characterId'] for r in json.loads((ROOT/'data/normalized/verified-characters.json').read_text(encoding='utf8'))['records']}
        equipment={r['itemCode'] for r in json.loads((ROOT/'data/normalized/verified-equipment.json').read_text(encoding='utf8'))['records']}
        for team in self.doc['snapshots']:
            for member in team['members']:
                self.assertIn(member['characterId'],characters)
                for gear in member['equipment'].values():self.assertIn(gear['equipmentId'],equipment)
