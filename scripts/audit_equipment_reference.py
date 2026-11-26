"""Compare native templates/instance values with freshly fetched public evidence.

Unknown native values are retained, never filled from external template ranges.
The local database keeps the original records and a separate immutable audit.
"""
import argparse,hashlib,json,math,re,sqlite3
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
from local_game_database import ROOT,DEFAULT_DB,connect,encoded,stamp
from equipment_unknown_mapping import inspect_attribute,map_unknown

METHOD='native-instance-vs-rangerbook-v1'
AUDIT_SCHEMA="""
CREATE TABLE IF NOT EXISTS equipment_reference_audits (
 audit_id TEXT PRIMARY KEY, checked_at TEXT NOT NULL, report_sha256 TEXT NOT NULL,
 report TEXT NOT NULL CHECK(json_valid(report))
);
CREATE TABLE IF NOT EXISTS equipment_template_checks (
 audit_id TEXT NOT NULL REFERENCES equipment_reference_audits(audit_id), item_code TEXT NOT NULL,
 status TEXT NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload)), PRIMARY KEY(audit_id,item_code)
);
CREATE TABLE IF NOT EXISTS equipment_attribute_checks (
 audit_id TEXT NOT NULL REFERENCES equipment_reference_audits(audit_id), observation_id TEXT NOT NULL,
 attribute_index INTEGER NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload)),
 PRIMARY KEY(audit_id,observation_id,attribute_index)
);
CREATE TABLE IF NOT EXISTS equipment_audit_exports (
 audit_id TEXT PRIMARY KEY REFERENCES equipment_reference_audits(audit_id), content_sha256 TEXT NOT NULL,
 payload TEXT NOT NULL CHECK(json_valid(payload)), remote_status TEXT NOT NULL DEFAULT 'prepared',
 remote_verified_at TEXT
);
"""

def digest(value):return hashlib.sha256(encoded(value).encode('utf8')).hexdigest()
def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def compare_value(entry,gear,external):
    result={'index':entry['index'],'attributeId':entry['attributeId'],'attributeCode':entry.get('attributeCode'),
            'nativeValue':entry.get('value'),'nativeUnit':entry.get('unit'),
            'nativeVisuallyVerified':entry.get('valueVisuallyVerified') is True,'status':'unparsed_native'}
    if entry.get('valueVerified') is not True or entry.get('value') is None:return result
    if type(entry['value']) not in (int,float) or not math.isfinite(entry['value']) or entry.get('enhancementIncluded') is not True:
        raise ValueError('native value lacks finite value/verified enhancement')
    level=gear.get('enhancement')
    if type(level) is not int or not 0<=level<=5:raise ValueError('unsupported observed enhancement')
    code=entry.get('attributeCode');key='EQUIP:GEAR_FILTER_'+str(code)+'_nm'
    options=[r for r in external.get('normalOptions',[]) if r.get('optionKey')==key] if external else []
    if len(options)!=1:
        result['status']='missing_reference' if not options else 'ambiguous_reference';return result
    option=options[0];bounds=option.get('range')
    if not bounds or any(type(bounds.get(k)) not in (int,float) or not math.isfinite(bounds[k]) for k in ('min','max')):
        result['status']='missing_reference_range';return result
    result.update(referenceKey=key,referenceBaseRange=bounds,enhancement=level,referenceRule='base * (level + 1)')
    if bounds.get('unit')!=entry['unit']:
        result['status']='unit_mismatch';return result
    a,b=sorted(Decimal(str(bounds[k]))*(level+1) for k in ('min','max'))
    # Percent values are stored in displayed percentage points, already rounded
    # to one decimal by the proven native formatter. Never multiply them again.
    if entry['unit']=='PERCENT':a,b=[v.quantize(Decimal('.1'),rounding=ROUND_HALF_UP) for v in (a,b)]
    elif entry['unit']=='FLAT':
        # The native formatter truncates flat values; interval endpoints remain
        # reference numbers so a non-integral fixed reference is not auto-confirmed.
        pass
    else:result['status']='unsupported_unit';return result
    value=Decimal(str(entry['value']))
    result['referenceEnhancedRange']={'min':float(a),'max':float(b),'unit':entry['unit']}
    result['status']=('fixed_value_match' if a==b else 'within_reference_range') if a<=value<=b else 'value_mismatch'
    return result

