"""Prepare read-only guild-war JSON boundaries after the operator switches account.

No UI navigation, battle entry, registration, deck save, or POST. Unknown
response bodies stay in RAM; only key/type shapes and hashes are recorded.
"""
import argparse,hashlib,json,re,time
from datetime import datetime,timezone
from pvp_session import Reader,NEW_SHA,ROOT,load_session
from fetch_ranked_pvp_response import normal_json,AcquisitionStopped


def shape(value,depth=0):
    if isinstance(value,dict):
        def field(key):
            if len(key)>36 or re.fullmatch('[a-fA-F0-9]{16,}',key) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,35}',key):return '<dynamic-key>'
            return key
        return {field(k):shape(v,depth+1) for k,v in list(value.items())[:60]} if depth<4 else [field(k) for k in list(value)[:60]]
    if isinstance(value,list):return {'length':len(value),'firstShape':shape(value[0],depth+1) if value else None}
    return type(value).__name__


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--use-authorized-runtime-session',action='store_true');args=p.parse_args()
    if not args.use_authorized_runtime_session:p.error('explicit local guild-session authorization required')
    try:
        with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',120) as reader:
            reader.expected_module_sha=NEW_SHA;reader.refresh();session=load_session(reader,authorized=True)
        reports=[]
        for path in ('/guildwar/main','/guildwar/defencedeck'):
            raw,doc=normal_json(session,path,purpose='guild-war-bootstrap')
            reports.append({'path':path,'capturedAt':datetime.now(timezone.utc).isoformat(),'responseSha256':hashlib.sha256(raw).hexdigest(),'shape':shape(doc)})
            time.sleep(.5)
        folder=ROOT/'data/research/runtime.private/guild-top100-session';folder.mkdir(exist_ok=True)
        (folder/'guildwar-read-shapes.private.json').write_text(json.dumps(reports,indent=2)+'\n',encoding='utf8')
        print(json.dumps({'normalReadCompleted':True,'responses':reports,'credentialsPersisted':False}))
    except Exception as error:
        print(json.dumps({'normalReadCompleted':False,'reason':str(error) if isinstance(error,AcquisitionStopped) else 'guildwar_context_or_shape_failed','credentialsPersisted':False}));raise SystemExit(1)
