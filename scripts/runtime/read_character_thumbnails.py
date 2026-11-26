"""Copy exact known character thumbnails from the game's normal resource cache."""
import base64,hashlib,io,json,re,sys,tarfile,uuid
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bounded_equipment_reader import Reader
from equipment_memory import ROOT
from native_layouts import NEW_SHA
from build_character_native_details import ASSETS,png_size

ADB=r'C:\LDPlayer\LDPlayer9\adb.exe';SERIAL='emulator-5554';REMOTE='/sdcard/Android/data/com.linecorp.LGRGS/files/.res'


def main():
 basic_path=ROOT/'data/normalized/verified-characters.json';raw=basic_path.read_bytes();ids={r['characterId'] for r in json.loads(raw)['records']}
 with Reader(ADB,SERIAL,120) as r:
  r.expected_module_sha=NEW_SHA;r.refresh()
  paths=r.shell("find "+REMOTE+" -maxdepth 2 -type f -name '*-thum.png'").decode().splitlines()
 if len(paths)>7000:raise ValueError('thumbnail inventory bound')
 wanted={}
 for path in paths:
  if not path.startswith(REMOTE+'/'):raise ValueError('source root differs')
  relative=path[len(REMOTE)+1:];parts=relative.split('/')
  if len(parts)==2 and parts[0] in ids and parts[1]==parts[0]+'-thum.png':
   if not re.fullmatch('[A-Za-z0-9_-]+',parts[0]) or parts[0] in wanted:raise ValueError('duplicate/invalid thumbnail identity')
   if not (ASSETS/parts[0]/parts[1]).exists():wanted[parts[0]]=relative
 folder=ROOT/'data/research/runtime.private'/('character-thumbnails-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]);folder.mkdir()
 records=[];items=sorted(wanted.items())
 for start in range(0,len(items),128):
  part=items[start:start+128];expected={p for _,p in part}
  # All names derive from accepted IDs and an exact native filename format.
  command='cd '+REMOTE+' && tar -cf - '+' '.join(p for _,p in part)
  with Reader(ADB,SERIAL,45) as copy_reader:encoded=copy_reader.shell(command+' | base64')
  if len(encoded)>90*1024*1024:raise ValueError('bounded thumbnail copy failed')
  archive_bytes=base64.b64decode(b''.join(encoded.split()),validate=True)
  with tarfile.open(fileobj=io.BytesIO(archive_bytes),mode='r:') as archive:
   members=archive.getmembers()
   if len(members)!=len(part) or {m.name for m in members}!=expected:raise ValueError('archive inventory differs')
   for member in members:
    if not member.isfile() or member.size>2*1024*1024:raise ValueError('unsafe thumbnail archive member')
    b=archive.extractfile(member).read();w,h=png_size(b);code=member.name.split('/')[0]
    (folder/(code+'.png')).write_bytes(b);records.append({'characterId':code,'file':code+'.png','sha256':hashlib.sha256(b).hexdigest(),'width':w,'height':h,'sourcePath':REMOTE+'/'+member.name})
  print(json.dumps({'copiedThumbnails':len(records),'requestedThumbnails':len(items)}),flush=True)
 doc={'sourceKind':'verified-game-cache-character-thumbnails','capturedAt':datetime.now(timezone.utc).isoformat(),'gameVersion':'12.4.2','moduleSha256':NEW_SHA,
      'nativeDocumentSha256':hashlib.sha256(raw).hexdigest(),'sourceRoot':REMOTE,'records':records,'baseApkThumbnailsReused':sum((ASSETS/c/(c+'-thum.png')).exists() for c in ids),
      'requestedFiles':len(items),'copiedFiles':len(records),'credentialsRead':False,'wholeGameComplete':False}
 (folder/'capture.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps({'copy':folder.relative_to(ROOT).as_posix(),'copied':len(records),'credentialsRead':False}))


if __name__=='__main__':main()
