"""Find exact callers of verified guild-war readers in the saved ARM64 code.

This checks BL/B encodings in .text, including callers not disassembled in the
targeted Ghidra project. ELF unwind bounds identify candidates for decompilation.
No process access, requests, project writes or auto-analysis.
"""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from native_elf import NativeELF

SHA = '1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0'
TARGETS = {
    0x0133bc78: 'registration fortress GET',
    0x0133c388: 'ally fortress GET',
    0x0133c590: 'opponent fortress GET',
    0x0133c678: 'own saved defense GET',
    0x013411ec: 'selected defender replay list POST (read purpose)',
    0x013402e0: 'guild contribution GET',
    0x0133adc0: 'guild war main GET',
    0x0134859c: 'GuildWarMemberModel constructor (tower defender)',
    0x013486b4: 'GuildWarMemberModel parser (tower defender)',
    0x01255908: 'guild confirm POST; not established as a defense reader',
}


def find():
    elf = NativeELF(ROOT / 'data/research/runtime.private/modules/libgame-12.4.2-pull.so')
    if elf.sha256 != SHA or struct.unpack_from('<H', elf.data, 18)[0] != 183:
        raise ValueError('verified ARM64 module required')
    string_index = struct.unpack_from('<H', elf.data, 62)[0]
    strings = elf.sections[string_index]
    names = elf.data[strings[4]:strings[4] + strings[5]]
    section = next(s for s in elf.sections
                   if names[s[0]:names.find(b'\0', s[0])] == b'.text')
    if section[5] > 24 * 1024 * 1024 or section[5] % 4:
        raise ValueError('code section bound')
    code = memoryview(elf.data)[section[4]:section[4] + section[5]]
    calls = []
    for index, (word,) in enumerate(struct.iter_unpack('<I', code)):
        if word & 0x7c000000 != 0x14000000:
            continue
        immediate = word & 0x3ffffff
        if immediate & 0x2000000:
            immediate -= 0x4000000
        pc = section[3] + elf.image_base + index * 4
        target = pc + immediate * 4
        if target not in TARGETS:
            continue
        calls.append({'instruction': hex(pc), 'functionStart': hex(elf.function_start(pc)),
                      'target': hex(target), 'purpose': TARGETS[target],
                      'encoding': 'BL' if word & 0x80000000 else 'B'})
    report = {'moduleSha256': SHA, 'bytesOfCodeChecked': len(code),
              'method': 'Exact ARM64 BL/B in .text; ELF unwind function boundaries',
              'targets': {hex(k): v for k, v in TARGETS.items()}, 'references': calls,
              'networkRequests': 0, 'indirectCallsExcluded': True}
    (ROOT / 'reports/guildwar-reader-callers.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return report


if __name__ == '__main__':
    print(json.dumps(find(), ensure_ascii=False))
