"""Resolve ordinary GearStat IDs to Chinese kinds from saved verified objects.

No numerical values, external template guesses, process access or credentials.
Only attribute objects from accepted native captures are read. Conflicting ID
namespaces/kinds are withheld rather than resolved by majority vote.
"""
import argparse,hashlib,json,re,sqlite3,struct
from collections import defaultdict
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB,connect,encoded,stamp
from native_layouts import NEW_SHA,layout_for_sha
from native_elf import NativeELF

SCHEMA='''
CREATE TABLE IF NOT EXISTS gear_attribute_label_sources (
 source_id TEXT PRIMARY KEY,captured_at TEXT NOT NULL,module_sha256 TEXT NOT NULL,
 payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE TABLE IF NOT EXISTS current_gear_attribute_labels (
 scope TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES gear_attribute_label_sources(source_id)
);
CREATE TABLE IF NOT EXISTS gear_attribute_labels (
 source_id TEXT NOT NULL REFERENCES gear_attribute_label_sources(source_id),attribute_id INTEGER NOT NULL,
 type_enum INTEGER NOT NULL,code TEXT NOT NULL,label TEXT NOT NULL,
 PRIMARY KEY(source_id,attribute_id)
);
'''


def digest(raw):return hashlib.sha256(raw).hexdigest()


def resolve(observations,names):
    grouped=defaultdict(set);proofs=defaultdict(set)
    for row in observations:
        grouped[row['attributeId']].add(row['typeEnum']);proofs[row['attributeId']].add(row['sha256'])
    conflicts=[];records=[]
    for attr,kinds in sorted(grouped.items()):
        if len(kinds)!=1:conflicts.append(attr);continue
        kind=next(iter(kinds));name=names.get(kind)
        if not name:continue
        records.append({'attributeId':attr,'typeEnum':kind,'code':name['code'],'label':name['label'],
                        'evidenceRecordHashes':sorted(proofs[attr]),'numericValue':None})
    return records,conflicts


