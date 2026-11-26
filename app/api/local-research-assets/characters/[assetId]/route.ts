import {readFile,realpath,stat} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {readLocalCharacterAsset} from '../../../../../lib/local-game-data';
export const dynamic='force-dynamic';
export async function GET(request:Request,{params}:{params:Promise<{assetId:string}>}){
 if(process.env.NODE_ENV!=='development'||!['localhost','127.0.0.1','[::1]'].includes(new URL(request.url).hostname))return new Response(null,{status:404});
 const {assetId}=await params;if(!/^[A-Za-z0-9_-]{1,160}$/.test(assetId))return new Response(null,{status:404});
 const mapping=await readLocalCharacterAsset(assetId);const expected=mapping?.sha256;
 if(!expected)return new Response(null,{status:404});
 try{
  const root=await realpath(path.join(process.cwd(),'data'));
  const file=await realpath(path.join(process.cwd(),mapping!.path));const relative=path.relative(root,file);
  if(!relative||relative==='..'||relative.startsWith('..'+path.sep)||path.isAbsolute(relative))return new Response(null,{status:404});
  const info=await stat(file);if(!info.isFile()||info.size>2*1024*1024)return new Response(null,{status:404});
  const bytes=await readFile(file);
  if(createHash('sha256').update(bytes).digest('hex')!==expected)return new Response(null,{status:404});
  return new Response(new Uint8Array(bytes),{headers:{'Content-Type':'image/png','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}});
 }catch(e){if(e instanceof Error&&'code'in e&&e.code==='ENOENT')return new Response(null,{status:404});throw e;}
}