def load_evidence(directory):
    directory=Path(directory).resolve();manifest=json.loads((directory/'manifest.json').read_text(encoding='utf8'))
    if manifest.get('sourceKind')!='public-rangerbook-reference-audit':raise ValueError('unexpected reference source')
    files={}
    for record in manifest['files']:
        name=record['file'];path=(directory/name).resolve()
        if path.parent!=directory or not record['url'].startswith('https://rangerbook.warmycat.com/') or file_sha(path)!=record['sha256']:
            raise ValueError('reference evidence path/hash mismatch')
        files[name]=record
    if not {'gear.html','equipment.json','gear-detail.js'}<=files.keys():raise ValueError('incomplete reference evidence')
    js=(directory/'gear-detail.js').read_text(encoding='utf8')
    if not re.search(r'if\s*\(mode\s*===\s*"multiply"\)\s*result\s*=\s*base\s*\*\s*\(level\s*\+\s*1\)',js):
        raise ValueError('external basic enhancement rule changed; review required')
    raw=json.loads((directory/'equipment.json').read_text(encoding='utf8'))
    rows=raw['equipment'];refs={r['equipCode']:r for r in rows}
    if len(refs)!=len(rows):raise ValueError('duplicate reference itemCode')
    return manifest,files,refs

def build_audit(reference_dir,root=ROOT):
    root=Path(root);manifest,files,refs=load_evidence(reference_dir)
    paths={k:root/'data/normalized'/v for k,v in [('templates','verified-equipment.json'),('defense','defense-teams.private.json'),('reference','equipment-reference-preview.json')]}
    docs={k:json.loads(p.read_text(encoding='utf8')) for k,p in paths.items()}
    if docs['templates'].get('sourceKind')!='verified-equipment-template' or docs['defense'].get('sourceKind')!='validated-player-team-snapshots' or docs['reference'].get('sourceKind')!='external-user-confirmed':
        raise ValueError('unexpected normalized native/reference source')
    prior={r['url']:r['sha256'] for r in docs['reference']['sources']}
    effect_map=None;native_cache={};mapping_counts=Counter();normalized_refs={r['itemCode']:r for r in docs['reference']['records']}
    if 'equipment-effects.json' in files:
        effects=json.loads((Path(reference_dir)/'equipment-effects.json').read_text(encoding='utf8'))['effects']
        effect_map={e['attributeId']:e for e in effects}
        if len(effect_map)!=len(effects):raise ValueError('duplicate external attribute ID')
    # Do not silently combine new external numbers with older reference labels.
    for name in ('equipment.json','gear-detail.js'):
        if prior.get(files[name]['url'])!=files[name]['sha256']:raise ValueError('reference changed since normalized preview; rebuild/review required')
    hashes={k:file_sha(p) for k,p in paths.items()}
    template_checks=[]
    for row in docs['templates']['records']:
        other=refs.get(row['itemCode']);status='identity_match' if other and other['starGrade']==row['starCount'] and other['equipType']==row['equipType'] else 'identity_mismatch'
        template_checks.append({'itemCode':row['itemCode'],'status':status,'nativeStars':row['starCount'],'referenceStars':other['starGrade'] if other else None,'nativeType':row['equipType'],'referenceType':other['equipType'] if other else None})
    observations=[];attribute_checks=[]
    for team in docs['defense']['snapshots']:
        if team['status']!='success':continue
        for member in team.get('members') or []:
            for slot,gear in member['equipment'].items():
                owner='owner-'+hashlib.sha256(team['playerId'].encode()).hexdigest()[:24]
                observation_id=digest([team['snapshotId'],team['playerId'],member['memberIndex'],slot])
                alias=lambda identity: digest([team['playerId'],identity.get('namespace'),identity['value']]) if identity else None
                attrs=[]
                for entry in (gear.get('actualEffects') or {}).get('entries',[]):
                    check=compare_value(entry,gear,refs.get(gear.get('equipmentId')))
                    check.update(observationId=observation_id,itemCode=gear.get('equipmentId'))
                    if check['status']=='unparsed_native' and entry.get('attributeTypeRaw') is None:
                        # The HTTP branch provides real IDs/grades, but not the
                        # native selectors/base ranges required by this mapper.
                        # Do not open nonexistent memory blobs or invent a type.
                        check['nativeDefinitionStatus']='not_acquired_in_http_response'
                    elif check['status']=='unparsed_native' and effect_map is not None:
                        native=inspect_attribute(root,team,member,slot,entry,native_cache)
                        mapping=map_unknown(entry,normalized_refs.get(gear.get('equipmentId')),effect_map,native,files['equipment-effects.json'])
                        check['externalMapping']=mapping;mapping_counts[mapping['status']]+=1
                    attribute_checks.append(check)
                    attrs.append({k:entry.get(k) for k in ['index','attributeId','attributeCode','attributeLabel','attributeTypeRaw','valueGradeRaw','value','unit','valueVerified','enhancementIncluded','valueVisuallyVerified']})
                observations.append({'observationId':observation_id,'recordScope':'equipment-instance-observation' if gear['state']=='equipped' else 'equipment-slot-observation',
                    'ownerAlias':owner,'characterInstanceAlias':alias(member.get('characterInstanceIdentity')),
                    'equipmentInstanceAlias':alias(gear.get('equipmentInstanceIdentity')),'characterId':member.get('characterId'),
                    'snapshotId':team['snapshotId'],'retrievedAt':team['retrievedAt'],'purpose':team['purpose'],'memberIndex':member['memberIndex'],'slot':slot,
                    'state':gear['state'],'equipmentId':gear.get('equipmentId'),'enhancement':gear.get('enhancement'),'instanceGrade':gear.get('instanceGrade'),
                    'attributeReadState':gear.get('attributeReadState'),'attributes':attrs,
                    'referenceChecks':[c for c in attribute_checks[-len(attrs):]] if attrs else []})
    summary=dict(Counter(r['status'] for r in attribute_checks))
    summary.update(templatesCompared=len(template_checks),templatesMatched=sum(r['status']=='identity_match' for r in template_checks),
        equippedInstances=sum(o['state']=='equipped' for o in observations),confirmedEmptySlots=sum(o['state']=='not_equipped' for o in observations),
        unknownSlots=sum(o['state']=='unknown' for o in observations),attributeEntries=len(attribute_checks),visuallyCheckedValues=sum(c['nativeVisuallyVerified'] for c in attribute_checks))
    report={'schemaVersion':1,'method':METHOD,'checkedAt':stamp(),'referenceFetchedAt':manifest['fetchedAt'],'referenceUrl':'https://rangerbook.warmycat.com/gear/',
        'sourceHashes':hashes,'referenceManifestSha256':file_sha(Path(reference_dir)/'manifest.json'),'referenceSources':manifest['files'],
        'summary':summary,'scope':'native template identities and already-parsed ordinary instance values; no inferred random rolls or conditions',
        'rangeAgreementDoesNotVerifyExactRoll':True,'templateChecks':template_checks,'attributeChecks':attribute_checks}
    if effect_map is not None:report['externalMappingSummary']=dict(mapping_counts)
    report['auditId']='equipment-audit-'+digest(report)[:24]
    # Structured reference and sanitized observations are retained for an explicit
    # private Supabase draft; no account IDs, credentials, keys or memory bytes.
    export={'auditId':report['auditId'],'templates':docs['templates']['records'],'references':docs['reference']['records'],
        'observations':observations,'report':report}
    return report,export

