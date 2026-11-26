"""Check the accepted rank-one guild's normal responses, including JSON strings.

Retains schema/counts/hashes only. Does not fetch player teams or change guild
membership. The earlier public-player-team refusal remains paused.
"""
import argparse
import collections
import hashlib
import json
import re
import sqlite3
import sys
import time
import urllib.parse
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from audit_public_guildwar_schema import schema_key
from pvp_session import Reader, NEW_SHA, load_session
from fetch_ranked_pvp_response import normal_json, AcquisitionStopped
from collect_ranked_pvp_http import acquisition_lock


def scan(value):
    stack = [(value, '$', 0)]
    fields = collections.Counter()
    candidates = []
    nodes = 0
    encoded = 0
    units = 0
    equipment = 0
    while stack:
        current, path, depth = stack.pop()
        nodes += 1
        if nodes > 200000 or depth > 32:
            raise AcquisitionStopped('embedded_schema_bound')
        if isinstance(current, dict):
            units += 'unitCode' in current
            equipment += 'itemCode' in current
            for key, child in current.items():
                safe = schema_key(key)
                fields[safe] += 1
                child_path = path+'.'+safe
                if re.search(r'defen|fortress|tower|deck|grouptype|teamtype', safe, re.I):
                    candidates.append({'path': child_path, 'valueType': type(child).__name__})
                stack.append((child, child_path, depth+1))
        elif isinstance(current, list):
            stack.extend((child, path+'[]', depth+1) for child in current)
        elif isinstance(current, str) and len(current) <= 2*1024*1024 and current.lstrip()[:1] in ('{', '['):
            try:
                decoded = json.loads(current)
            except ValueError:
                continue
            encoded += 1
            stack.append((decoded, path+'<decoded-json>', depth+1))
    return {'nodesChecked': nodes, 'embeddedJsonStrings': encoded,
            'fieldOccurrenceCounts': dict(fields), 'defenseFieldCandidates': candidates,
            'unitCodeObjects': units, 'itemCodeObjects': equipment, 'scanComplete': True}


def run():
    folder = ROOT/'data/research/runtime.private/guild-battle-profile-probe'
    folder.mkdir(exist_ok=True)
    state = folder/'embedded-schema-progress.private.json'
    if state.exists() and json.loads(state.read_bytes()).get('stopReason') in ('http_access_denied', 'http_error_429'):
        raise AcquisitionStopped('previous_refusal_requires_manual_access_review')
    with closing(sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro', uri=True)) as db:
        ranking = json.loads(db.execute("SELECT s.payload FROM current_guild_rankings c JOIN guild_rank_sources s USING(snapshot_id) WHERE c.scope='top100'").fetchone()[0])
    guild = next(g for g in ranking['guilds'] if g['rank'] == 1)
    report = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'moduleSha256': NEW_SHA,
              'guildAlias': hashlib.sha256(guild['guildId'].encode()).hexdigest()[:20],
              'rankingSnapshotId': ranking['snapshotId'], 'requests': [], 'stopReason': None,
              'credentialsUsedInRamOnly': True, 'rawResponseRetained': False,
              'playerTeamRequests': 0, 'defensesImported': 0}
    with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe', 'emulator-5554', 100) as reader:
        reader.expected_module_sha = NEW_SHA
        reader.refresh()
        session = load_session(reader, authorized=True)
    try:
        for suffix, purpose in [('', 'guild-profile'), ('/member/list', 'guild-roster')]:
            raw, doc = normal_json(session, '/guild/'+urllib.parse.quote(guild['guildId'], safe='')+suffix, purpose=purpose)
            result = doc.get('result')
            if purpose == 'guild-profile' and result.get('guild', {}).get('gid') != guild['guildId']:
                raise AcquisitionStopped('guild_profile_identity_differs')
            report['requests'].append({'purpose': purpose, 'responseSha256': hashlib.sha256(raw).hexdigest(), **scan(result)})
            state.write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
            time.sleep(.5)
    except AcquisitionStopped as error:
        report['stopReason'] = str(error)
        state.write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
        raise
    (ROOT/'reports/guild-normal-embedded-schema-check.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'requests': len(report['requests']),
                      'encodedObjects': sum(r['embeddedJsonStrings'] for r in report['requests']),
                      'defenseCandidates': sum(len(r['defenseFieldCandidates']) for r in report['requests']),
                      'rawResponsesRetained': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--use-authorized-runtime-session', action='store_true')
    args = parser.parse_args()
    if not args.use_authorized_runtime_session:
        parser.error('authorized local game session required')
    with acquisition_lock():
        run()
