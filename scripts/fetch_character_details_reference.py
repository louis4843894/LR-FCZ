"""Copy the specified site's documented public V2 character datasets only.

No login, cookies, private APIs, or modification of earlier reference copies.
The saved v2-data.js proves the /res/v2/{name}.json public resource pattern.
"""
import argparse,hashlib,json,urllib.request,urllib.parse
from datetime import datetime,timezone
from pathlib import Path
from local_game_database import ROOT

ORIGIN='https://rangerbook.warmycat.com'


def fetch(folder):
 folder=Path(folder).resolve()
 if not folder.is_relative_to(ROOT/'data/research/external-reference'):raise ValueError('reference directory required')
 script=(folder/'v2-data.js').read_text(encoding='utf8')
 if 'res/v2/' not in script or 'data("abilities")' not in script or '"rangers"' not in script:raise ValueError('public data loader proof absent')
 manifest=folder/'datasets-source.json'
 if manifest.exists():
  doc=json.loads(manifest.read_bytes())
  for row in doc['files']:
   if hashlib.sha256((folder/row['file']).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('immutable reference differs')
  return doc
 files=[]
 for name,path,limit in [('rangers.json','/res/v2/rangers.json',32*1024*1024),('abilities.json','/res/v2/abilities.json',16*1024*1024),
                         ('official-locales.json','/res/v2/locales/official.json',12*1024*1024),('custom-locales.json','/res/v2/locales/custom.json',4*1024*1024)]:
  output=folder/name
  if output.exists():raise ValueError('partial copy exists; use a fresh reference directory')
  req=urllib.request.Request(ORIGIN+path,headers={'User-Agent':'LR-local-reference-review/1.0','Accept':'application/json'})
  with urllib.request.urlopen(req,timeout=30) as response:
   if urllib.parse.urlparse(response.url).netloc!='rangerbook.warmycat.com':raise ValueError('unexpected reference redirect')
   raw=response.read(limit+1)
   if len(raw)>limit:raise ValueError('reference size bound')
   modified=response.headers.get('Last-Modified');etag=response.headers.get('ETag')
  parsed=json.loads(raw)
  if name in ('rangers.json','abilities.json') and parsed.get('schemaVersion')!=2:raise ValueError('unsupported public reference schema')
  if 'locales' in name and not isinstance(parsed,list):raise ValueError('invalid reference catalog')
  output.write_bytes(raw);files.append({'file':name,'url':ORIGIN+path,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),
                                      'retrievedAt':datetime.now(timezone.utc).isoformat(),'lastModified':modified,'etag':etag})
 doc={'schemaVersion':1,'sourceKind':'external-user-confirmed','localVerification':False,'retrievedAt':datetime.now(timezone.utc).isoformat(),
      'publicLoaderSha256':hashlib.sha256((folder/'v2-data.js').read_bytes()).hexdigest(),'files':files}
 manifest.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return doc


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True);a=p.parse_args();d=fetch(a.directory)
 print(json.dumps({'copy':a.directory.as_posix(),'files':[{k:r[k] for k in ['file','bytes','sha256']} for r in d['files']],'credentialsUsed':False}))
