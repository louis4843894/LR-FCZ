"""Download only Rangerbook's public equipment evidence into a new local audit folder."""
import hashlib,json,uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
URLS={
    'gear.html':'https://rangerbook.warmycat.com/gear/',
    'equipment.json':'https://rangerbook.warmycat.com/res/v2/equipment.json',
    'equipment-effects.json':'https://rangerbook.warmycat.com/res/v2/equipment-effects.json',
    'gear-detail.js':'https://rangerbook.warmycat.com/assets/js/gear-detail.js?v=20261102-number-format1',
}

def main():
    out=ROOT/'data/research/external-reference'/('audit-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6])
    out.mkdir(parents=True,exist_ok=False)
    def download(item):
        name,url=item
        with urlopen(Request(url,headers={'User-Agent':'LR-local-reference-audit/1.0','Cache-Control':'no-cache'}),timeout=35) as r:
            if r.geturl().split('/')[2]!='rangerbook.warmycat.com':raise ValueError('unexpected source redirect')
            raw=r.read(20*1024*1024+1)
            if len(raw)>20*1024*1024:raise ValueError('source too large')
            content_type=r.headers.get('Content-Type')
        if name.endswith('.json'):
            data=json.loads(raw)
            key='effects' if name=='equipment-effects.json' else 'equipment'
            if not isinstance(data.get(key),list) or not data[key]:raise ValueError('unexpected equipment/effect format')
        (out/name).write_bytes(raw)
        return {'file':name,'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'contentType':content_type}
    with ThreadPoolExecutor(max_workers=3) as pool:files=list(pool.map(download,URLS.items()))
    manifest={'schemaVersion':1,'sourceKind':'public-rangerbook-reference-audit','fetchedAt':datetime.now(timezone.utc).isoformat(),'files':files}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print(json.dumps({'directory':str(out.relative_to(ROOT)),'files':[{'file':f['file'],'bytes':f['bytes'],'sha256':f['sha256']} for f in files]}))

if __name__=='__main__':main()
