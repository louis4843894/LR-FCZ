"""Synthetic tests for normal-response schema inspection; no game access."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'scripts/runtime'))
from probe_guild_embedded_fields import scan
from fetch_ranked_pvp_response import AcquisitionStopped


class EmbeddedGuildSchemaTest(unittest.TestCase):
    def test_checks_encoded_teams_and_retains_no_values(self):
        report = scan({'data': json.dumps({'defenceDecks': [
            {'unitCode': 'fixture-unit', 'equip': {'itemCode': 'fixture-item'}}]})})
        self.assertEqual(report['embeddedJsonStrings'], 1)
        self.assertEqual(report['unitCodeObjects'], 1)
        self.assertEqual(report['itemCodeObjects'], 1)
        self.assertIn('$.data<decoded-json>.defenceDecks', [r['path'] for r in report['defenseFieldCandidates']])
        self.assertNotIn('fixture-unit', json.dumps(report))
        self.assertNotIn('fixture-item', json.dumps(report))

    def test_redacts_identifier_keys_and_stops_excess_depth(self):
        identifier = 'u'+'a'*32
        report = scan({identifier: {'unitCode': 'fixture-unit'}})
        self.assertNotIn(identifier, json.dumps(report))
        value = {'unitCode': 'fixture-unit'}
        for _ in range(34):
            value = {'data': value}
        with self.assertRaises(AcquisitionStopped):
            scan(value)


if __name__ == '__main__':
    unittest.main()
