"""Insert a private character-detail draft with field provenance; preserve old data."""
import argparse,hashlib,json,sqlite3
from contextlib import closing
from datetime import datetime,timezone
from local_game_database import ROOT,DEFAULT_DB,encoded
from sync_equipment_audit_supabase import upload,digest
from sync_character_templates_supabase import freeze
from supabase_local_connection import existing_service_client,existing_anon_client
from build_character_native_details import read_native_details,public_talents


def select(row,keys):return {k:row.get(k) for k in keys}
def public_details(row):
 if row['status']!='matched-reference':return None
 def effects(items):
  return [select(e,['name','magnitudeText','durationText','rangePoints','triggerChancePercent','targetLimitText','availableEvents','availableGuardian']) for e in items] if items is not None else None
 def abilities(items):
  if items is None:return None
  return [{**select(a,['abilityCode','name','description','status']),
           'triggerEffects':[select(t,['chancePercent','phase','battleMode','condition','additionalCondition','effect']) for t in a['triggerEffects']] if a['triggerEffects'] is not None else None} for a in items]
 skills=[{**select(s,['skillCode','name','description','status','activationRatePercent','cooldownSeconds','startupSeconds','triggerLabel','searchRatio']),'effects':effects(s['effects'])} for s in row['skills']] if row['skills'] is not None else None
 talent=row['talents'];major=talent.get('major') if talent else None
 talent_safe=None if talent is None else {'major':None if major is None else {
   **select(major,['talentCode','description','activationChancePercent','condition','additionalConditions']),
   'effects':[select(e,['description','durationSeconds','activationChancePercent']) for e in major['effects']]},
   'enhancements':[select(e,['talentCode','description']) for e in talent['enhancements']]}
 stats=row['stats'];stats_safe=None
 if stats:
  stats_safe=select(stats,['hp','mineralCost','respawnSeconds','attackRange','splashRange','criticalChancePercent','criticalDamagePercent','dodgeChancePercent','skillDodgeChancePercent','skillResistancePercent','hitChancePercent','skillHitChancePercent'])
  for key,fields in [('attack',['physical','magical']),('defense',['physical','magical']),('moveSpeed',['pointsPerSecond']),('attackSpeed',['secondsPerAttack'])]:
   stats_safe[key]=select(stats[key],fields) if isinstance(stats.get(key),dict) else None
 return {'skills':skills,'abilities':abilities(row['abilities']),'awakeningAbilities':abilities(row['awakeningAbilities']),
         'talents':talent_safe,'stats':stats_safe,'availability':{k:row.get('availability',{}).get(k,'unknown') if row.get('availability',{}).get(k) in ('present','absent','unknown') else 'unknown' for k in ['skills','abilities','awakening','talents']},'releaseDate':row['releaseDate'],'templateOnly':True,'playerTrainingOrEquipmentApplied':False,
         'awakeningCandidatesAreNotPlayerAwakening':True,'localNumericVerification':False}


