"""Inventory Guild RTTI classes, virtual slots and known storage literals.

Only the verified saved native module is read. Class names identify candidates,
not proof of field semantics or runtime content. No auto-analysis or requests.
"""
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from native_elf import NativeELF

SHA = '1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0'


def inventory():
    elf = NativeELF(ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so')
    if elf.sha256 != SHA:
        raise ValueError('verified module required')
    reverse = {}
    for slot, target in elf.relative.items():
        reverse.setdefault(target, []).append(slot)
    string_index = struct.unpack_from('<H', elf.data, 62)[0]
    name_section = elf.sections[string_index]
    section_names = elf.data[name_section[4]:name_section[4]+name_section[5]]
    code_ranges = [(s[3]+elf.image_base, s[3]+elf.image_base+s[5]) for s in elf.sections
                   if section_names[s[0]:section_names.find(b'\0', s[0])] in (b'.text', b'.plt')]

    def slots(table):
        result = {}
        for offset in range(0, 0x60, 8):
            target = elf.ptr(table+offset)
            if not any(start <= target < end for start, end in code_ranges):
                break
            result[hex(offset)] = hex(target)
        return result
    classes = []
    # A lookbehind leaves the NUL delimiter available for the adjacent name.
    for match in re.finditer(rb'(?<=\x00)([0-9]{1,3}[A-Za-z0-9_]*Guild[A-Za-z0-9_]*)\x00', elf.data):
        name = match.group(1).decode()
        address = elf.address(match.start(1))
        types = {slot - 8 for slot in reverse.get(address, [])}
        tables = sorted(slot + 8 for typ in types for slot in reverse.get(typ, [])
                        if elf.ptr(slot - 8) == 0)
        classes.append({'rttiName': name, 'nameAddress': hex(address),
                        'vtableAddressPoints': [hex(t) for t in tables],
                        'virtualSlots': {hex(t): slots(t) for t in tables}})
    report = {'moduleSha256': SHA,
              'scope': 'Exact Guild RTTI names and relocated vtables; semantic roles require constructor/getter evidence.',
              'slotScope': 'First 0x60 bytes, stopping at a non-code slot; not a claim of complete vtable length.',
              'classes': classes, 'networkRequests': 0, 'runtimeMemoryRead': False}
    (ROOT/'reports/guild-class-storage-inventory.json').write_text(
        json.dumps(report, indent=2)+'\n', encoding='utf8')
    return report


if __name__ == '__main__':
    report = inventory()
    candidates = [r for r in report['classes']
                  if re.search(r'Manager|Model|Data|Loader|Container|History|DB', r['rttiName'])]
    print(json.dumps({'classes': len(report['classes']), 'storageCandidates': [
        {k: v for k, v in c.items() if k != 'virtualSlots'} for c in candidates]}))
