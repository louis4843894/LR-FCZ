"""Inspect the exact public Legend export; retain schema statistics only.

No administrator mode, login, game session, player-data import or raw export.
Empty source objects are observations, not proof a player has no formation.
"""
import argparse
import collections
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://pvp-data.warmycat.com/guildwar_data_LEGEND.json'
SENSITIVE = {'cookie', 'lf_ac', 'authorization', 'password', 'access_token', 'refresh_token'}


def schema_key(key):
    identifier = re.fullmatch(r'[Uu][a-f0-9]{32}|[a-f0-9]{16,}', key) or (len(key) >= 20 and re.search(r'[0-9]{6,}', key))
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,59}', key) and not identifier:
        return key
    return '<numeric-key>' if key.isdigit() else '<identifier-key>'


def inspect(doc):
    guilds = doc.get('guilds') if isinstance(doc, dict) else None
    if not isinstance(guilds, list) or not 1 <= len(guilds) <= 200:
        raise ValueError('known compact export shape changed')
    fields = collections.Counter()
    member_schemas = collections.Counter()
    guild_fields = set()
    root_types = collections.Counter()
    root_keys = collections.Counter()
    candidates = collections.Counter()
    members = 0
    empty = 0
    for guild in guilds:
        guild_fields.update(schema_key(key) for key in guild.keys())
        for member in guild.get('members') or []:
            members += 1
            member_schemas[','.join(sorted(schema_key(key) for key in member.keys()))] += 1
            group = member.get('guildwar')
            root_types[type(group).__name__] += 1
            if isinstance(group, dict):
                empty += not group
                root_keys.update(schema_key(key) for key in group.keys())
    stack = [doc]
    nodes = 0
    characters = 0
    encoded = 0
    while stack:
        value = stack.pop()
        nodes += 1
        if nodes > 3000000:
            raise ValueError('schema traversal bound; previous report retained')
        if isinstance(value, dict):
            if any(key in value for key in ('unitCode', 'rangerId', 'characterId')):
                characters += 1
            for key, child in value.items():
                if key.lower() in SENSITIVE:
                    raise ValueError('unexpected sensitive field; no values retained')
                if not schema_key(key).startswith('<'):
                    fields[key] += 1
                    if re.search(r'defen|fortress|tower|deck|teamtype|grouptype', key, re.I):
                        candidates[key] += 1
                stack.append(child)
        elif isinstance(value, list):
            stack.extend(value)
        elif isinstance(value, str) and len(value) <= 2000000 and value[:1] in ('{', '['):
            try:
                decoded = json.loads(value)
            except ValueError:
                continue
            encoded += 1
            stack.append(decoded)
    return {'guilds': len(guilds), 'members': members, 'objectsWithCharacterCode': characters,
            'guildFieldNames': sorted(guild_fields), 'memberSchemas': dict(member_schemas),
            'guildwarRootTypes': dict(root_types), 'guildwarRootKeys': dict(root_keys),
            'emptyGuildwarObjects': empty, 'emptyObjectMeaningEstablished': False,
            'fieldOccurrenceCounts': dict(fields), 'defenseDeckTowerCandidates': dict(candidates),
            'encodedJsonStrings': encoded, 'nodesChecked': nodes, 'schemaTraversalComplete': True,
            'rawPlayerDataRetained': False, 'importedAsDefense': 0,
            'purposeFromReviewedProducerUi': 'guild war attack formation'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true')
    args = parser.parse_args()
    if not args.fetch:
        parser.error('--fetch is required to read this exact public source')
    request = urllib.request.Request(URL, headers={'User-Agent': 'LR-local-schema-review'})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise ValueError('public source unavailable')
        raw = response.read(26*1024*1024+1)
    if len(raw) > 26*1024*1024:
        raise ValueError('public export size bound')
    report = {**inspect(json.loads(raw)), 'checkedAt': datetime.now(timezone.utc).isoformat(),
              'sourceUrl': URL, 'sourceSha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    (ROOT/'reports/public-guildwar-reference-complete-schema.json').write_text(
        json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(json.dumps({k: report[k] for k in ('guilds', 'members', 'objectsWithCharacterCode',
                                           'defenseDeckTowerCandidates', 'schemaTraversalComplete')}))
