import {describe,it,expect,vi,afterEach} from 'vitest';
import {DatabaseSync} from 'node:sqlite';
import {mkdirSync,rmSync} from 'node:fs';
import path from 'node:path';
vi.mock('server-only',()=>({}));
import {readCharacterDetailStore} from '../lib/local-game-data';
import {getCharacterReference} from '../lib/character-reference';
const relative=`data/local/fixture-character-detail-${process.pid}.sqlite`;const file=path.resolve(relative);const nativeSha='1'.repeat(64);
afterEach(()=>{vi.unstubAllEnvs();rmSync(file,{force:true});});
function source(overrides:Record<string,unknown>={}){
 mkdirSync(path.dirname(file),{recursive:true});const db=new DatabaseSync(file);
 db.exec('CREATE TABLE current_character_details(scope TEXT,source_id TEXT);CREATE TABLE character_detail_sources(source_id TEXT,payload TEXT);CREATE TABLE character_template_details(source_id TEXT,character_id TEXT,payload TEXT);');
 const metadata={sourceKind:'native-matched-user-confirmed-character-details',nativeDocumentSha256:nativeSha,templateOnly:true,localNumericVerification:false,playerTrainingOrEquipmentApplied:false,awakeningCandidatesAreNotPlayerAwakening:true,
 retrievedAt:'2026-11-26T00:00:00Z',summary:{nativeCharacters:2,skillsCharacters:1},index:{fixture:{status:'matched-reference',skillCount:0,abilityCount:2,awakeningCount:3,talentsAvailable:true},unknown:{status:'not_in_reference',skillCount:null,abilityCount:null,awakeningCount:null,talentsAvailable:false}},...overrides};
 db.prepare('INSERT INTO character_detail_sources VALUES (?,?)').run('fixture',JSON.stringify(metadata));db.prepare('INSERT INTO current_character_details VALUES (?,?)').run('native-matched-reference','fixture');
 db.prepare('INSERT INTO character_template_details VALUES (?,?,?)').run('fixture','fixture',JSON.stringify({characterId:'fixture',status:'matched-reference',skills:[]}));db.close();
 vi.stubEnv('NODE_ENV','development');vi.stubEnv('LR_LOCAL_DATABASE_PATH',relative);
}
describe('character detail source matches the accepted native document',()=>{
 it('uses the accepted file hash rather than rehashing canonical SQLite JSON',async()=>{
  source();const db=new DatabaseSync(file);db.exec('CREATE TABLE documents(sha256 TEXT,payload TEXT);CREATE TABLE current_documents(filename TEXT,sha256 TEXT);');
  db.prepare('INSERT INTO documents VALUES (?,?)').run(nativeSha,JSON.stringify({sourceKind:'verified-character-template',localVerification:true,capturedAt:1,records:[{characterId:'fixture',name:'測試',description:null,starCount:9,unitCategory:'STR',unitElement:'none'}]}));
  db.prepare('INSERT INTO current_documents VALUES (?,?)').run('verified-characters.json',nativeSha);db.close();
  const result=await getCharacterReference();expect(result?.nativeSha).toBe(nativeSha);expect(result?.records[0].skillCount).toBe(0);expect(result?.records[0].awakeningCount).toBe(3);
 });
 it('retains unknown vs empty counts and can load one character without all details',async()=>{
  source();const summary=await readCharacterDetailStore(nativeSha);expect(summary?.index.get('fixture')?.skillCount).toBe(0);expect(summary?.index.get('unknown')?.skillCount).toBeNull();expect(summary?.detail).toBeNull();
  expect((await readCharacterDetailStore(nativeSha,'fixture'))?.detail).toMatchObject({characterId:'fixture',skills:[]});
 });
 it('withholds stale native versions and a claim that reference numbers are native',async()=>{
  source();expect(await readCharacterDetailStore('2'.repeat(64))).toBeNull();
  const db=new DatabaseSync(file);const meta=JSON.parse(String(db.prepare('SELECT payload FROM character_detail_sources').get()?.payload));meta.localNumericVerification=true;db.prepare('UPDATE character_detail_sources SET payload=?').run(JSON.stringify(meta));db.close();
  expect(await readCharacterDetailStore(nativeSha,'fixture')).toBeNull();
 });
});
