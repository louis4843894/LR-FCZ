"""Export only native RANGERS definitions; guardians never become character rows."""
import argparse,hashlib,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def export(source,output):
    doc=json.loads(source.read_text(encoding='utf8'))
    if doc.get('sourceKind')!='verified-native-unit-definitions' or doc.get('localVerification') is not True:raise ValueError('not a verified native unit source')
    records=[];seen=set();unknown=[]
    for r in doc['records']:
        if r.get('unitIdentity')!='RANGERS':continue
        if r.get('recordScope')!='character-template' or r.get('fieldStatus',{}).get('identity')!='verified-native':raise ValueError('unverified Ranger identity')
        if r['characterId'] in seen:raise ValueError('duplicate/conflicting Ranger ID')
        seen.add(r['characterId'])
        if r.get('starCount') is not None and r.get('fieldStatus',{}).get('starCount')!='verified-native-ui-relation':raise ValueError('star count lacks UI relation evidence')
        # Alternate resource-code storage can be empty; it is not the definition ID.
        # Image mapping remains unknown until the renderer/resource branch is proved.
        records.append({k:r.get(k) for k in ['characterId','name','nameKey','description','descriptionKey','starCount','unitCategory','unitType','unitElement','resourceCode','imageMapping','skills','primarySkillCode','primaryAbilityCode','recordScope','fieldStatus']})
    if not records:raise ValueError('no verified RANGERS records; previous website data remains unchanged')
    result={'schemaVersion':1,'sourceKind':'verified-character-template','localVerification':True,'recordCount':len(records),'coverageComplete':False,
            'capturedAt':doc['capturedAt'],'gameVersion':doc['gameVersion'],'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'records':records}
    result['loadedContainerTraversalEnded']=doc.get('loadedContainerTraversalEnded') is True
    result['fieldCoverage']={k:sum(r.get(k) is not None for r in records) for k in ['characterId','name','unitCategory','unitType','unitElement','starCount','imageMapping','primarySkillCode','primaryAbilityCode','skills']}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',dir=output.parent,suffix='.tmp',delete=False) as f:
        temporary=Path(f.name);json.dump(result,f,ensure_ascii=False,indent=2)
    try:temporary.replace(output)
    finally:temporary.unlink(missing_ok=True)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,default=ROOT/'data/normalized/verified-characters.json');a=p.parse_args();print('Website native Rangers:',export(a.source,a.output)['recordCount'])