def save_local(report,export,database=DEFAULT_DB):
    if report.get('externalMappingSummary',{}).get('conflict',0) or report['summary']['templatesMatched']!=report['summary']['templatesCompared'] or any(c['status'].endswith('mismatch') for c in report['attributeChecks']):
        raise ValueError('conflicting audit must not be accepted')
    db=connect(database);db.executescript(AUDIT_SCHEMA)
    try:
        with db:
            sha=digest(report);existing=db.execute('SELECT report_sha256 FROM equipment_reference_audits WHERE audit_id=?',(report['auditId'],)).fetchone()
            if existing and existing[0]!=sha:raise ValueError('audit ID conflict; previous audit preserved')
            db.execute('INSERT OR IGNORE INTO equipment_reference_audits VALUES (?,?,?,?)',(report['auditId'],report['checkedAt'],sha,encoded(report)))
            db.executemany('INSERT OR IGNORE INTO equipment_template_checks VALUES (?,?,?,?)',[(report['auditId'],c['itemCode'],c['status'],encoded(c)) for c in report['templateChecks']])
            db.executemany('INSERT OR IGNORE INTO equipment_attribute_checks VALUES (?,?,?,?,?)',[(report['auditId'],c['observationId'],c['index'],c['status'],encoded(c)) for c in report['attributeChecks']])
            db.execute('INSERT OR IGNORE INTO equipment_audit_exports(audit_id,content_sha256,payload) VALUES (?,?,?)',(report['auditId'],digest(export),encoded(export)))
        return {'auditId':report['auditId'],'templateChecks':db.execute('SELECT count(*) FROM equipment_template_checks WHERE audit_id=?',(report['auditId'],)).fetchone()[0],
                'attributeChecks':db.execute('SELECT count(*) FROM equipment_attribute_checks WHERE audit_id=?',(report['auditId'],)).fetchone()[0],'integrity':db.execute('PRAGMA quick_check').fetchone()[0]}
    finally:db.close()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reference',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    report,export=build_audit(a.reference)
    folder=ROOT/'data/research/runtime.private/equipment-audits'/report['auditId'];folder.mkdir(parents=True,exist_ok=True)
    (folder/'export.private.json').write_text(json.dumps(export,ensure_ascii=False,indent=2),encoding='utf8')
    # Public-safe report contains only template/attribute IDs and opaque observation aliases.
    (ROOT/'reports/equipment-instance-reference-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'auditId':report['auditId'],'summary':report['summary'],'localSaved':save_local(report,export) if a.apply else False}))

if __name__=='__main__':main()
