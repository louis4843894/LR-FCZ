"""Synthetic schema/retention regressions; never requests or imports real data."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_public_guildwar_schema import inspect


class PublicGuildSchemaTest(unittest.TestCase):
    def test_numeric_team_map_counts_fields_without_retaining_values(self):
        source = {'guilds': [{'guildName': 'fixture guild', 'members': [
            {'name': 'fixture member', 'level': 1, 'guildwar': {'0': [
                {'unitCode': 'fixture-role-one', 'unitLevel': 10},
                {'unitCode': 'fixture-role-two', 'unitLevel': 20}]}},
            {'name': 'fixture empty observation', 'guildwar': {}},
        ]}]}
        report = inspect(source)
        self.assertEqual(report['objectsWithCharacterCode'], 2)
        self.assertEqual(report['fieldOccurrenceCounts']['unitCode'], 2)
        self.assertEqual(report['emptyGuildwarObjects'], 1)
        self.assertFalse(report['emptyObjectMeaningEstablished'])
        self.assertTrue(all(isinstance(v, int) for v in report['fieldOccurrenceCounts'].values()))
        text = json.dumps(report)
        for private_value in ('fixture guild', 'fixture member', 'fixture-role-one', 'fixture-role-two'):
            self.assertNotIn(private_value, text)

    def test_encoded_object_is_checked_and_identifier_keys_are_not_retained(self):
        source = {'guilds': [{'members': [{'guildwar': {'opaqueIdentifier0123456789': []},
            'data': json.dumps({'defenceDecks': [{'unitCode': 'fixture-role'}]})}]}]}
        report = inspect(source)
        self.assertEqual(report['defenseDeckTowerCandidates']['defenceDecks'], 1)
        self.assertEqual(report['encodedJsonStrings'], 1)
        self.assertEqual(report['objectsWithCharacterCode'], 1)
        self.assertNotIn('fixture-role', json.dumps(report))
        self.assertNotIn('opaqueIdentifier0123456789', json.dumps(report))

    def test_credential_shaped_source_is_rejected_without_echoing_value(self):
        secret = 'fixture-do-not-echo'
        with self.assertRaises(ValueError) as error:
            inspect({'guilds': [{'members': [{'guildwar': {}, 'cookie': secret}]}]})
        self.assertNotIn(secret, str(error.exception))


if __name__ == '__main__':
    unittest.main()
