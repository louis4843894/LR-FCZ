// Captures only game_item_equip database. Never logs passphrases or account DBs.
'use strict';
const targetName='game_item_equip.db';
const output='/data/local/tmp/lr-equip-capture.private.json';
let captured=false,busy=false;
function rows(db,sql){const c=db.rawQuery(sql,null);const result=[];try{const cols=Array.from(c.getColumnNames()).map(String);while(c.moveToNext()){let row={};for(let i=0;i<cols.length;i++){const t=c.getType(i);row[cols[i]]=t===0?null:t===1?Number(c.getLong(i)):t===2?c.getDouble(i):t===4?{blobBytes:c.getBlob(i).length}:String(c.getString(i));}result.push(row);}return result;}finally{c.close();}}
function capture(db,path){if(captured||busy||!path.endsWith('/'+targetName))return;busy=true;try{
 const schema=rows(db,"SELECT type,name,sql FROM sqlite_master WHERE type='table' ORDER BY name");
 const integrity=rows(db,'PRAGMA integrity_check');const tables={};
 for(const t of schema){if(t.name.startsWith('sqlite_'))continue;const q='"'+t.name.replace(/"/g,'""')+'"';tables[t.name]={columns:rows(db,'PRAGMA table_info('+q+')'),rows:rows(db,'SELECT * FROM '+q)};}
 const payload={source:path,captureKind:'SQLCipher-live-query',arch:Process.arch,integrity,schema,tables,modules:Process.enumerateModules().filter(m=>/libgame|sqlcipher|houdini/i.test(m.name)).map(m=>({name:m.name,base:String(m.base),size:m.size,path:m.path}))};
 const f=new File(output,'w');f.write(JSON.stringify(payload));f.close();captured=true;
 console.log('EQUIP_CAPTURE_OK '+JSON.stringify({path,output,tables:Object.fromEntries(Object.entries(tables).map(([n,t])=>[n,t.rows.length])),integrity}));
 try{db.execSQL("ATTACH DATABASE '/data/local/tmp/lr-equip-decoded.private.db' AS lr_plain KEY ''");const c=db.rawQuery("SELECT sqlcipher_export('lr_plain')",null);try{c.moveToFirst();}finally{c.close();}db.execSQL('DETACH DATABASE lr_plain');console.log('EQUIP_PLAINTEXT_EXPORT_OK');}catch(e){console.log('EQUIP_PLAINTEXT_EXPORT_UNAVAILABLE '+String(e));}
}catch(e){console.log('EQUIP_CAPTURE_ERROR '+String(e));}finally{busy=false;}}
Java.perform(function(){
 const name='net.zetetic.database.sqlcipher.SQLiteDatabase';
 try{const DB=Java.use(name);console.log('SQLCIPHER_CLASS_READY '+name);
 for(const method of ['openDatabase','openOrCreateDatabase']){if(!DB[method])continue;for(const ov of DB[method].overloads){ov.implementation=function(){const a=Array.from(arguments);const db=ov.apply(this,a);try{let path=String(db.getPath());if(path.endsWith('/'+targetName))capture(db,path);}catch(e){console.log('EQUIP_PATH_CHECK_ERROR '+String(e));}return db;};}}
 // Also catch an already-open target when its first query arrives.
 for(const ov of DB.rawQuery.overloads){ov.implementation=function(){if(!busy&&!captured){try{const path=String(this.getPath());if(path.endsWith('/'+targetName))capture(this,path);}catch(e){}}return ov.apply(this,arguments);};}
 console.log('SQLCIPHER_HOOKS_READY');
 }catch(e){console.log('SQLCIPHER_CLASS_UNAVAILABLE '+String(e));}
});
