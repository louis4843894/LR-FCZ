import {createHash} from 'node:crypto';
import {getCharacterReference} from '../../../lib/character-reference';
import {publicCharacterDetails} from '../../../lib/character-details';
import {publicNativeTalents} from '../../../lib/character-native';
import {getVerifiedEquipmentList} from '../../../lib/verified-equipment';
import {getLocalGearIconUrl} from '../../../lib/local-research-assets';
import {getGuildRankings,getRankedGuild} from '../../../lib/guild-rankings';
import {getPvpRankings,isRankingSnapshotId,type RankingAttempt} from '../../../lib/pvp-rankings';
import {getAcquisitionProgress} from '../../../lib/acquisition-progress';
import {getDefenseTeams} from '../../../lib/defense-teams';
import {pvpViewerTeams,viewerReference} from '../../../lib/defense-viewer-data';
import {localDatabase,readCharacterDetailStore,readCharacterNativeStore,readRankingStore} from '../../../lib/local-game-data';
import {activePvpScope} from '../../../lib/pvp-scopes';
import {assertSiteDisplaySafe,type DisplayDefense} from '../../../lib/site-display-contract';

export const dynamic='force-dynamic';
const hash=(s:string,n=12)=>createHash('sha256').update(s).digest('hex').slice(0,n);
const safeResponse=(data:unknown)=>{assertSiteDisplaySafe(data);return Response.json(data,{headers:{'Cache-Control':'no-store'}});};

/** Local-only read/export boundary. It cannot fetch game data or publish files. */
export async function GET(request:Request){
  const url=new URL(request.url);
  if(process.env.NODE_ENV!=='development'||!['localhost','127.0.0.1','[::1]'].includes(url.hostname))return new Response(null,{status:404});
  const part=url.searchParams.get('part');
  if(part==='catalogs'){
    const [characters,equipment]=await Promise.all([getCharacterReference(),getVerifiedEquipmentList()]);
    if(!characters||!equipment.length)return new Response(null,{status:409});
    const gearIcons=Object.fromEntries((await Promise.all(equipment.map(async e=>[e.itemCode,await getLocalGearIconUrl(e.dataCode)] as const))).filter((r):r is readonly [string,string]=>r[1]!==null));
    return safeResponse({characters,equipment:equipment.map(e=>({...e,reference:viewerReference(e.reference)})),gearIcons});
  }
  if(part==='character-details'){
    const source=await getCharacterReference();if(!source)return new Response(null,{status:409});
    const [details,native]=await Promise.all([readCharacterDetailStore(source.nativeSha),readCharacterNativeStore(source.nativeSha,source.records.map(r=>r.characterId))]);
    const db=await localDatabase();if(!db||!details||!native)return new Response(null,{status:409});
    try{
      const raw=new Map(db.prepare("SELECT d.character_id,d.payload FROM current_character_details c JOIN character_template_details d USING(source_id) WHERE c.scope='native-matched-reference'").all().map(row=>[String(row.character_id),JSON.parse(String(row.payload)) as unknown]));
      return safeResponse(Object.fromEntries(source.records.map(row=>[row.characterId,{row,details:publicCharacterDetails(raw.get(row.characterId),row.characterId),detailStatus:details.index.get(row.characterId)?.status??'not_acquired',nativeTalents:publicNativeTalents(native.details.get(row.characterId),row.characterId),retrievedAt:source.retrievedAt,detailsRetrievedAt:details.retrievedAt}])));
    }finally{db.close();}
  }
  if(part==='guilds')return safeResponse(await getGuildRankings());
  if(part==='guild'){
    const data=await getRankedGuild(url.searchParams.get('alias')??'');if(!data)return new Response(null,{status:404});
    // Personal saved configurations and research-only raw grades are not published.
    if(data.war)data.war.savedConfigurations=[];
    const display=JSON.parse(JSON.stringify(data,(key,value)=>key==='effectIdentifiers'?undefined:key==='reference'?viewerReference(value):value));
    return safeResponse(display);
  }
  if(part==='pvp-index')return safeResponse((await getPvpRankings())?.scopes??[]);
  if(part==='pvp'){
    const scope=url.searchParams.get('scope')??'';
    const variants:Record<string,unknown>={};
    for(const top of [10,30,50,100,200,1000])variants[String(top)]=await getPvpRankings(scope,top);
    return safeResponse(variants);
  }
  if(part==='defenses'){
    const store=await readRankingStore();
    const current=new Set(store.current.filter(r=>activePvpScope(r.scope)).map(r=>r.snapshotId));
    const attempts=new Map<string,RankingAttempt>();const latest=new Map<string,RankingAttempt>();
    for(const row of store.attempts)if(current.has(row.snapshotId)){
      const key=JSON.stringify([row.snapshotId,row.playerId]);const attempt=row.payload as RankingAttempt;latest.set(key,attempt);
      if(attempt.status==='success'||attempt.status==='partial')attempts.set(key,attempt);
    }
    const wanted=new Set([...attempts.values()].flatMap(a=>a.defenseSnapshotIds));
    const teams=await getDefenseTeams('pvp_defense',undefined,{snapshotIds:wanted,keepSnapshots:true});if(!teams)return new Response(null,{status:409});
    const documents=store.snapshots as {snapshotId:string;scope:{label:string};capturedAt:string;players:{playerId:string;rank:number;score:number;displayName:string|null}[]}[];
    const files:Record<string,DisplayDefense>={};
    for(const doc of documents)if(current.has(doc.snapshotId)&&isRankingSnapshotId(doc.snapshotId))for(const player of doc.players){
      const key=JSON.stringify([doc.snapshotId,player.playerId]);const a=attempts.get(key);if(!a)continue;
      const alias=hash(player.playerId);const selected=teams.filter(t=>t.playerId===`本機玩家-${alias}`&&a.defenseSnapshotIds.includes(t.snapshotId));
      if(!selected.length)throw new Error('排名防禦顯示關聯缺漏');
      files[`defense-${alias}-${doc.snapshotId.slice(-24)}`]={displayPlayers:[{title:player.displayName??'排名玩家',teams:pvpViewerTeams(selected)}],rankingContext:{scopeLabel:doc.scope.label,rank:player.rank,score:player.score,snapshotId:doc.snapshotId,rankingCapturedAt:doc.capturedAt,lastCheckedAt:a.lastCheckedAt??null,cacheState:a.cacheState??null,latestStatus:latest.get(key)?.status??a.status}};
    }
    return safeResponse(files);
  }
  if(part==='status'){
    const data=await getAcquisitionProgress();return safeResponse(data?{...data,storage:'已驗證網站顯示資料'}:null);
  }
  return new Response(null,{status:400});
}
