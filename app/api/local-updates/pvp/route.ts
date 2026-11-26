import {readPvpAutoUpdateState} from '../../../../lib/local-game-data';
import {startLocalPvpUpdate} from '../../../../lib/start-local-pvp-update';
export const runtime='nodejs';
const headers={'Cache-Control':'no-store'};
function local(request:Request){
 if(process.env.NODE_ENV!=='development'||!process.env.LR_LOCAL_DATABASE_PATH)return false;
 const url=new URL(request.url);if(!['127.0.0.1','localhost'].includes(url.hostname))return false;
 // Next may normalize request.url to localhost while the browser uses
 // 127.0.0.1. Compare Origin with the validated actual Host, not that alias.
 try{
  const host=request.headers.get('host')??url.host;
  const browserUrl=new URL(`${url.protocol}//${host}`);
  if(!['127.0.0.1','localhost'].includes(browserUrl.hostname)||browserUrl.host!==host.toLowerCase())return false;
  const origin=request.headers.get('origin');return !origin||origin===browserUrl.origin;
 }catch{return false;}
}
export async function GET(request:Request){
 if(!local(request))return Response.json({status:'unavailable'},{status:403,headers});
 return Response.json({state:await readPvpAutoUpdateState()},{headers});
}
export async function POST(request:Request){
 if(!local(request))return Response.json({status:'unavailable'},{status:403,headers});
 const state=await readPvpAutoUpdateState();
 if(!state?.enabled||state.paused)return Response.json({status:'paused_or_disabled',state},{status:409,headers});
 if(state.status==='running')return Response.json({status:'already_running',state},{status:202,headers});
 try{await startLocalPvpUpdate();return Response.json({status:'starting',state},{status:202,headers});}
 catch{return Response.json({status:'local_task_unavailable',state},{status:503,headers});}
}
