import "server-only";
import { readFile } from "node:fs/promises";
import path from "node:path";
import type {GearRoll} from './gear-instance-values';

const filenames = new Set([
  "verified-equipment.json", "equipment-reference-preview.json", "verified-characters.json",
  "guild-roster.private.json", "defense-teams.private.json",
]);

export async function localDatabase() {
  const configured=process.env.LR_LOCAL_DATABASE_PATH;
  if(!configured || process.env.NODE_ENV!=="development")return null;
  const root=path.resolve(process.cwd(),"data/local");const databasePath=path.resolve(process.cwd(),configured);
  const relative=path.relative(root,databasePath);
  if(!relative || relative.startsWith("..") || path.isAbsolute(relative))throw new Error("本機資料庫路徑必須位於 data/local");
  const {DatabaseSync}=await import("node:sqlite");return new DatabaseSync(databasePath,{readOnly:true});
}

export type CharacterDetailIndex={status:string;skillCount:number|null;abilityCount:number|null;awakeningCount:number|null;talentsAvailable:boolean};
export async function readCharacterTemplateDocument():Promise<{text:string;documentSha:string|null}>{
 const db=await localDatabase();
 if(!db)return {text:await readNormalizedText('verified-characters.json'),documentSha:null};
 try{
  const row=db.prepare("SELECT c.sha256,d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename='verified-characters.json'").get();
  if(!row||typeof row.payload!=='string'||typeof row.sha256!=='string'||!/^[a-f0-9]{64}$/.test(row.sha256))throw new Error('角色基本資料版本不存在');
  // SQLite preserves the accepted FILE hash while its payload is canonical
  // JSON. Hashing the serialized payload would reject an unchanged document.
  return {text:row.payload,documentSha:row.sha256};
 }finally{db.close();}
}
export async function readCharacterDetailStore(nativeSha:string,characterId?:string):Promise<{retrievedAt:string;summary:Record<string,number>;index:Map<string,CharacterDetailIndex>;detail:unknown|null}|null>{
 if(!/^[a-f0-9]{64}$/.test(nativeSha)||(characterId!==undefined&&!/^[A-Za-z0-9_-]+$/.test(characterId)))return null;
 const db=await localDatabase();if(!db)return null;
 try{
  if(!db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='current_character_details'").get())return null;
  const row=db.prepare("SELECT s.source_id,s.payload FROM current_character_details c JOIN character_detail_sources s USING(source_id) WHERE c.scope='native-matched-reference'").get();if(!row)return null;
  const meta=JSON.parse(String(row.payload));
  if(meta.sourceKind!=='native-matched-user-confirmed-character-details'||meta.nativeDocumentSha256!==nativeSha||meta.templateOnly!==true||meta.localNumericVerification!==false||meta.playerTrainingOrEquipmentApplied!==false||meta.awakeningCandidatesAreNotPlayerAwakening!==true)return null;
  if(typeof meta.retrievedAt!=='string'||!Number.isFinite(Date.parse(meta.retrievedAt)))return null;
  const summary:Record<string,number>={};for(const key of ['matchedCharacters','skillsCharacters','abilitiesCharacters','awakeningAbilitiesCharacters','talentsCharacters','statsCharacters','skills','skillEffects','nativeCharacters','not_in_reference','skills_absent','abilities_absent','awakening_absent','talents_absent'])
   if(Number.isSafeInteger(meta.summary?.[key])&&meta.summary[key]>=0)summary[key]=meta.summary[key];
  const index=new Map<string,CharacterDetailIndex>();const count=(v:unknown)=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=0&&v<=128?v:null;
  for(const [id,v] of Object.entries(meta.index??{})){
   const item=v as Record<string,unknown>;
   if(!/^[A-Za-z0-9_-]+$/.test(id)||!item||!['matched-reference','not_in_reference','identity_conflict'].includes(String(item.status)))continue;
   index.set(id,{status:String(item.status),skillCount:count(item.skillCount),abilityCount:count(item.abilityCount),awakeningCount:count(item.awakeningCount),talentsAvailable:item.talentsAvailable===true});
  }
  const detail=characterId?db.prepare('SELECT payload FROM character_template_details WHERE source_id=? AND character_id=?').get(row.source_id,characterId):null;
  return {retrievedAt:meta.retrievedAt,summary,index,detail:detail?JSON.parse(String(detail.payload)):null};
 }finally{db.close();}
}

export async function readCollectionTarget(module:"guild"|"pvp"):Promise<string|null>{
  const database=await localDatabase();if(!database)return null;
  try{
    const row=database.prepare("SELECT target_name FROM collection_targets WHERE module=? AND source='user'").get(module);
    return row&&typeof row.target_name==="string" ? row.target_name : null;
  }finally{database.close();}
}

export async function readLatestEquipmentChecks():Promise<unknown[]>{
  const database=await localDatabase();if(!database)return [];
  try{
    if(!database.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='equipment_attribute_checks'").get())return [];
    return database.prepare("SELECT payload FROM equipment_attribute_checks WHERE audit_id=(SELECT audit_id FROM equipment_reference_audits ORDER BY checked_at DESC LIMIT 1) AND status='unparsed_native'").all().map(row=>JSON.parse(String(row.payload)) as unknown);
  }finally{database.close();}
}

export async function readNativeGearLabels():Promise<{sourceId:string;records:{attributeId:number;typeEnum:number;code:string;label:string}[]}|null>{
  const database=await localDatabase();if(!database)return null;
  try{
    if(!database.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='gear_attribute_label_sources'").get())return null;
    const row=database.prepare("SELECT s.source_id,s.payload FROM current_gear_attribute_labels c JOIN gear_attribute_label_sources s USING(source_id) WHERE scope='ordinary-native'").get();
    if(!row)return null;
    const data=JSON.parse(String(row.payload));
    if(data.sourceKind!=='verified-native-gearstat-labels'||data.numericValuesDerived!==false||data.moduleSha256!=='1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0')throw new Error('原生詞條名稱來源無效');
    return {sourceId:String(row.source_id),records:database.prepare('SELECT attribute_id,type_enum,code,label FROM gear_attribute_labels WHERE source_id=?').all(row.source_id).map(r=>({attributeId:Number(r.attribute_id),typeEnum:Number(r.type_enum),code:String(r.code),label:String(r.label)}))};
  }finally{database.close();}
}

export async function readNativeGearRolls(observations:string[],scope:'ranked-http'|'guildwar'='ranked-http'):Promise<Map<string,GearRoll>>{
  const result=new Map<string,GearRoll>();if(!observations.length)return result;
  const database=await localDatabase();if(!database)return result;
  try{
    if(!database.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='gear_roll_sources'").get())return result;
    const source=database.prepare("SELECT s.source_id,s.payload FROM current_gear_rolls c JOIN gear_roll_sources s USING(source_id) WHERE scope=?").get(scope);if(!source)return result;
    const meta=JSON.parse(String(source.payload));
    const kind=scope==='guildwar'?'calibrated-native-definition-guildwar-rolls':'calibrated-native-definition-http-rolls';
    if(meta.sourceKind!==kind||meta.moduleSha256!=='1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0'||meta.externalReferenceValuesUsed!==false||!Number.isInteger(meta.calibration?.screenCheckedGearCount)||meta.calibration.screenCheckedGearCount<2||!Number.isInteger(meta.calibration?.screenCheckedValueCount)||meta.calibration.screenCheckedValueCount<6)throw new Error('裝備實例數值還原來源未驗證');
    const keys=[...new Set(observations)];
    for(let i=0;i<keys.length;i+=400){const part=keys.slice(i,i+400);for(const r of database.prepare(`SELECT observation_id,payload FROM gear_instance_rolls WHERE source_id=? AND observation_id IN (${part.map(()=>'?').join(',')})`).all(source.source_id,...part)){
      const item=JSON.parse(String(r.payload));
      if(item.observationId!==r.observation_id||!Array.isArray(item.entries))throw new Error('裝備實例數值識別不一致');
      result.set(item.observationId,{observationId:item.observationId,equipmentId:item.equipmentId,enhancement:item.enhancement,instanceGrade:item.instanceGrade,
        equipmentInstanceHash:item.equipmentInstanceHash,factorCapturedAt:item.factorCapturedAt,
        ...(scope==='guildwar'?{extraSpecialObserved:!!item.supplementarySpecial,
          ...(meta.optionProof?.normalFunction==='0122e270'&&meta.optionProof?.talentDescriptionFunction==='0122e690'&&meta.optionProof?.placeholderFormatter==='0122c704'&&
              item.supplementarySpecial?.state==='values_reconstructed'&&item.supplementarySpecial?.valueVerified===true&&item.supplementarySpecial?.enhancementIncluded===true&&
              item.supplementarySpecial?.activationState==='not_verified'&&['name','normalText','description'].every(k=>typeof item.supplementarySpecial[k]==='string'&&item.supplementarySpecial[k].length>0&&item.supplementarySpecial[k].length<=1000)&&
              Number.isInteger(item.supplementarySpecial.specialEnhancement)&&item.supplementarySpecial.specialEnhancement>=0&&item.supplementarySpecial.specialEnhancement<=100?
            {extraSpecial:{name:item.supplementarySpecial.name,normalText:item.supplementarySpecial.normalText,description:item.supplementarySpecial.description,
              specialEnhancement:item.supplementarySpecial.specialEnhancement,valueVisuallyVerified:false as const,activationState:'not_verified' as const}}:{})}:{}),
        entries:item.entries.map((a:GearRoll['entries'][number])=>({index:a.index,attributeId:a.attributeId,valueGradeRaw:a.valueGradeRaw,sourceField:a.sourceField,value:a.value,unit:a.unit,
          enhancementIncluded:a.enhancementIncluded===true,valueVerified:a.valueVerified===true,valueVisuallyVerified:false,
          ...(scope==='guildwar'&&a.calculationKind==='native-conditional'?{calculationKind:'native-conditional' as const,conditionState:'applicability_not_verified' as const,
            appliedEnhancementLevel:Number.isInteger(a.appliedEnhancementLevel)&&a.appliedEnhancementLevel!>=0&&a.appliedEnhancementLevel!<=100?a.appliedEnhancementLevel:undefined}:{} ),
          ...(scope==='guildwar'&&a.calculationKind==='native-skillplus'&&meta.skillPlusProof?.formulaFunction==='0122ed7c'&&meta.skillPlusProof?.nameFunction==='01230e34'?{calculationKind:'native-skillplus' as const,conditionState:'skill_activation_not_verified' as const,
            labelTemplate:typeof a.labelTemplate==='string'&&a.labelTemplate.length<=1000?a.labelTemplate:null,
            modifierOperator:['+','-','/'].includes(a.modifierOperator??'')?a.modifierOperator:undefined,
            appliedEnhancementLevel:Number.isInteger(a.appliedEnhancementLevel)&&a.appliedEnhancementLevel!>=0&&a.appliedEnhancementLevel!<=100?a.appliedEnhancementLevel:undefined}:{} )}))});
    }}
    return result;
  }finally{database.close();}
}

export async function readRankingStore():Promise<{snapshots:unknown[];current:{scope:string;snapshotId:string}[];attempts:{snapshotId:string;playerId:string;payload:unknown}[]}>{
  const database=await localDatabase();const empty={snapshots:[],current:[],attempts:[]};if(!database)return empty;
  try{
    if(!database.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='ranking_snapshots'").get())return empty;
    const checked=new Map<string,string>();
    if(database.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='pvp_http_checks'").get())
      for(const r of database.prepare("SELECT s.private_directory,c.checked_at FROM pvp_http_checks c JOIN pvp_http_sources s USING(capture_id)").all())checked.set(String(r.private_directory),String(r.checked_at));
    const rankingChecks=new Map<string,string>();
    if(database.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='pvp_ranking_checks'").get())
      for(const r of database.prepare("SELECT snapshot_id,max(checked_at) AS checked_at FROM pvp_ranking_checks GROUP BY snapshot_id").all())rankingChecks.set(String(r.snapshot_id),String(r.checked_at));
    return {
      snapshots:database.prepare("SELECT snapshot_id,payload FROM ranking_snapshots ORDER BY captured_at").all().map(r=>{
        const payload=JSON.parse(String(r.payload)) as Record<string,unknown>;
        return rankingChecks.has(String(r.snapshot_id))?{...payload,lastCheckedAt:rankingChecks.get(String(r.snapshot_id))}:payload;
      }),
      current:database.prepare("SELECT scope_label,snapshot_id FROM current_rankings ORDER BY scope_label").all().map(r=>({scope:String(r.scope_label),snapshotId:String(r.snapshot_id)})),
      attempts:database.prepare("SELECT ranking_snapshot_id,player_id,payload FROM ranking_defense_attempts ORDER BY attempted_at").all().map(r=>{
        const payload=JSON.parse(String(r.payload)) as Record<string,unknown>;
        return {snapshotId:String(r.ranking_snapshot_id),playerId:String(r.player_id),payload:{...payload,lastCheckedAt:checked.get(String(payload.captureDirectory))??payload.defenseRetrievedAt??null}};
      }),
    };
  }finally{database.close();}
}

export async function readLatestPvpUpdate(){
  const database=await localDatabase();if(!database)return null;
  try{
    const row=database.prepare("SELECT started_at,finished_at,status,reason_code FROM update_attempts WHERE module='pvp' ORDER BY id DESC LIMIT 1").get();
    return row?{startedAt:String(row.started_at),finishedAt:row.finished_at?String(row.finished_at):null,status:String(row.status),reason:row.reason_code?String(row.reason_code):null}:null;
  }finally{database.close();}
}

export async function readPvpAutoUpdateState(){
  if(process.env.NODE_ENV!=='development')return null;
  try{
    const d=JSON.parse(await readFile(path.join(process.cwd(),'data/research/runtime.private/pvp-auto-state.private.json'),'utf8'));
    if(d.schemaVersion!==1)return null;
    return {enabled:d.enabled===true,paused:d.paused===true,intervalMinutes:Number.isInteger(d.intervalMinutes)&&d.intervalMinutes>0?d.intervalMinutes:10,
      status:['not_started','ready','running','success','failed','skipped','paused'].includes(d.lastStatus)?String(d.lastStatus):'not_started',
      lastStartedAt:typeof d.lastStartedAt==='string'?d.lastStartedAt:null,lastFinishedAt:typeof d.lastFinishedAt==='string'?d.lastFinishedAt:null};
  }catch(error:unknown){if(error instanceof Error&&'code' in error&&error.code==='ENOENT')return null;throw error;}
}

export async function readRankedGuildStore(){
  const database=await localDatabase();if(!database)return null;
  try{
    if(!database.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='guild_rank_sources'").get())return null;
    const source=database.prepare("SELECT r.payload FROM current_guild_rankings c JOIN guild_rank_sources r USING(snapshot_id) WHERE c.scope='top100'").get();
    if(!source)return null;
    const ranking=JSON.parse(String(source.payload)) as {snapshotId:string};
    const checked=database.prepare('SELECT max(checked_at) AS at FROM guild_ranking_checks WHERE snapshot_id=?').get(ranking.snapshotId);
    return {ranking:{...ranking,lastCheckedAt:checked?.at?String(checked.at):undefined} as unknown,
      rosters:database.prepare('SELECT r.payload FROM current_ranked_guild_rosters c JOIN guild_roster_sources r USING(source_id)').all().map(r=>JSON.parse(String(r.payload)) as unknown),
      attempts:database.prepare('SELECT guild_id,part,checked_at,status,reason FROM guild_fetch_attempts ORDER BY checked_at').all().map(r=>({guildId:String(r.guild_id),part:String(r.part),checkedAt:String(r.checked_at),status:String(r.status),reason:r.reason?String(r.reason):null}))};
  }finally{database.close();}
}

export async function readGuildWarStore():Promise<unknown[]>{
  const database=await localDatabase();if(!database)return [];
  try{
    if(!database.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='guild_war_sources'").get())return [];
    return database.prepare('SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id) ORDER BY s.captured_at').all().map(r=>JSON.parse(String(r.payload)) as unknown);
  }finally{database.close();}
}

export async function readGuildAttackFormationStore(guildId: string): Promise<unknown[]> {
  const database = await localDatabase();
  if (!database) return [];
  try {
    const tables = database.prepare(`SELECT count(*) AS total FROM sqlite_master
      WHERE type = 'table' AND name IN ('current_guild_public_formations', 'guild_public_formation_sources')`).get();
    if (Number(tables?.total) !== 2) return [];
    return database.prepare(`SELECT s.payload FROM current_guild_public_formations c
      JOIN guild_public_formation_sources s USING (source_id)
      WHERE c.guild_id = ? AND s.guild_id = c.guild_id AND s.player_id = c.player_id AND s.status = 'success'
      ORDER BY s.captured_at DESC, s.player_id`).all(guildId).map(row => JSON.parse(String(row.payload)) as unknown);
  } finally {
    database.close();
  }
}

export async function readCharacterInstanceProgress(keys:readonly string[]):Promise<Map<string,unknown>>{
 const result=new Map<string,unknown>();if(!keys.length)return result;
 const db=await localDatabase();if(!db)return result;
 try{
  if(!db.prepare("SELECT name FROM sqlite_master WHERE name='current_character_instance_sources'").get())return result;
  const source=db.prepare("SELECT s.source_id,s.payload FROM current_character_instance_sources c JOIN character_instance_sources s USING(source_id) WHERE c.scope='accepted-defense'").get();
  if(!source||typeof source.payload!=='string')return result;
  const meta=JSON.parse(source.payload);
  if(meta.sourceKind!=='accepted-response-character-instances'||meta.templateTrainingSubstituted!==false)return result;
  const ids=[...new Set(keys)].filter(k=>/^[a-f0-9]{64}$/.test(k));
  for(let i=0;i<ids.length;i+=400){const part=ids.slice(i,i+400);
   for(const row of db.prepare(`SELECT observation_id,payload FROM character_instance_progress WHERE source_id=? AND observation_id IN (${part.map(()=>'?').join(',')})`).all(source.source_id,...part)){
    result.set(String(row.observation_id),JSON.parse(String(row.payload)) as unknown);
   }
  }
  return result;
 }finally{db.close();}
}

export async function readCharacterNativeStore(nativeSha:string,ids:readonly string[]=[]):Promise<{sourceId:string;summary:Record<string,number>;index:Map<string,{imageSha:string|null;width:number|null;height:number|null;talentAvailable:boolean}>;details:Map<string,unknown>}|null>{
 if(!/^[a-f0-9]{64}$/.test(nativeSha))return null;
 const db=await localDatabase();if(!db)return null;
 try{
  if(!db.prepare("SELECT name FROM sqlite_master WHERE name='current_character_native_sources'").get())return null;
  const source=db.prepare("SELECT s.source_id,s.payload FROM current_character_native_sources c JOIN character_native_sources s USING(source_id) WHERE c.scope='native-templates'").get();
  if(!source)return null;const meta=JSON.parse(String(source.payload));
  if(meta.sourceKind!=='verified-native-character-enrichment'||meta.nativeDocumentSha256!==nativeSha||meta.moduleSha256!=='1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0'||meta.proof?.groupCodeGetter!=='00c15958'||meta.proof?.enhancementGradePrefix!=='00e5fa60'||meta.proof?.thumbnailFormat!=='0194709c')return null;
  const index=new Map<string,{imageSha:string|null;width:number|null;height:number|null;talentAvailable:boolean}>();
  for(const [id,value] of Object.entries(meta.index??{})){
   const r=value as {image?:{sourceKind?:string;sha256?:string;width?:number;height?:number};talentStatus?:string};if(!/^[A-Za-z0-9_-]+$/.test(id)||!r)continue;
   const image=r.image?.sourceKind==='verified-local-game-thumbnail'&&/^[a-f0-9]{64}$/.test(r.image.sha256??'')&&Number.isInteger(r.image.width)&&Number.isInteger(r.image.height)&&r.image.width!>0&&r.image.height!>0?r.image:null;
   index.set(id,{imageSha:image?.sha256??null,width:image?.width??null,height:image?.height??null,talentAvailable:r.talentStatus==='verified-native-group'});
  }
  const details=new Map<string,unknown>();const keys=[...new Set(ids)].filter(id=>/^[A-Za-z0-9_-]+$/.test(id));
  for(let i=0;i<keys.length;i+=400){const part=keys.slice(i,i+400);for(const row of db.prepare(`SELECT character_id,payload FROM character_native_details WHERE source_id=? AND character_id IN (${part.map(()=>'?').join(',')})`).all(source.source_id,...part))details.set(String(row.character_id),JSON.parse(String(row.payload)) as unknown);}
  return {sourceId:String(source.source_id),summary:{images:Number(meta.summary?.images??0),talentCharacters:Number(meta.summary?.charactersWithNativeTalentGroup??0),...(Number.isSafeInteger(meta.summary?.not_configured)&&meta.summary.not_configured>=0?{talentsAbsent:meta.summary.not_configured}:{})},index,details};
 }finally{db.close();}
}

export async function readLocalCharacterAsset(id:string):Promise<{path:string;sha256:string}|null>{
 if(!/^[A-Za-z0-9_-]{1,160}$/.test(id))return null;
 const db=await localDatabase();if(!db)return null;
 try{
  if(!db.prepare("SELECT name FROM sqlite_master WHERE name='current_character_native_sources'").get())return null;
  const row=db.prepare(`SELECT d.payload FROM current_character_native_sources c JOIN character_native_sources s USING(source_id)
   JOIN character_native_details d USING(source_id) JOIN current_documents b ON b.filename='verified-characters.json'
   WHERE c.scope='native-templates' AND d.character_id=? AND json_extract(s.payload,'$.nativeDocumentSha256')=b.sha256
   AND json_extract(s.payload,'$.sourceKind')='verified-native-character-enrichment' AND json_extract(s.payload,'$.proof.thumbnailFormat')='0194709c'
   AND json_extract(s.payload,'$.moduleSha256')='1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0'`).get(id);
  if(!row)return null;const image=JSON.parse(String(row.payload)).image;
  if(image?.sourceKind!=='verified-local-game-thumbnail'||typeof image.path!=='string'||!/^[a-f0-9]{64}$/.test(image.sha256??''))return null;
  const base=`data/extracted/lr_20261116T212608096_7b99bdd0/apk_contents/base/assets/res/tutorial_res/hd/${id}/${id}-thum.png`;
  const cache=new RegExp(`^data/research/runtime\\.private/character-thumbnails-[A-Za-z0-9-]+/${id}\\.png$`);
  if(image.path!==base&&!cache.test(image.path))return null;
  return {path:image.path,sha256:image.sha256};
 }finally{db.close();}
}

export async function readRankedSnapshotKeys():Promise<Set<string>>{
  const store=await readRankingStore();const keys=new Set<string>();
  for(const row of store.attempts){const payload=row.payload as {status?:string;defenseSnapshotIds?:unknown};
    if((payload.status==='success'||payload.status==='partial')&&Array.isArray(payload.defenseSnapshotIds))
      for(const id of payload.defenseSnapshotIds)if(typeof id==='string')keys.add(JSON.stringify([row.playerId,id]));
  }
  return keys;
}

/** Keep the existing field whitelists; change only the server-side storage source. */
export async function readNormalizedText(filename: string): Promise<string> {
  if (!filenames.has(filename)) throw new Error("不支援的資料來源");
  const configured = process.env.LR_LOCAL_DATABASE_PATH;
  if (!configured || process.env.NODE_ENV !== "development") {
    return readFile(path.join(process.cwd(), "data/normalized", filename), "utf8");
  }
  const database = (await localDatabase())!;
  try {
    const row = database.prepare("SELECT d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename=?").get(filename);
    if (!row || typeof row.payload !== "string") throw new Error("資料庫尚未匯入此模組");
    return row.payload;
  } finally { database.close(); }
}
