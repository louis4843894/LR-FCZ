"""Inspect the verified GuildDBContainer root and three values per container.

Samples identify storage candidates; they do not establish whole-table coverage
or infer player data from a class/file name. No credentials or object dumps.
"""
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
from read_defense_team import typed


def inspect(r):
    elf = NativeELF(ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so')
    if elf.sha256 != NEW_SHA or r.module_sha != NEW_SHA:
        raise ValueError('verified module required')
    ptr = u64(r.read(r.base+0x1fd7588-GBASE, 8))
    result = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'moduleSha256': NEW_SHA,
              'global': '0x1fd7588', 'initialized': bool(ptr), 'fields': {},
              'credentialsRead': False, 'networkRequests': 0}
    if not ptr:
        return result
    body = typed(r, ptr, 0x70, 0x1e4b938)

    def kind(address):
        ap = u64(r.read(address, 8))-r.base+GBASE
        return {'type': elf.type_name(ap), 'vtable': hex(ap)}

    for offset in range(0x18, 0x70, 8):
        target = u64(body, offset)
        row = kind(target) if target else {'state': 'not_loaded'}
        if target and row['vtable'] == '0x1f6a690':
            header = typed(r, target, 0x28, 0x1f6a690)
            node = u64(header, 0x18)
            initial = node
            seen = set()
            samples = []
            while node and len(samples) < 3:
                if node in seen:
                    raise ValueError('template cache cycle')
                seen.add(node)
                entry = r.read(node, 0x128)
                samples.append(kind(u64(entry, 0x108)))
                node = u64(entry, 0x120)
            if u64(r.read(target+0x18, 8)) != initial:
                raise ValueError('template cache changed')
            row.update(sampledValues=len(samples), valueTypes=samples,
                       moreEntriesExist=bool(node), rawKeyKind=struct.unpack_from('<I', header, 0x20)[0])
        elif target and row['vtable'] == '0x1f6a7f8':
            header = typed(r, target, 0x20, 0x1f6a7f8)
            data = r.read(u64(header, 0x18), 16)
            count, capacity = struct.unpack_from('<II', data)
            if count > capacity or capacity > 100000:
                raise ValueError('template array bounds')
            size = min(count, 3)
            pointers = r.read(u64(data, 8), size*8) if size else b''
            row.update(count=count, valueTypes=[kind(u64(pointers, i*8)) for i in range(size)])
        result['fields'][hex(offset)] = row
    if typed(r, ptr, 0x70, 0x1e4b938) != body:
        raise ValueError('template root changed')
    return result


if __name__ == '__main__':
    with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe', 'emulator-5554', 120) as r:
        r.expected_module_sha = NEW_SHA
        r.refresh()
        report = inspect(r)
    (ROOT/'reports/guild-template-storage-root-check.json').write_text(
        json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(json.dumps(report))