def build(database=DEFAULT_DB):
    module=ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so';elf=NativeELF(module)
    if elf.sha256!=NEW_SHA:raise ValueError('unverified label code module')
    if elf.cstring(0x7bce95)!='GEAR_FILTER_%s_nm':raise ValueError('native label pattern differs')
    translation=ROOT/'data/extracted/lr_20261116T212608096_7b99bdd0/assets/res/tutorial_res/db/lang_equip/lang_equip.ndb'
    names={}
    with sqlite3.connect(translation.resolve().as_uri()+'?mode=ro',uri=True) as db:
        for kind in range(1,46):
            offset=struct.unpack_from('<i',elf.data,elf.offset(0x85611c+(kind-1)*4))[0];code=elf.cstring(0x85611c+offset)
            row=db.execute("SELECT msg FROM lang_equip WHERE language='zh-Hant' AND dataCode=?",('GEAR_FILTER_'+code+'_nm',)).fetchone()
            if row and row[0]:names[kind]={'code':code,'label':row[0]}
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True) as db:
        raw=db.execute("SELECT d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename='defense-teams.private.json'").fetchone()
        source_ids=sorted({t['sourceId'] for t in json.loads(raw[0])['snapshots']})
    observations=[];sources=[]
    private=(ROOT/'data/research/runtime.private').resolve();ap=layout_for_sha(NEW_SHA)['attributeVtable']
    for source_id in source_ids:
        directory=(private/source_id).resolve()
        if directory.parent!=private:raise ValueError('unsafe native source path')
        manifest=directory/'capture.json'
        if not manifest.exists():continue
        raw=manifest.read_bytes();meta=json.loads(raw)
        if meta.get('moduleSha256')!=NEW_SHA or meta.get('consistentSnapshot') is not True:continue
        if len(meta.get('records',[]))>100:raise ValueError('native record bound')
        found=0
        for unit in meta['records']:
            for key,entry in unit['files'].items():
                if not re.fullmatch(r'gear-[123]-attribute-(?:[0-9]|1[0-5])',key):continue
                path=(directory/entry['file']).resolve()
                if path.parent!=directory:raise ValueError('unsafe attribute path')
                blob=path.read_bytes()
                if digest(blob)!=entry['sha256'] or len(blob)!=0x78:raise ValueError('attribute hash or boundary differs')
                if struct.unpack_from('<Q',blob)[0]-meta['moduleBase']+0x100000!=ap:raise ValueError('attribute object type differs')
                attr,kind=struct.unpack_from('<II',blob,0x18)
                if attr:
                    observations.append({'attributeId':attr,'typeEnum':kind,'sha256':entry['sha256']});found+=1
        if found:sources.append({'manifestSha256':digest(raw),'capturedAt':meta['capturedAt'],'attributeObjects':found})
    # A later verified global container can extend the observed instance IDs.
    # Re-validate its frozen files; never infer a kind from a nearby ID.
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True) as db:
        exists=db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='current_gear_definitions'").fetchone()
        current=db.execute("SELECT s.payload FROM current_gear_definitions c JOIN gear_definition_sources s USING(source_id) WHERE scope='ordinary-gearstat'").fetchone() if exists else None
    if current:
        from parse_gear_definitions import parse
        accepted=json.loads(current[0]);definition=parse(ROOT/accepted['captureDirectory'])
        if definition!=accepted:raise ValueError('accepted global definitions differ from original copies')
        observations.extend({'attributeId':r['attributeId'],'typeEnum':r['typeEnum'],'sha256':r['rawRecordSha256']} for r in definition['records'])
        sources.append({'manifestSha256':definition['captureManifestSha256'],'capturedAt':definition['capturedAt'],'attributeObjects':len(definition['records']),'recordScope':'global-ordinary-gearstat-definitions'})
    records,conflicts=resolve(observations,names)
    if not records:raise ValueError('no verified native labels')
    doc={'schemaVersion':1,'sourceKind':'verified-native-gearstat-labels','moduleSha256':NEW_SHA,
         'idNamespace':'ordinary-GearStat.attrNo','records':records,'conflictingAttributeIds':conflicts,
         'evidence':{'typeNameFunction':'0122f924','typeNameTable':'0085611c','labelPattern':'GEAR_FILTER_%s_nm',
                     'attributeIdOffset':'0x18','typeEnumOffset':'0x1c','translationSha256':digest(translation.read_bytes()),'sources':sources},
         'numericValuesDerived':False,'wholeGameCoverageConfirmed':False}
    doc['sourceId']='gear-labels-'+digest(encoded(doc).encode())[:24]
    return doc


def save(doc,database=DEFAULT_DB):
    directory=ROOT/'data/research/runtime.private/gear-label-exports'/doc['sourceId'];directory.mkdir(parents=True,exist_ok=True)
    output=directory/'labels.private.json';text=encoded(doc)+'\n'
    if output.exists() and output.read_text(encoding='utf8')!=text:raise ValueError('immutable label source differs')
    output.write_text(text,encoding='utf8')
    db=connect(database);db.executescript(SCHEMA)
    try:
        with db:
            previous=db.execute('SELECT payload FROM gear_attribute_label_sources WHERE source_id=?',(doc['sourceId'],)).fetchone()
            if previous and previous[0]!=encoded(doc):raise ValueError('immutable label database source differs')
            db.execute('INSERT OR IGNORE INTO gear_attribute_label_sources VALUES (?,?,?,?)',(doc['sourceId'],stamp(),doc['moduleSha256'],encoded(doc)))
            db.executemany('INSERT OR IGNORE INTO gear_attribute_labels VALUES (?,?,?,?,?)',[(doc['sourceId'],r['attributeId'],r['typeEnum'],r['code'],r['label']) for r in doc['records']])
            db.execute('INSERT INTO current_gear_attribute_labels VALUES (?,?) ON CONFLICT(scope) DO UPDATE SET source_id=excluded.source_id',('ordinary-native',doc['sourceId']))
    finally:db.close()
    return directory


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');a=p.parse_args();doc=build()
    if a.apply:save(doc)
    print(json.dumps({'sourceId':doc['sourceId'],'labels':len(doc['records']),'nativeSourceCaptures':len(doc['evidence']['sources']),
                      'attributeObjectsVerified':sum(s['attributeObjects'] for s in doc['evidence']['sources']),
                      'conflictingIds':len(doc['conflictingAttributeIds']),'numericValuesDerived':False,'saved':a.apply}))
