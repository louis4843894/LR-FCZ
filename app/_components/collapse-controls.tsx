'use client';
import {useEffect,useRef} from 'react';

/** Native details keep individual keyboard controls and require no extra stored state. */
export function CollapseControls(){
  const ref=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    const scope=ref.current?.closest('[data-collapse-scope]');if(!scope)return;
    const reveal=()=>{
      let id:string;try{id=decodeURIComponent(location.hash.slice(1));}catch{return;}
      const target=document.getElementById(id);if(!target||!scope.contains(target))return;
      let p:HTMLElement|null=target;
      while(p&&scope.contains(p)){if(p instanceof HTMLDetailsElement)p.open=true;p=p.parentElement;}
    };
    reveal();window.addEventListener('hashchange',reveal);return()=>window.removeEventListener('hashchange',reveal);
  },[]);
  const toggle=(open:boolean)=>ref.current?.closest('[data-collapse-scope]')?.querySelectorAll<HTMLDetailsElement>('details').forEach(d=>{d.open=open;});
  return <div className="collapse-controls" ref={ref} aria-label="內容展開與收合"><button type="button" onClick={()=>toggle(true)}>全部展開</button><button type="button" onClick={()=>toggle(false)}>全部收合</button></div>;
}
