"""Reproduce the native PVP request chain from the saved verified module.

No device access, credentials, HTTP requests, injection, or UI automation.
The result proves code relationships, not successful direct acquisition.
"""
import hashlib,json,struct
from pathlib import Path
from native_elf import NativeELF
from native_layouts import NEW_SHA

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so'


def verify(module=MODULE):
    elf=NativeELF(module)
    if elf.sha256!=NEW_SHA:raise ValueError('unverified native request module')
    checks=[
        elf.type_name(0x1f150f8)=='17PvpMainController',
        elf.type_name(0x1e7d468)=='17FriendDataManager',
        elf.type_name(0x1ef0bd8)=='14MainDataLoader',
        elf.ptr(0x1f154e0+0x28)==0x1747410,
        elf.ptr(0x1e7d468+0x180)==0x113b5a0,
        elf.ptr(0x1e7d468+0x188)==0x113b5a8,
        elf.cstring(0x7e89c2)=='/player/units/team/%s/uid/%s',
        elf.cstring(0x7dae58)=='equip',
        elf.cstring(0x7d9df8)=='cookie: %s=%s; udid=%s;',
        elf.cstring(0x80e594)=='LF_AC',
        elf.cstring(0x7dd881)=='playerUnitTeamGroupMap',
        elf.cstring(0x80ab06)=='pvpteam',
        elf.adr_references(0x174733c)==[{'adr':0x17472f0,'functionStart':0x174720c}],
    ]
    # The callback interface thunk subtracts exactly 0x128, then branches to
    # the owning controller method. This is this class's own vtable slot.
    off=elf.offset(0x1747410)
    checks.append(elf.data[off:off+8].hex()=='00a004d17effff17')
    for getter,expected in [(0x113b5a0,'006040f9c0035fd6')]:
        off=elf.offset(getter);checks.append(elf.data[off:off+8].hex()==expected)
    if not all(checks):raise ValueError('native request chain evidence differs')
    files=['pvp-request-confirmed-clean.txt','pvp-http-request-parameters.txt',
           'pvp-http-request-create.txt','pvp-native-request-entry.txt',
           'pvp-http-worker-and-unit-group.txt']
    reports={f:hashlib.sha256((ROOT/'reports/ghidra'/f).read_bytes()).hexdigest() for f in files}
    return {
        'moduleSha256':NEW_SHA,'gameVersion':'12.4.2',
        'chain':['PvpRankingCell+0x168 callback receiver',
                 'PvpMainController secondary vtable +0x28 -> 01747410 (this -= 0x128)',
                 '0174720c(targetUid) -> 015eab84(MainDataLoader)',
                 '01a4be64 -> 01a4c298 -> 01a4d184 -> 01b0142c(normal HTTP queue)',
                 '015eac0c(response bytes -> JSON -> FriendModel)',
                 'FriendDataManager virtual+0x188 -> 0113b5a8 -> this+0xc0'],
        'pathTemplate':'/player/units/team/equip/uid/{targetUid}',
        'requestMode':0,
        'responseTeamPath':'result.playerUnitTeamGroupMap.pvpteam',
        'pvpTeamKind':5,'ordinaryTeamKeys':['team1','team2','team3','team4','team5'],
        'sessionDependency':{'header':'Cookie','name':'LF_AC',
                             'producer':'01058da8 -> 01a33288 / 01a32fe4',
                             'verifierReadsCredentials':False},
        'runtimeAcquisitionTestPerformedByThisVerifier':False,
        'requiredRuntimeParameter':'existing authenticated runtime session (LF_AC and normal client context)',
        'verifierHttpRequestsSent':0,
        'reportSha256':reports,
    }


if __name__=='__main__':
    report=verify()
    (ROOT/'reports/pvp-native-request-code-evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'nativeRequestChainVerified':True,'verificationScope':'static-native-module-only',
                      'runtimeTestPerformed':False,'httpRequestsSent':0}))
