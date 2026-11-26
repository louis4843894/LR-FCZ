"""Inspect only retained caches of the verified GuildWarDataManager.

Reports types/counts and bounded container relationships, without credentials,
player identifiers, object dumps or changing the current screen.
"""
import hashlib
import json
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from native_elf import NativeELF
from native_layouts import NEW_SHA
from bounded_equipment_reader import Reader
from equipment_memory import GBASE, u64
from read_defense_team import typed, dictionary
from read_guild_members import array


def inspect(reader):
    elf = NativeELF(ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so')
    if reader.module_sha != NEW_SHA or elf.sha256 != NEW_SHA:
        raise ValueError('verified module required')
    manager = u64(reader.read(reader.base+0x200a320-GBASE, 8))
    raw = typed(reader, manager, 0xc0, 0x1eb5c00)
    seen = set()
    nodes = 0

    def describe(pointer, depth=0):
        nonlocal nodes
        if pointer in seen:
            return {'state': 'already_observed'}
        if nodes >= 512:
            raise ValueError('cache observation bound')
        seen.add(pointer)
        nodes += 1
        ap = u64(reader.read(pointer, 8))-reader.base+GBASE
        try:
            name = elf.type_name(ap)
        except (ValueError, UnicodeError, struct.error):
            return {'state': 'unresolved_type', 'vtable': hex(ap)}
        result = {'type': name, 'vtable': hex(ap)}
        if depth >= 3:
            result['childrenNotInspected'] = True
            return result
        if ap == 0x1f6a690:
            header = typed(reader, pointer, 0x28, ap)
            rows = dictionary(reader, pointer, 128)
            result.update(count=len(rows), rawKeyKind=struct.unpack_from('<I', header, 0x20)[0],
                          children=[])
            for numeric, value, entry in rows:
                # The key union is not assigned a meaning before writer proof.
                key = {'rawSmallInteger': numeric} if 0 <= numeric < 10000 else {
                    'keyFingerprint': hashlib.sha256(entry[:256].split(b'\0', 1)[0]).hexdigest()[:16]}
                result['children'].append({**key, 'value': describe(value, depth+1)})
        elif ap == 0x1f6a7f8:
            pointers, *_ = array(reader, pointer, 128)
            result.update(count=len(pointers), children=[describe(p, depth+1) for p in pointers])
        return result

    fields = {}
    for offset in [0x18, 0x20, 0x28, 0x38, 0x40, 0x48, 0x50, 0x78, 0x80, 0x88, 0x90]:
        pointer = u64(raw, offset)
        fields[hex(offset)] = describe(pointer) if pointer else {'state': 'not_loaded'}
    if typed(reader, manager, 0xc0, 0x1eb5c00) != raw:
        raise ValueError('manager changed during observation')
    return {'checkedAt': datetime.now(timezone.utc).isoformat(), 'moduleSha256': NEW_SHA,
            'rootType': elf.type_name(0x1eb5c00), 'fields': fields,
            'observedObjects': nodes, 'readBytes': reader.read_bytes,
            'scope': 'Confirmed retained fields; nested containers bounded to depth 3 / 512 objects / 128 entries.',
            'credentialsRead': False, 'networkRequests': 0}


if __name__ == '__main__':
    with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe', 'emulator-5554', 120) as reader:
        reader.expected_module_sha = NEW_SHA
        reader.refresh()
        report = inspect(reader)
    (ROOT/'reports/guild-runtime-storage-caches.json').write_text(
        json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(json.dumps(report))
