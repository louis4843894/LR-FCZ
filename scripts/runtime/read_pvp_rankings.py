"""Bounded read-only copies of the normal PVP ranking layer's loaded records.

No endpoint requests, UI navigation, injection, or whole-process memory dump.
The loaded array is not evidence that the entire leaderboard was retrieved.
"""
import argparse
import hashlib
import json
import struct
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from bounded_equipment_reader import Reader
from equipment_memory import ROOT, GBASE, u64
from read_defense_team import typed
from read_guild_members import array
sys.path.insert(0, str(ROOT / 'scripts'))
from native_layouts import NEW_SHA

SCENE = 0x1f150f8  # exact RTTI: PvpMainController
LAYER = 0x1f14af8  # exact RTTI: PvpRankingLayer
ROW = 0x1e53d58    # exact RTTI: RankingData
_LAYER_PATH = None


def find_layer(reader):
    global _LAYER_PATH
    if reader.module_sha != NEW_SHA:
        raise ValueError('PVP ranking layout requires the verified 12.4.2 module')
    director = u64(reader.read(reader.base + 0x204e2f0 - GBASE, 8))
    scene = u64(reader.read(director + 0xf0, 8))
    typed(reader, scene, 8, SCENE)
    # Reuse only observed child indices and class identities, never addresses.
    # Every new scene/PID/base is traversed afresh and each step revalidated.
    if _LAYER_PATH:
        try:
            node=scene;raw=typed(reader,node,0x110,SCENE)
            for index,expected_ap in _LAYER_PATH:
                children,*_=array(reader,u64(raw,0xb8),128)
                if index>=len(children):raise ValueError('ranking child path changed')
                node=children[index];raw=typed(reader,node,0x110,expected_ap)
                if not raw[0x104]:raise ValueError('cached UI path is hidden')
            if u64(raw)-reader.base+GBASE==LAYER:return director,scene,node
        except (ValueError,RuntimeError):
            _LAYER_PATH=None
    pending = [(scene, 0, [])]
    seen = set()
    matches = []
    matched_depth = None
    types={}
    selected_path=None
    while pending and len(seen) < 320:
        node, depth, path = pending.pop(0)
        if matched_depth is not None and depth > matched_depth:
            break
        if not node or node in seen:
            continue
        seen.add(node)
        raw = reader.read(node, 0xc0)
        types[node]=u64(raw)-reader.base+GBASE
        if u64(raw) - reader.base + GBASE == LAYER:
            matches.append(node)
            matched_depth = depth
            selected_path=path
            continue
        if depth < 7 and u64(raw, 0xb8):
            children, *_ = array(reader, u64(raw, 0xb8), 128)
            pending.extend((child, depth + 1, path+[(index,child)]) for index,child in enumerate(children))
    if pending and matched_depth is None:
        raise ValueError('ranking scene traversal exceeded node bound')
    if len(matches) != 1:
        raise ValueError('expected exactly one normally loaded PVP ranking layer')
    _LAYER_PATH=[(index,types[node]) for index,node in selected_path]
    return director, scene, matches[0]


def capture(reader, output, max_rows=100, scope_label=None):
    if type(max_rows) is not int or not 1 <= max_rows <= 256:
        raise ValueError('max_rows must be 1..256')
    director, scene, layer = find_layer(reader)
    layer_raw = typed(reader, layer, 0x1a0, LAYER)
    source = u64(layer_raw, 0x178)  # virtual+448 -> 017456ec
    if not source:
        raise ValueError('ranking array has not been loaded')
    pointers, header, data, items = array(reader, source, 256)
    if not pointers:
        raise ValueError('ranking array is empty; previous successful data must be retained')
    if len(set(pointers)) != len(pointers):
        raise ValueError('ranking array contains repeated record pointers')
    output.mkdir(parents=True, exist_ok=False)
    files = {}

    def save(name, blob):
        filename = name + '.bin'
        (output / filename).write_bytes(blob)
        files[name] = {'file': filename, 'length': len(blob),
                       'sha256': hashlib.sha256(blob).hexdigest()}

    save('layer', layer_raw)
    save('array', header)
    save('array-data', data)
    save('row-pointers', items)
    rows, errors = [], []
    selected = pointers[:max_rows]
    raws = []
    for start in range(0, len(selected), 128):
        raws.extend(reader.read_many((pointer, 0xb0) for pointer in selected[start:start+128]))
    for index, (pointer, raw) in enumerate(zip(selected, raws)):
        prefix = f'row-{index:03d}'
        try:
            if u64(raw) - reader.base + GBASE != ROW:
                raise ValueError('ranking record type mismatch')
            uid = reader.string(raw, 0x18)
            rank = struct.unpack_from('<i', raw, 0x34)[0]
            if not uid or rank < 1:
                raise ValueError('ranking record lacks a valid player identity/rank')
            save(prefix, raw)
            # Only ranking display fields and the identity needed to link defense.
            # Do not follow imageUrl or unrelated account/profile fields.
            for label, offset in [('player-id', 0x18), ('name', 0x58), ('league-phase', 0x78)]:
                value = reader.string(raw, offset)
                value.decode('utf8', 'strict')
                save(prefix + '-' + label, value)
            current = typed(reader, pointer, 0xb0, ROW)
            if reader.string(current, 0x18) != uid or current[0x30:0x38] != raw[0x30:0x38]:
                raise ValueError('ranking record changed during capture')
            rows.append({'index': index, 'prefix': prefix, 'objectAddress': pointer, 'status': 'captured'})
        except (ValueError, RuntimeError) as error:
            errors.append({'index': index, 'reason': str(error)})
    final, *_ = array(reader, source, 256)
    if (final != pointers or u64(reader.read(director + 0xf0, 8)) != scene
            or u64(reader.read(layer + 0x178, 8)) != source):
        raise ValueError('PVP ranking source changed during capture')
    result = {
        'schemaVersion': 1, 'sourceKind': 'native-visible-pvp-ranking',
        'captureVersion': 'pvp-ranking-v1',
        'capturedAt': datetime.now(timezone.utc).isoformat(),
        'gameVersion': '12.4.2', 'moduleSha256': reader.module_sha,
        'pid': reader.pid, 'moduleBase': reader.base, 'arrayAddress': source,
        'scopeLabel': scope_label, 'loadedCount': len(pointers),
        'capturedCount': len(rows), 'maxRows': max_rows,
        'loadedArrayFullyCaptured': len(rows) == len(pointers) and not errors,
        'wholeRankingComplete': False, 'consistent': True,
        'rows': rows, 'errors': errors, 'files': files,
        'fieldEvidence': ['reports/ghidra/ranking-data-parser-and-table-source.txt',
                          'reports/ghidra/ranking-source-and-field-getters.txt'],
    }
    (output / 'capture.private.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-rows', type=int, default=100)
    parser.add_argument('--scope-label', help='Label read directly from the visible ranking screen; never inferred from rank')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    out = args.output or ROOT / 'data/research/runtime.private' / (
        'pvp-ranking-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:6])
    if not out.resolve().is_relative_to((ROOT/'data/research/runtime.private').resolve()):
        raise ValueError('raw ranking copies must stay under runtime.private')
    with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe', 'emulator-5554', 180) as reader:
        reader.expected_module_sha = NEW_SHA
        reader.refresh()
        result = capture(reader, out, args.max_rows, args.scope_label)
    print(json.dumps({k: result[k] for k in ['loadedCount', 'capturedCount', 'loadedArrayFullyCaptured', 'wholeRankingComplete']}))
    print('Saved', out.relative_to(ROOT))