def prepare(database=DEFAULT_DB):
 with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)) as db:
  sid,payload=db.execute("SELECT s.source_id,s.payload FROM current_character_details c JOIN character_detail_sources s USING(source_id) WHERE c.scope='native-matched-reference'").fetchone();meta=json.loads(payload)
  native_sha,native_text=db.execute("SELECT d.sha256,d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename='verified-characters.json'").fetchone();native=json.loads(native_text)
  details={code:json.loads(p) for code,p in db.execute('SELECT character_id,payload FROM character_template_details WHERE source_id=?',(sid,))}
 if native_sha!=meta['nativeDocumentSha256'] or len(details)!=len(native['records']):raise ValueError('character native version/count changed')
 raw=ROOT/'data/research/runtime.private/character-detail-exports'/sid/'details.private.json';frozen=json.loads(raw.read_bytes())
 if frozen['sourceId']!=sid or {r['characterId']:r for r in frozen['records']}!=details:raise ValueError('character frozen overlay differs')
 native_detail_source,native_details=read_native_details(database)
 combined=[]
 for base in native['records']:
  detail=details[base['characterId']]
  native_detail=native_details.get(base['characterId']);image=native_detail.get('image') if native_detail else None
  combined.append({**select(base,['characterId','name','description','starCount','unitCategory','unitElement','primarySkillCode','primaryAbilityCode']),
                   'nativeTalentStages':public_talents(native_detail),'localThumbnail':{k:image[k] for k in ['sha256','width','height','sourceKind']} if image else None,
                   'recordScope':'character-template','detailStatus':detail['status'],'templateDetails':public_details(detail),
                   'fieldSources':{'basic':'verified-native-template','details':'user-confirmed-reference','skillDescriptionSources':sorted({s['textSource'] for s in detail['skills'] or []}),'detailNumbersNativeVerified':False,
                                   'talentGroupAndOrder':'verified-native-template','talentDescriptionSources':sorted({s.get('labelSource','unresolved') for s in (native_detail or {}).get('talents',{}).get('steps') or []}),'thumbnail':'verified-local-game-asset' if image else 'not_available'}})
 manifest={'nativeDocumentSha256':native_sha,'nativeCapturedAt':datetime.fromtimestamp(native['capturedAt'],timezone.utc).isoformat(),
           'referenceRetrievedAt':meta['retrievedAt'],'detailSourceId':sid,'referenceManifestSha256':meta['referenceManifestSha256'],'localTranslationSha256':meta['localTranslationSha256'],'summary':meta['summary']}
 if meta.get('startupSource'):manifest['startupSource']=meta['startupSource']
 manifest['nativeEnrichmentSourceId']=native_detail_source
 content=digest({'records':combined,'provenance':manifest});snapshot_id='characters-details-'+content[:24]
 folder=ROOT/'data/research/runtime.private/character-detail-exports'/snapshot_id;folder.mkdir(parents=True,exist_ok=True)
 output=folder/'characters.private.json';file_sha=freeze(output,{'records':combined});source_file=output.relative_to(ROOT).as_posix()
 manifest_sha=freeze(folder/'manifest.private.json',manifest);rows=[]
 for i,row in enumerate(combined):
  item={'snapshot_id':snapshot_id,'module':'characters','source_record_identity':{'scope':'character-template','characterId':row['characterId']},
        'source_file':source_file,'source_file_sha256':file_sha,'source_record_locator':f'$.records[{i}]',
        'raw_record':{'nativeDocumentSha256':native_sha,'detailSourceId':sid,'recordScope':'character-template'},
        'normalized_record':row,'validation_status':'source-record-verified','parse_warnings':[] if row['detailStatus']=='matched-reference' else ['character_detail_reference_not_available']}
  item['record_sha256']=digest(item);rows.append(item)
 snapshot={'snapshot_id':snapshot_id,'module':'characters','source_kind':'dynamic','source_version':'native-matched-character-details-v1',
           'captured_at':meta['retrievedAt'],'source_manifest_sha256':manifest_sha,'content_sha256':digest(rows),'record_count':len(rows),
           'source_metadata':{**manifest,'draftOnly':True,'detailsSourceKind':'external-user-confirmed','detailNumericNativeParsed':False,
                              'templateOnly':True,'containsRawMemoryOrCredentials':False,'awakeningCandidatesAreNotPlayerAwakening':True},
           'expected_counts':{'research_records':len(rows)},'is_complete':False,'status':'draft'}
 plan={'snapshot':snapshot,'researchRows':rows,'equipmentRows':[]};freeze(folder/'supabase-upload.private.json',plan)
 # These raw/ambiguous fields must never leave the local research copy.
 if any(word in encoded(plan) for word in ['candidateProbabilityRaw','descriptionParameters','moduleBase','rawMemory']):raise ValueError('character upload whitelist failed')
 return folder,plan


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');a=p.parse_args();folder,plan=prepare()
 if not a.apply:print(json.dumps({'prepared':True,'snapshotId':plan['snapshot']['snapshot_id'],'characters':len(plan['researchRows']),'summary':plan['snapshot']['source_metadata']['summary']}))
 else:
  try:receipt=upload(plan,existing_service_client(),existing_anon_client())
  except Exception:
   print(json.dumps({'uploaded':False,'reason':'remote_connection_or_readback_failed','localDataPreserved':True}));raise SystemExit(1)
  freeze(folder/'supabase-receipt.private.json',receipt)
  (ROOT/'reports/character-details-supabase-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt))
