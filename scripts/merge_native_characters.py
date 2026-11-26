"""Merge validated offline native definitions, rejecting conflicting template IDs."""
import argparse,json,tempfile
from pathlib import Path

def merge(sources,output):
    docs=[json.loads(p.read_text(encoding='utf8')) for p in sources]
    if not docs or any(d.get('sourceKind')!='verified-native-unit-definitions' or d.get('localVerification') is not True for d in docs):raise ValueError('only verified native definitions can be merged')
    if len({d['gameVersion'] for d in docs})!=1 or len({d.get('localizationSha256') for d in docs})!=1:raise ValueError('source versions differ; reconcile before merging')
    records={}
    for doc in docs:
        for row in doc['records']:
            code=row['characterId']
            if code in records:
                signature=lambda r:{k:v for k,v in r.items() if k!='provenance'}
                if signature(records[code])!=signature(row):raise ValueError('conflicting native character: '+code)
            else:records[code]=row
    result={'schemaVersion':1,'sourceKind':'verified-native-unit-definitions','localVerification':True,'recordCount':len(records),'gameVersion':docs[0]['gameVersion'],
        'capturedAt':max(d['capturedAt'] for d in docs),'coverageComplete':False,'loadedContainerTraversalEnded':False,'localizationSha256':docs[0].get('localizationSha256'),
        'sourceCaptures':[d['sourceCaptureSha256'] for d in docs],'fieldEvidence':docs[0]['fieldEvidence'],'records':list(records.values())}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',dir=output.parent,suffix='.tmp',delete=False) as f:
        temporary=Path(f.name);json.dump(result,f,ensure_ascii=False,indent=2)
    try:temporary.replace(output)
    finally:temporary.unlink(missing_ok=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print('Merged native definitions:',merge(a.source,a.output)['recordCount'])
