// Observe only equipment file I/O; never collect keys or other files.
const watchedFds=new Set(), watchedStreams=new Set();
function stack(c){try{return Thread.backtrace(c,Backtracer.ACCURATE).slice(0,16).map(a=>DebugSymbol.fromAddress(a).toString());}catch(e){return[];}}
function log(o){send(o);}
function hook(name,callbacks){try{const a=Module.findGlobalExportByName(name);if(a)Interceptor.attach(a,callbacks);}catch(e){log({event:'hook-error',name,error:String(e)});}}
for(const name of ['open','open64','openat'])hook(name,{onEnter(a){this.path=null;try{const s=a[name==='openat'?1:0].readUtf8String();if(s.includes('/game_item_equip/')||s.endsWith('/game_item_equip.db')){this.path=s;this.stack=stack(this.context);}}catch(e){}},onLeave(r){if(this.path){watchedFds.add(r.toInt32());log({event:'open',path:this.path,fd:r.toInt32(),stack:this.stack});}}});
for(const name of ['fopen','fopen64'])hook(name,{onEnter(a){this.path=null;try{const s=a[0].readUtf8String();if(s.includes('/game_item_equip/')||s.endsWith('/game_item_equip.db')){this.path=s;this.stack=stack(this.context);}}catch(e){}},onLeave(r){if(this.path){watchedStreams.add(r.toString());log({event:'fopen',path:this.path,stream:r.toString(),stack:this.stack});}}});
hook('read',{onEnter(a){this.fd=a[0].toInt32();this.buf=a[1];},onLeave(r){const n=r.toInt32();if(watchedFds.has(this.fd)&&n>0){log({event:'read',fd:this.fd,bytes:n,buffer:this.buf.toString(),stack:stack(this.context)});}}});
hook('fread',{onEnter(a){this.buf=a[0];this.unit=a[1].toInt32();this.stream=a[3].toString();},onLeave(r){const n=r.toInt32()*this.unit;if(watchedStreams.has(this.stream)&&n>0)log({event:'fread',bytes:n,buffer:this.buf.toString(),stack:stack(this.context)});}});
hook('close',{onEnter(a){watchedFds.delete(a[0].toInt32());}});
hook('fclose',{onEnter(a){watchedStreams.delete(a[0].toString());}});
rpc.exports={status(){return {arch:Process.arch,modules:Process.enumerateModules().filter(m=>/libgame|sqlcipher|houdini|ndk_translation/i.test(m.name)).map(m=>({name:m.name,base:m.base.toString(),size:m.size,path:m.path}))};}};
log({event:'ready',arch:Process.arch});
