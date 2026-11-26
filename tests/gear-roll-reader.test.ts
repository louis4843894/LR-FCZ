import {describe,it,expect,vi,afterEach} from 'vitest';
import {DatabaseSync} from 'node:sqlite';
import {mkdirSync,rmSync} from 'node:fs';
import path from 'node:path';
vi.mock('server-only',()=>({}));
import {readNativeGearRolls} from '../lib/local-game-data';
const relative=`data/local/fixture-roll-reader-${process.pid}.sqlite`;const file=path.resolve(relative);
afterEach(()=>{vi.unstubAllEnvs();rmSync(file,{force:true});});
function source(calibration:unknown){
 mkdirSync(path.dirname(file),{recursive:true});const db=new DatabaseSync(file);
 db.exec('CREATE TABLE gear_roll_sources(source_id TEXT,payload TEXT);CREATE TABLE current_gear_rolls(scope TEXT,source_id TEXT);CREATE TABLE gear_instance_rolls(source_id TEXT,observation_id TEXT,payload TEXT);');
 db.prepare('INSERT INTO gear_roll_sources VALUES (?,?)').run('fixture',JSON.stringify({sourceKind:'calibrated-native-definition-http-rolls',moduleSha256:'1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0',externalReferenceValuesUsed:false,calibration}));
 db.prepare('INSERT INTO current_gear_rolls VALUES (?,?)').run('ranked-http','fixture');
 db.prepare('INSERT INTO gear_instance_rolls VALUES (?,?,?)').run('fixture','observation',JSON.stringify({observationId:'observation',equipmentId:'eq_fixture',enhancement:5,instanceGrade:9,equipmentInstanceHash:'fixture-hash',factorCapturedAt:'2026-11-26T00:00:00Z',privateDiagnostic:'fixture-do-not-expose',entries:[{index:0,attributeId:1,valueGradeRaw:1,sourceField:'attr1No',value:24,unit:'PERCENT',enhancementIncluded:true,valueVerified:true,privateDiagnostic:'fixture-do-not-expose',valueVisuallyVerified:true}]}));
 db.close();vi.stubEnv('NODE_ENV','development');vi.stubEnv('LR_LOCAL_DATABASE_PATH',relative);
}
describe('derived gear source reader',()=>{
 it('whitelists verified guild special text and withholds it when native proof is absent',async()=>{
  source({screenCheckedGearCount:2,screenCheckedValueCount:6});const db=new DatabaseSync(file);
  const meta=JSON.parse(String(db.prepare('SELECT payload FROM gear_roll_sources').get()?.payload));
  meta.sourceKind='calibrated-native-definition-guildwar-rolls';meta.optionProof={normalFunction:'0122e270',talentDescriptionFunction:'0122e690',placeholderFormatter:'0122c704'};
  db.prepare('UPDATE gear_roll_sources SET payload=?').run(JSON.stringify(meta));db.prepare('UPDATE current_gear_rolls SET scope=?').run('guildwar');
  const item=JSON.parse(String(db.prepare('SELECT payload FROM gear_instance_rolls').get()?.payload));
  item.supplementarySpecial={state:'values_reconstructed',name:'光之盔甲',normalText:'降低傷害 +23.9%',description:'反射26.7%的物理傷害',specialEnhancement:5,valueVerified:true,enhancementIncluded:true,activationState:'not_verified',valueVisuallyVerified:true,rawFields:{privateDiagnostic:'fixture-do-not-expose'}};
  db.prepare('UPDATE gear_instance_rolls SET payload=?').run(JSON.stringify(item));db.close();
  const values=await readNativeGearRolls(['observation'],'guildwar');expect(values.get('observation')?.extraSpecial).toMatchObject({name:'光之盔甲',valueVisuallyVerified:false,activationState:'not_verified'});
  expect(JSON.stringify([...values])).not.toContain('fixture-do-not-expose');expect(JSON.stringify([...values])).not.toContain('rawFields');
  const changed=new DatabaseSync(file);delete meta.optionProof;changed.prepare('UPDATE gear_roll_sources SET payload=?').run(JSON.stringify(meta));changed.close();
  const withheld=(await readNativeGearRolls(['observation'],'guildwar')).get('observation');expect(withheld?.extraSpecial).toBeUndefined();expect(withheld?.extraSpecialObserved).toBe(true);
 });
 it('rejects missing calibration instead of treating undefined counts as verified',async()=>{
  source(undefined);await expect(readNativeGearRolls(['observation'])).rejects.toThrow('未驗證');
 });
 it('whitelists values and cannot copy a diagnostic or a false visual-review claim',async()=>{
  source({screenCheckedGearCount:2,screenCheckedValueCount:6});const values=await readNativeGearRolls(['observation']);
  expect(values.get('observation')?.entries[0]).toMatchObject({value:24,enhancementIncluded:true,valueVisuallyVerified:false});expect(JSON.stringify([...values])).not.toContain('fixture-do-not-expose');
 });
});
