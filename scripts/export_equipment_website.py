"""Whitelist verified template fields for server-side website use; never export memory dumps."""
import argparse,hashlib,json,re
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def export(source,output):
 doc=json.loads(source.read_text(encoding='utf8'));seen={};rows=[]
 if (doc.get('traversal') or {}).get('consistentSnapshot') is False:raise ValueError('inconsistent capture cannot be published')
 source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
 provenance={'gameVersion':doc.get('gameVersion','12.4.0'),'parserVersion':doc.get('parserVersion','runtime-equipment-v1'),'sourceSnapshotSha256':source_sha,'capturedAt':datetime.fromtimestamp(doc['capturedAt'],timezone.utc).isoformat() if doc.get('capturedAt') else None}
 for r in doc['records']:
  if not all(r.get('validation',{}).get(k) is True for k in ['vtableVerified','dictionaryKeyMatchesItemCode','gradeChecksumVerified']):raise ValueError('unverified record')
  code=r['itemCode']
  if not re.fullmatch(r'eq_[A-Za-z0-9_]+',code):raise ValueError('invalid itemCode')
  if r['equipType'] not in ('ARMOR','WEAPON','ACC') or type(r['starCount']) is not int or not 1<=r['starCount']<=9:raise ValueError('unsupported equipment fields')
  translations={t['language']:t['msg'] for t in r.get('nameTranslations',[]) if t['dataCode']==code+'_nm'}
  row={'itemCode':code,'dataCode':code+'_nm','equipType':r['equipType'],'starCount':r['starCount'],'maxEnchant':r['maxEnchant'],'minAttributeCount':r['minAttributeCount'],'maxAttributeCount':r['maxAttributeCount'],'names':translations,'effects':None,'effectsStatus':'unparsed','recordScope':'equipment-template','provenance':provenance}
  if 'goodGearAttr' in r:row['goodGearAttr']=r['goodGearAttr']
  if code in seen:
   if seen[code]!=row:raise ValueError('conflicting itemCode '+code)
   continue
  seen[code]=row;rows.append(row)
 result={'schemaVersion':1,'gameVersion':'12.4.0','sourceKind':'verified-equipment-template','recordCount':len(rows),'counts':{'captured':doc['recordParsing'].get('capturedRecordCount',len(rows)),'parsed':len(rows),'failed':doc['recordParsing'].get('failedRecordCount',0)},'coverageComplete':False,'loadedContainerTraversalEnded':doc['recordParsing'].get('loadedDictionaryTraversalEnded',False),'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'records':rows}
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('Website whitelist exported:',len(rows),'records')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,default=ROOT/'data/research/equipment-runtime-records.json');p.add_argument('--output',type=Path,default=ROOT/'data/normalized/verified-equipment.json');a=p.parse_args();export(a.source,a.output)
