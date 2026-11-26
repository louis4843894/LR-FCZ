"""Offline parser for copies from the verified normal PVP ranking layer.

Player identities remain local. This does not infer defense teams or fetch data.
"""
import argparse
import hashlib
import json
import re
import struct
from datetime import datetime
from pathlib import Path

from native_layouts import NEW_SHA


def parse_capture(directory):
    directory = Path(directory)
    manifest_bytes = (directory / 'capture.private.json').read_bytes()
    meta = json.loads(manifest_bytes)
    if (meta.get('sourceKind') != 'native-visible-pvp-ranking'
            or meta.get('moduleSha256') != NEW_SHA or meta.get('consistent') is not True):
        raise ValueError('unverified or inconsistent PVP ranking capture')
    captured_at = datetime.fromisoformat(meta['capturedAt'].replace('Z', '+00:00'))
    if captured_at.tzinfo is None:
        raise ValueError('ranking timestamp must contain a timezone')
    if type(meta.get('loadedCount')) is not int or not 1 <= meta['loadedCount'] <= 256:
        raise ValueError('invalid loaded ranking count')
    if not 1 <= len(meta['rows']) <= meta['loadedCount']:
        raise ValueError('empty or invalid ranking rows; retain previous snapshot')

    def blob(key):
        entry = meta['files'][key]
        if Path(entry['file']).name != entry['file']:
            raise ValueError('ranking blob must be a direct child')
        data = (directory / entry['file']).read_bytes()
        if len(data) != entry['length'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('ranking blob hash/length mismatch')
        return data

    layer = blob('layer')
    if len(layer) != 0x1a0 or struct.unpack_from('<Q', layer)[0] - meta['moduleBase'] + 0x100000 != 0x1f14af8:
        raise ValueError('ranking layer type mismatch')
    header, array_data, pointers = blob('array'), blob('array-data'), blob('row-pointers')
    if (len(header)!=0x20 or struct.unpack_from('<Q',header)[0]-meta['moduleBase']+0x100000!=0x1f6a7f8
            or len(array_data)!=16 or len(pointers)!=meta['loadedCount']*8
            or struct.unpack_from('<Q',layer,0x178)[0]!=meta['arrayAddress']):
        raise ValueError('ranking array source/type mismatch')
    count,capacity=struct.unpack_from('<II',array_data)
    if count!=meta['loadedCount'] or not count<=capacity<=4096:
        raise ValueError('ranking array count/capacity mismatch')
    addresses=struct.unpack('<'+'Q'*count,pointers)
    if not all(addresses) or len(set(addresses))!=len(addresses):
        raise ValueError('ranking array has invalid/repeated pointers')
    if (meta.get('capturedCount')!=len(meta['rows'])
            or meta.get('loadedArrayFullyCaptured') is True and (len(meta['rows'])!=count or meta.get('errors'))):
        raise ValueError('ranking capture completeness claim is inconsistent')
    rows, seen_players, seen_indices = [], set(), set()
    for row in meta['rows']:
        index = row['index']
        prefix = row['prefix']
        if (type(index) is not int or index < 0 or index >= meta['loadedCount']
                or index in seen_indices or prefix != f'row-{index:03d}' or row['status'] != 'captured'
                or row.get('objectAddress')!=addresses[index]):
            raise ValueError('invalid/duplicate ranking row position')
        seen_indices.add(index)
        raw = blob(prefix)
        if len(raw) != 0xb0 or struct.unpack_from('<Q', raw)[0] - meta['moduleBase'] + 0x100000 != 0x1e53d58:
            raise ValueError('ranking record type mismatch')

        def text(label, offset):
            value = blob(prefix + '-' + label)
            if raw[offset] & 1:
                if len(value) != struct.unpack_from('<Q', raw, offset + 8)[0]:
                    raise ValueError('ranking long string dependency mismatch')
            else:
                size = raw[offset] >> 1
                if size > 22 or raw[offset + size + 1] != 0 or value != raw[offset+1:offset+1+size]:
                    raise ValueError('ranking inline string mismatch')
            result = value.decode('utf8', 'strict')
            if '\x00' in result or len(result) > 1024:
                raise ValueError('invalid ranking string')
            return result

        uid = text('player-id', 0x18)
        name = text('name', 0x58)
        phase = text('league-phase', 0x78)
        score, rank = struct.unpack_from('<ii', raw, 0x30)
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', uid) or uid in seen_players or rank < 1:
            raise ValueError('missing/duplicate ranking identity or invalid rank')
        seen_players.add(uid)
        rows.append({'playerId': uid, 'rank': rank, 'score': score,
                     'displayName': name or None, 'leaguePhase': phase or None,
                     'retrievedAt': meta['capturedAt'], 'sourceRowIndex': index,
                     'sourceRecordSha256': hashlib.sha256(raw).hexdigest(),
                     'defenseState': 'not_read', 'defenseSnapshotIds': [],
                     'defenseRetrievedAt': None, 'failureReason': None})
    snapshot_id = 'pvp-ranking-' + hashlib.sha256(manifest_bytes).hexdigest()[:24]
    return {
        'schemaVersion': 1, 'sourceKind': 'verified-native-pvp-ranking',
        'parserVersion': 'pvp-ranking-v1', 'snapshotId': snapshot_id,
        'capturedAt': meta['capturedAt'], 'gameVersion': meta['gameVersion'],
        'moduleSha256': NEW_SHA, 'sourceCaptureSha256': hashlib.sha256(manifest_bytes).hexdigest(),
        'sourceDirectory': str(directory.resolve()),
        'scope': {'kind': 'visible-pvp-ranking-list', 'label': meta.get('scopeLabel'),
                  'wholeRankingComplete': False},
        'rankRange': {'minimum': min(row['rank'] for row in rows),
                      'maximum': max(row['rank'] for row in rows)},
        'loadedCount': meta['loadedCount'], 'retrievedPlayerCount': len(rows),
        'loadedArrayFullyCaptured': meta.get('loadedArrayFullyCaptured') is True,
        'status': 'success' if meta.get('loadedArrayFullyCaptured') is True and not meta.get('errors') else 'partial',
        'failedRowCount': len(meta.get('errors') or []),
        'players': rows,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    private_root=Path(__file__).resolve().parents[1]/'data/research/runtime.private'
    if not args.output.resolve().is_relative_to(private_root.resolve()):
        raise ValueError('ranking identities must stay under runtime.private')
    document = parse_capture(args.capture)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'players': document['retrievedPlayerCount'], 'rankRange': document['rankRange'],
                      'status': document['status'], 'wholeRankingComplete': False}))
