"""Read confirmed guild/selected-defender roots; retain aliases and types only.

No session extraction, API call, game function invocation or memory dump.
Offsets/getters: guild-battle-selected-member-getters-1242.txt and
guild-battle-manager-and-selection-roots-1242.txt.
"""
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from bounded_equipment_reader import Reader
from equipment_memory import ROOT, GBASE, u64

sys.path.insert(0, str(ROOT/'scripts'))
from native_elf import NativeELF
from native_layouts import NEW_SHA


def inspect(reader):
    elf = NativeELF(ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so')
    if elf.sha256 != NEW_SHA or reader.module_sha != NEW_SHA:
        raise ValueError('unverified module')
    for getter in [0x00c9c9fc, 0x01349688, 0x01349698, 0x0134840c]:
        offset = elf.offset(getter)
        if reader.read(reader.base+getter-GBASE, 8) != elf.data[offset:offset+8]:
            raise ValueError('verified getter differs in loaded module')
    rows = json.loads(gzip.decompress((ROOT/'data/site-display/guilds.json.gz').read_bytes()))['data']['guilds']
    names = {g['alias']: {'name': g['name'], 'rank': g['rank']} for g in rows}
    result = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'moduleSha256': NEW_SHA,
              'credentialsRead': False, 'gameHttpRequests': 0, 'rawMemoryRetained': False, 'guilds': []}
    manager = u64(reader.read(reader.base+0x0200a320-GBASE, 8))
    if not manager or u64(reader.read(manager, 8))-reader.base+GBASE != 0x01eb5c00:
        raise ValueError('guild war manager not initialized or type differs')
    for side, offset in [('ally', 0x18), ('opponent', 0x20)]:
        info = u64(reader.read(manager+offset, 8))
        row = {'side': side, 'modelPresent': bool(info)}
        if info:
            if u64(reader.read(info, 8))-reader.base+GBASE != 0x01eb6020:
                raise ValueError('guild info receiver type differs')
            # 0134840c copies std::string from GuildWarInfoModel+0x50.
            raw = reader.read(info+0x50, 24)
            size = u64(raw, 8) if raw[0] & 1 else raw[0] >> 1
            if not 1 <= size <= 128:
                raise ValueError('guild identifier string bound')
            alias = hashlib.sha256(reader.string(raw, 0)).hexdigest()[:20]
            row.update({'alias': alias, 'rankedGuild': names.get(alias), 'identifierRetained': False})
        result['guilds'].append(row)
    preset = u64(reader.read(reader.base+0x01fd7b40-GBASE, 8))
    selected = {'presetPresent': bool(preset)}
    if preset:
        if u64(reader.read(preset, 8))-reader.base+GBASE != 0x01dfebb0:
            raise ValueError('BattlePresetDataManager receiver type differs')
        # vtable+0x190 / 00c9c9fc returns this+0xf8.
        member = u64(reader.read(preset+0xf8, 8))
        selected['memberPresent'] = bool(member)
        if member:
            ap = u64(reader.read(member, 8))-reader.base+GBASE
            selected.update({'vtable': hex(ap), 'rttiName': elf.type_name(ap)})
            if ap == 0x01eb60e0:
                deck = reader.read(member+0x80, 8)
                tower = int.from_bytes(reader.read(member+0x88, 4), 'little')
                selected.update({'deckIdentifierRead': True, 'deckIdentifierHash': hashlib.sha256(deck).hexdigest(),
                                 'deckIdentifierRetained': False, 'towerCode': tower})
    result['selectedDefender'] = selected
    return result


if __name__ == '__main__':
    with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe', 'emulator-5554', 90) as reader:
        reader.expected_module_sha = NEW_SHA
        reader.refresh()
        result = inspect(reader)
    (ROOT/'reports/guild-defense-selected-context-check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps(result, ensure_ascii=False))
