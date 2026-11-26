import {it,expect,vi,afterEach} from 'vitest';
import {DatabaseSync} from 'node:sqlite';
import {rmSync} from 'node:fs';
vi.mock('server-only',()=>({}));
import {readLocalCharacterAsset} from '../lib/local-game-data';
const file=`data/local/fixture-character-asset-${process.pid}.sqlite`;const sha='a'.repeat(64);
afterEach(()=>{vi.unstubAllEnvs();rmSync(file,{force:true});});
function fixture(imagePath='data/research/runtime.private/character-thumbnails-fixture/fixture.png'){
 const db=new DatabaseSync(file);db.exec('CREATE TABLE current_documents(filename TEXT,sha256 TEXT);CREATE TABLE current_character_native_sources(scope TEXT,source_id TEXT);CREATE TABLE character_native_sources(source_id TEXT,payload TEXT);CREATE TABLE character_native_details(source_id TEXT,character_id TEXT,payload TEXT);');
 db.prepare('INSERT INTO current_documents VALUES (?,?)').run('verified-characters.json',sha);
 db.prepare('INSERT INTO current_character_native_sources VALUES (?,?)').run('native-templates','native');
 db.prepare('INSERT INTO character_native_sources VALUES (?,?)').run('native',JSON.stringify({nativeDocumentSha256:sha,sourceKind:'verified-native-character-enrichment',proof:{thumbnailFormat:'0194709c'},moduleSha256:'1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0'}));
 db.prepare('INSERT INTO character_native_details VALUES (?,?,?)').run('native','fixture',JSON.stringify({image:{sourceKind:'verified-local-game-thumbnail',path:imagePath,sha256:sha}}));
 db.close();vi.stubEnv('NODE_ENV','development');vi.stubEnv('LR_LOCAL_DATABASE_PATH',file);
}
it('serves only the accepted native asset mapping and a safe ID',async()=>{
 fixture();expect(await readLocalCharacterAsset('fixture')).toEqual({path:'data/research/runtime.private/character-thumbnails-fixture/fixture.png',sha256:sha});
 expect(await readLocalCharacterAsset('../fixture')).toBeNull();expect(await readLocalCharacterAsset('unknown')).toBeNull();
});
it('rejects unsafe paths and stale native template versions',async()=>{
 fixture('data/local/private.png');expect(await readLocalCharacterAsset('fixture')).toBeNull();
 const db=new DatabaseSync(file);db.prepare('UPDATE current_documents SET sha256=?').run('b'.repeat(64));db.close();expect(await readLocalCharacterAsset('fixture')).toBeNull();
});
