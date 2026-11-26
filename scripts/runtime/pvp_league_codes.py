"""Prove request league codes by matching the game's cache to saved UI sources.

The output contains codes/counts/hashes, never player IDs or credentials.
No guessed league names, UI navigation, injection or HTTP requests.
"""
import argparse,hashlib,json,sqlite3,sys
from datetime import datetime,timezone
from pathlib import Path
from bounded_equipment_reader import Reader
from equipment_memory import ROOT,GBASE,u64
from read_defense_team import typed
from read_guild_members import array
from native_layouts import NEW_SHA

OUTPUT=ROOT/'data/research/runtime.private/pvp-league-codes.private.json'
from pvp_scope_policy import SCOPES,LABELS as SCOPE_LABELS,canonical_scope,matches_scope


def verified_mappings():
    proof=json.loads(OUTPUT.read_bytes())
    if proof['moduleSha256']!=NEW_SHA:raise ValueError('unverified phase-code module')
    return [{**m,'label':canonical_scope(m['label'])} for m in proof['mappings'] if matches_scope(m['label'],'all')]


def include_subdivisions():
    """0174f3dc explicitly builds all 14 phase strings, including inline SSO.

    MASTER/GOLD 1 and 2 are assembled from immediates, so a rodata-only search
    misses them. Request/response validation remains the existing normal path.
    """
    sys.path.insert(0,str(ROOT/'scripts'))
    from native_elf import NativeELF
    elf=NativeELF(ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so')
    if elf.sha256!=NEW_SHA:raise ValueError('unverified phase construction module')
    report=ROOT/'reports/ghidra/pvp-subdivision-ui-and-gear-manager.txt';text=report.read_text(encoding='utf8')
    for required in ['FUNCTION 0174f3dc','0x5f52455453414d','0x325f52455453414d','0x335f52455453414d','0x315f','0x325f','0x335f','0x444c4f47','lVar4 != 0x150']:
        if required not in text:raise ValueError('native 14-phase construction evidence incomplete')
    old=json.loads(OUTPUT.read_bytes());rows=[]
    language=ROOT/'data/extracted/lr_20261116T212608096_7b99bdd0/assets/res/tutorial_res/db/lang_etc/lang_etc.ndb'
    with sqlite3.connect(language.resolve().as_uri()+'?mode=ro',uri=True) as db:
        for scope in SCOPES:
            code=scope['phaseCode'];key='PVP_'+code+'_nm'
            translated=db.execute("SELECT msg FROM lang_etc WHERE dataCode=? AND language='zh-Hant'",(key,)).fetchone()
            if not translated or not translated[0].startswith(scope['group']):raise ValueError('phase name translation differs')
            rows.append({**scope,'minimumPlayers':1,'translationKey':key,'translatedPhaseName':translated[0],
                'method':'native-14-phase-array-and-local-translation','nativeFunction':'0174f3dc','wholeTierCoverageConfirmed':False,
                'codeEvidence':'0174f3dc builds 14 SSO phase strings at this+f8 (stride18); 01750af0 /pvp/league/rank/%s; 01750c2c validates response phase'})
    # Keep historical code proofs for offline parsing, never request lower tiers.
    rows.extend(m for m in old['mappings'] if m['phaseCode'] in ['SILVER_3','BRONZE'])
    old.update(mappings=rows,extendedAt=datetime.now(timezone.utc).isoformat(),subdivisionConstructionReportSha256=hashlib.sha256(report.read_bytes()).hexdigest())
    return old


def include_native_groups():
    """Extend UI-matched codes with exact native enum-table/translation evidence.

    The table is used by PvpTestLayer 018d90b0 to create phase widgets via
    01752630. It proves the phase literals, not whole-tier ranking coverage.
    Each actual normal response must independently echo the requested code.
    """
    sys.path.insert(0,str(ROOT/'scripts'))
    from native_elf import NativeELF
    elf=NativeELF(ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so')
    if elf.sha256!=NEW_SHA:raise ValueError('native phase-table module differs')
    proof=json.loads(OUTPUT.read_bytes());existing={m['label']:m for m in verified_mappings()}
    table=['BRONZE','SILVER_3','GOLD_3','DIAMOND_3','MASTER_3','LEGEND']
    labels=['青銅','白銀','黃金','鑽石','大師','傳奇']
    language=ROOT/'data/extracted/lr_20261116T212608096_7b99bdd0/assets/res/tutorial_res/db/lang_etc/lang_etc.ndb'
    with sqlite3.connect(language.resolve().as_uri()+'?mode=ro',uri=True) as db:
        for index,(code,label) in enumerate(zip(table,labels)):
            slot=0x1f404b0+index*8;literal=elf.ptr(slot)
            if elf.cstring(literal)!=code:raise ValueError('native phase-table entry differs')
            if label in existing:continue
            key='PVP_'+code+'_nm';row=db.execute("SELECT msg FROM lang_etc WHERE dataCode=? AND language='zh-Hant'",(key,)).fetchone()
            if not row or not row[0].startswith(label):raise ValueError('native phase translation differs')
            existing[label]={'phaseCode':code,'label':label,'minimumPlayers':1,
                             'method':'exact-native-phase-table-and-local-translation',
                             'nativeTableSlot':f'{slot:08x}','nativeLiteral':f'{literal:08x}',
                             'translationKey':key,'translatedPhaseName':row[0],
                             'wholeTierCoverageConfirmed':False,
                             'codeEvidence':'018d90b0 loads 01f404b0[index] -> 01752630; normal request 01750af0 and response 01750c2c must echo phase code'}
    proof['mappings']=[existing[label] for label in labels[::-1]]
    proof['extendedAt']=datetime.now(timezone.utc).isoformat()
    proof['nativePhaseTableReportSha256']=hashlib.sha256((ROOT/'reports/ghidra/pvp-ranking-phase-table-consumer.txt').read_bytes()).hexdigest()
    return proof


def discover(reader):
    if reader.module_sha!=NEW_SHA:raise ValueError('unverified phase-code module')
    with sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        sources=[json.loads(p) for p, in db.execute('SELECT payload FROM ranking_snapshots')]
    sources=[s for s in sources if s['sourceKind']=='verified-native-pvp-ranking']
    manager=u64(reader.read(reader.base+0x2028eb0-GBASE,8));typed(reader,manager,8,0x1f157e0)
    dictionary=u64(reader.read(manager+0x78,8));header=typed(reader,dictionary,0x28,0x1f6a690)
    head=node=u64(header,0x18);seen=set();mappings=[]
    while node:
        if node in seen or len(seen)>=32:raise ValueError('phase-cache traversal bound')
        seen.add(node);entry=reader.read(node,0x128);code=entry[:256].split(b'\0',1)[0].decode('ascii')
        items,*_=array(reader,u64(entry,0x108),256);uids=[]
        for start in range(0,len(items),128):
            rows=reader.read_many((p,0x30) for p in items[start:start+128])
            for row in rows:
                if u64(row)-reader.base+GBASE!=0x1e53d58:raise ValueError('native ranking row type differs')
                uids.append(reader.string(row,0x18).decode('utf8'))
        matches=[s for s in sources if {p['playerId'] for p in s['players']}==set(uids)]
        labels={s['scope']['label'] for s in matches}
        if len(labels)==1:
            source=matches[-1]
            mappings.append({'phaseCode':code,'label':source['scope']['label'],'count':len(items),
                             'nativeSourceId':source['snapshotId'],'nativeSourceSha256':source['sourceCaptureSha256'],
                             'uidSetSha256':hashlib.sha256(json.dumps(sorted(set(uids))).encode()).hexdigest()})
        node=u64(entry,0x120)
    if u64(reader.read(dictionary+0x18,8))!=head:raise ValueError('phase cache changed during verification')
    if {m['label'] for m in mappings}!={'傳奇','青銅'} or {m['phaseCode'] for m in mappings}!={'LEGEND','BRONZE'}:
        raise ValueError('expected observed ranking scopes were not proved')
    return {'moduleSha256':NEW_SHA,'verifiedAt':datetime.now(timezone.utc).isoformat(),
            'method':'exact-native-ranking-uid-set-vs-ui-confirmed-scope',
            'codeEvidence':'0174d004 -> PvpMainDataManager virtual+58 / 01751700 -> this+30; 01750af0 uses same phase key in this+78 cache and /pvp/league/rank/%s',
            'mappings':mappings}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--include-native-groups',action='store_true');parser.add_argument('--include-subdivisions',action='store_true');args=parser.parse_args()
    if args.include_subdivisions:result=include_subdivisions()
    elif args.include_native_groups:result=include_native_groups()
    else:
        with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',120) as reader:
            reader.expected_module_sha=NEW_SHA;reader.refresh();result=discover(reader)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (ROOT/'reports/pvp-league-code-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'phaseCodesVerified':len(result['mappings']),'credentialsRead':False}))
