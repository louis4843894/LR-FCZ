"use client";
import {useEffect,useState} from 'react';
import {useRouter} from 'next/navigation';
import type {readPvpAutoUpdateState} from '../../lib/local-game-data';
type State=NonNullable<Awaited<ReturnType<typeof readPvpAutoUpdateState>>>;
const descriptions:Record<string,string>={not_started:'等待首次執行',ready:'等待下一次執行',running:'正在更新排行與防禦',success:'上次更新完成',failed:'本次未完整完成，既有有效版本保留',skipped:'已有更新執行，略過重複啟動',paused:'自動更新已暫停，等待本機確認'};
export function PvpUpdateControls({initial}:{initial:State}){
 const [state,setState]=useState(initial);const [pending,setPending]=useState(false);const [message,setMessage]=useState('');const router=useRouter();
 useEffect(()=>{
  let active=true;let last=initial.status;
  const timer=setInterval(async()=>{
   try{
    const r=await fetch('/api/local-updates/pvp',{cache:'no-store'});if(!r.ok)return;const d=await r.json();
    if(active&&d.state){setState(d.state);if(last==='running'&&d.state.status!=='running'){setMessage('更新執行已結束；返回排行榜可查看目前版本。');router.refresh();}last=d.state.status;}
   }catch{/* Preserve the last known state when local preview is unavailable. */}
  },10000);
  return()=>{active=false;clearInterval(timer);};
 },[initial.status,router]);
 async function update(){
  setPending(true);setMessage('');
  try{
   const r=await fetch('/api/local-updates/pvp',{method:'POST',headers:{'Content-Type':'application/json'}});const d=await r.json();
   if(r.ok){setMessage(d.status==='already_running'?'已有更新正在執行。':'已排入立即更新；配置未變時會沿用有效快取。');if(d.state)setState(d.state);}
   else setMessage(d.status==='paused_or_disabled'?'自動更新已暫停或未啟用，請先在本機確認遊戲工作階段。':'目前無法啟動更新，既有資料仍可查看。');
  }catch{setMessage('本機更新服務暫時無法連線，既有資料仍可查看。');}
  finally{setPending(false);}
 }
 return <div className="pvp-update-controls"><button className="button button-primary" data-action="update-pvp" onClick={update} disabled={pending||state.paused||state.status==='running'}>{pending?'正在排程':state.status==='running'?'正在更新':'立即更新 PVP'}</button><span role="status">{message||(state.paused?'自動更新已暫停，等待本機確認':descriptions[state.status])}</span></div>;
}
