"""Index every literal /guild and /event/guild route in the verified module.

One bounded pass over .text finds ADR/ADRP+ADD references and known HTTP helper
calls. Method hints are function-level candidates, not proof a route is safe.
This script never sends a request or modifies the Ghidra project.
"""
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from native_elf import NativeELF

SHA = '1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0'
HTTP = {0x0105a004: 'GET wrapper', 0x01058b84: 'POST wrapper',
        0x01a4be64: 'common dispatcher; method requires data-flow proof'}


def index():
    elf = NativeELF(ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so')
    if elf.sha256 != SHA:
        raise ValueError('verified module required')
    si = struct.unpack_from('<H', elf.data, 62)[0]
    ns = elf.sections[si]
    names = elf.data[ns[4]:ns[4]+ns[5]]
    sections = {names[s[0]:names.find(b'\0', s[0])].decode(): s for s in elf.sections}
    data = sections['.rodata']
    strings = memoryview(elf.data)[data[4]:data[4]+data[5]]
    targets = {}
    # Complete C strings only: /guild/list inside /event/mission/guild/list
    # must not become an invented independent literal or request entry.
    for m in re.finditer(rb'(?<=\x00)(/[\x21-\x7e]{1,220})\x00', strings):
        path = m.group(1)
        if b'guild' in path.lower():
            targets[elf.address(data[4]+m.start(1))] = path.decode('ascii')
    text = sections['.text']
    if text[5] > 24*1024*1024 or text[5] % 4:
        raise ValueError('code section bound')
    code = memoryview(elf.data)[text[4]:text[4]+text[5]]
    pages = {a & ~4095 for a in targets}
    refs = {a: [] for a in targets}
    calls = {}
    for i, (word,) in enumerate(struct.iter_unpack('<I', code)):
        pc = text[3]+elf.image_base+i*4
        if word & 0x7c000000 == 0x14000000:
            imm = word & 0x3ffffff
            if imm & 0x2000000:
                imm -= 0x4000000
            destination = pc+imm*4
            if destination in HTTP:
                calls.setdefault(elf.function_start(pc), []).append(
                    {'instruction': hex(pc), 'helper': hex(destination), 'hint': HTTP[destination],
                     'encoding': 'BL' if word & 0x80000000 else 'B (tail transfer)'})
        op = word & 0x9f000000
        if op not in (0x90000000, 0x10000000):
            continue
        imm = ((word >> 29) & 3) | (((word >> 5) & 0x7ffff) << 2)
        if imm & 0x100000:
            imm -= 0x200000
        base = (pc & ~4095)+(imm << 12) if op == 0x90000000 else pc+imm
        if op == 0x10000000:
            if base in refs:
                refs[base].append({'instruction': hex(pc), 'function': hex(elf.function_start(pc)), 'encoding': 'ADR'})
            continue
        if base not in pages:
            continue
        register = word & 31
        for distance in range(1, 7):
            at = (i+distance)*4
            if at+4 > len(code):
                break
            following = struct.unpack_from('<I', code, at)[0]
            if following & 0xffc00000 == 0x91000000 and ((following >> 5) & 31) == register:
                target = base+((following >> 10) & 4095)
                if target in refs:
                    refs[target].append({'instruction': hex(pc), 'add': hex(pc+distance*4),
                                         'function': hex(elf.function_start(pc)), 'encoding': 'ADRP+ADD'})
                    break
            if following & 0xfc000000 == 0x94000000 and register < 19:
                break
            if following & 0xfc000000 == 0x14000000 or following & 0xfffffc1f in (0xd61f0000, 0xd65f0000):
                break
            if following & 31 == register and (
                following & 0x9f000000 in (0x90000000, 0x10000000)
                or following & 0x1f000000 in (0x11000000, 0x12000000, 0x0a000000, 0x0b000000)
                or following & 0x3b000000 == 0x39000000 and following & 0x00400000):
                break
    rows = []
    for address, path in sorted(targets.items()):
        references = refs[address]
        for ref in references:
            ref['httpHelperCallsInFunction'] = calls.get(int(ref['function'], 16), [])
        rows.append({'literal': path, 'address': hex(address), 'references': references})
    report = {'moduleSha256': SHA, 'bytesOfCodeChecked': len(code),
              'scope': 'Literal guild routes, exact PC-relative references and function-level HTTP helper hints; constructed routes/indirect dispatch may be absent.',
              'routes': rows, 'networkRequests': 0}
    (ROOT/'reports/guild-all-route-index.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    return report


if __name__ == '__main__':
    report = index()
    print(json.dumps({'routes': len(report['routes']), 'references': sum(len(r['references']) for r in report['routes']),
                      'guildCore': [r for r in report['routes'] if r['literal'].startswith('/guild/') and
                                    any(k in r['literal'] for k in ('confirm', 'list', 'search'))]}))
