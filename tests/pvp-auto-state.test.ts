import {it,expect,vi,afterEach} from 'vitest';
vi.mock('server-only',()=>({}));
vi.mock('node:fs/promises',()=>({readFile:async()=>JSON.stringify({schemaVersion:1,enabled:true,paused:false,intervalMinutes:10,lastStatus:'running',cookie:'fixture-private-secret',headers:{authorization:'fixture-secret'}})}));
import {readPvpAutoUpdateState} from '../lib/local-game-data';
afterEach(()=>vi.unstubAllEnvs());
it('exports only display status, never arbitrary worker state fields',async()=>{
 vi.stubEnv('NODE_ENV','development');const state=await readPvpAutoUpdateState();expect(state).toMatchObject({enabled:true,intervalMinutes:10,status:'running'});expect(JSON.stringify(state)).not.toContain('fixture-');
 vi.stubEnv('NODE_ENV','production');expect(await readPvpAutoUpdateState()).toBeNull();
});
