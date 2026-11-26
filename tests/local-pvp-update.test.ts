import {describe,it,expect,vi,beforeEach,afterEach} from 'vitest';
vi.mock('server-only',()=>({}));
const mock=vi.hoisted(()=>({state:{enabled:true,paused:false,status:'ready'} as Record<string,unknown>,start:vi.fn()}));
vi.mock('../lib/local-game-data',()=>({readPvpAutoUpdateState:async()=>mock.state}));
vi.mock('../lib/start-local-pvp-update',()=>({startLocalPvpUpdate:mock.start}));
import {GET,POST} from '../app/api/local-updates/pvp/route';
const request=(origin='http://127.0.0.1:3101')=>new Request('http://127.0.0.1:3101/api/local-updates/pvp',{method:'POST',headers:{origin}});
beforeEach(()=>{vi.stubEnv('NODE_ENV','development');vi.stubEnv('LR_LOCAL_DATABASE_PATH','data/local/lr.private.sqlite');mock.state={enabled:true,paused:false,status:'ready'};mock.start.mockReset().mockResolvedValue(undefined);});
afterEach(()=>vi.unstubAllEnvs());
describe('local immediate PVP update',()=>{
 it('starts only the fixed local task, while GET is read only',async()=>{
  expect((await GET(request())).status).toBe(200);expect(mock.start).not.toHaveBeenCalled();
  expect((await POST(request())).status).toBe(202);expect(mock.start).toHaveBeenCalledTimes(1);
 });
 it('does not start another task while running or when paused',async()=>{
  mock.state.status='running';expect((await POST(request())).status).toBe(202);
  mock.state.paused=true;expect((await POST(request())).status).toBe(409);expect(mock.start).not.toHaveBeenCalled();
 });
 it('does not expose update execution across origins or in production',async()=>{
  expect((await POST(request('https://fixture.invalid'))).status).toBe(403);vi.stubEnv('NODE_ENV','production');expect((await POST(request())).status).toBe(403);expect(mock.start).not.toHaveBeenCalled();
 });
 it('uses the actual loopback Host when Next normalizes its internal URL',async()=>{
  const local=new Request('http://localhost:3101/api/local-updates/pvp',{method:'POST',headers:{host:'127.0.0.1:3101',origin:'http://127.0.0.1:3101'}});
  expect((await POST(local)).status).toBe(202);expect(mock.start).toHaveBeenCalledTimes(1);
  for(const headers of [{host:'fixture.invalid',origin:'http://fixture.invalid'},{host:'127.0.0.1:3101',origin:'http://127.0.0.1:9999'}]){
   expect((await POST(new Request(local.url,{method:'POST',headers}))).status).toBe(403);
  }
  expect(mock.start).toHaveBeenCalledTimes(1);
 });
});
