"""Reconcile existing native evidence; never issue a request or invoke game code."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from native_elf import NativeELF

ROOT = Path(__file__).resolve().parents[1]
SHA = '1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0'


def main():
    sources = {}
    text = {}
    for name in ['guildwar-other-context-read-boundaries-1242.txt', 'guild-battle-response-and-input-1242.txt',
                 'guild-battle-selected-deck-source-1242.txt', 'guild-battle-manager-and-selection-roots-1242.txt',
                 'guild-battle-selected-member-getters-1242.txt', 'guild-battle-selection-and-transition-1242.txt',
                 'guild-selected-defense-ui-writers-1242.txt']:
        file = ROOT/'reports/ghidra'/name
        content = file.read_bytes()
        text[name] = content.decode('utf8')
        sources[name] = hashlib.sha256(content).hexdigest()
        if 'REPORT_COMPLETE' not in text[name]:
            raise ValueError('incomplete native evidence')
    elf = NativeELF(ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so')
    if elf.sha256 != SHA:
        raise ValueError('verified module required')
    assert elf.cstring(0x007d5858) == '/guildwar/battle/enter'
    assert elf.cstring(0x007b91c3) == 'MEMBER_MODEL'
    assert elf.cstring(0x007de8fb) == 'opponentBattlePlayerInfo'
    assert elf.cstring(0x007c8000) == 'playerUnitTeams'
    assert elf.cstring(0x007f8a5c) == '1'
    fortress_at = elf.offset(0x0080b92f)
    units_at = elf.offset(0x007f8a52)
    fields = [(elf.data[fortress_at:fortress_at+8]+bytes.fromhex('436f6465')).decode('ascii'),
              (0x64496b636564).to_bytes(6, 'little').decode('ascii'),
              (elf.data[units_at:units_at+8]+b's').decode('ascii')]
    assert fields == ['fortressCode', 'deckId', 'itemCodes']
    response = text['guild-battle-response-and-input-1242.txt']
    assert all(part in response for part in ['FUNCTION 0133d30c', '&UNK_007de8fb', '&UNK_007c8000', '&UNK_007f8a5c', '0x8e8', 'target_00e4ecf8', '0x660'])
    request = text['guildwar-other-context-read-boundaries-1242.txt']
    assert 'FUNCTION 0133d0f8' in request and 'target_01058b84' in request
    selection = text['guild-selected-defense-ui-writers-1242.txt'].split('FUNCTION 01333128')[0]
    assert all(part in selection for part in ['FUNCTION 0132acac', '&bStack_40', '0x198', 'lVar2'])
    getters = text['guild-battle-selected-member-getters-1242.txt']
    assert all(part in getters for part in ['FUNCTION 00c9c9fc', 'param_1 + 0xf8', 'FUNCTION 01349688', 'param_1 + 0x80', 'FUNCTION 01349698', 'param_1 + 0x88'])
    runtime = json.loads((ROOT/'reports/guild-defense-selected-context-check.json').read_text(encoding='utf8'))
    coverage = json.loads((ROOT/'reports/guild-top100-defense-coverage.json').read_text(encoding='utf8'))['summary']
    result = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'moduleSha256': SHA, 'sourceHashes': sources,
              'request': {'entry': '0133d0f8', 'method': 'POST', 'path': '/guildwar/battle/enter', 'callback': '0133d30c',
                          'bodyFields': fields, 'arbitraryGuildIdFieldEstablished': False, 'executed': False},
              'inputChain': {'uiSelection': '0132acac receives MEMBER_MODEL from event dictionary',
                             'receiver': 'BattlePresetDataManager global01fd7b40 / observed AP01dfebb0',
                             'setter': 'virtual+198 / 00c9ca04 retains one object at this+f8',
                             'getter': 'virtual+190 / 00c9c9fc returns this+f8',
                             'requestCaller': '01328cac uses selected object virtual+88 for deckId and +98 for fortressCode',
                             'matchingModel': 'GuildWarMemberModel AP01eb60e0: +88 -> 01349688 -> object+80; +98 -> 01349698 -> object+88',
                             'currentSelectedModelPresent': runtime['selectedDefender'].get('memberPresent', False),
                             'selectedRuntimeTypeDirectlyObserved': runtime['selectedDefender'].get('memberPresent', False)},
              'expectedResponse': {'path': 'opponentBattlePlayerInfo.playerUnitTeams["1"]', 'record': 'UnitData size0x8e8',
                                   'parser': '00e4ecf8', 'register': '00f617f8 / UnitManager global01fd41e8',
                                   'consumer': 'current BattleManager virtual+660; actual target depends on battle mode',
                                   'liveResponseCapturedThisRun': False},
              'currentVisibleContext': runtime['guilds'], 'top100Coverage': coverage,
              'newDefenseRecords': 0, 'gameHttpRequests': 0, 'credentialsRead': False,
              'limits': ['A battle-session response parser is not an established arbitrary-guild read API.',
                         'No missing target object or deckId was fabricated; current presence is recorded in inputChain.',
                         'The two inspected guild identities still match the accepted ally/opponent.',
                         '01333128 and the long-copy branch of 0134840c have decompiler PIC warnings; unrelated inlined blocks are not used as evidence.',
                         'Direct BL/B analysis does not exclude all indirect callers.',
                         'No battle, deck save, registration, permission change or refused player-team retry was performed.']}
    (ROOT/'reports/guild-defense-battle-boundary-review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'evidenceValidated': True, 'requestExecuted': False, 'expectedResponsePath': result['expectedResponse']['path'], 'selectedModelPresent': result['inputChain']['currentSelectedModelPresent'], 'newDefenseRecords': 0, 'coverage': coverage}))


if __name__ == '__main__':
    main()
