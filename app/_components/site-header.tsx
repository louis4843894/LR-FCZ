"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const modules=[{href:"/",label:"首頁",symbol:"⌂"},{href:"/characters",label:"Rangers 角色",symbol:"◇"},{href:"/gear",label:"裝備圖鑑",symbol:"✧"},{href:"/pvp",label:"PvP 排行與防禦",symbol:"⚔"},{href:"/guild",label:"公會排名與防禦",symbol:"♜"}];

export function SiteHeader(){
  const pathname=usePathname();const [open,setOpen]=useState(false);
  const header=useRef<HTMLElement>(null),toggle=useRef<HTMLButtonElement>(null);
  const active=modules.find(m=>m.href==="/"?pathname==="/":pathname===m.href||pathname.startsWith(m.href+'/'));
  const currentLabel=active?.label??({'/data-status':'資料更新狀態','/translations':'翻譯資料查詢'} as Record<string,string>)[pathname]??'詳細資料';
  useEffect(()=>{
    const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'&&open){setOpen(false);toggle.current?.focus();}};
    const outside=(event:PointerEvent)=>{if(open&&event.target instanceof Node&&!header.current?.contains(event.target))setOpen(false);};
    document.addEventListener('keydown',escape);document.addEventListener('pointerdown',outside);
    return()=>{document.removeEventListener('keydown',escape);document.removeEventListener('pointerdown',outside);};
  },[open]);
  return <><button className="skip-navigation" onClick={()=>{const main=document.querySelector('main');if(main){main.tabIndex=-1;main.focus();main.scrollIntoView({block:'start'});}}}>跳至主要內容</button><header className="site-header" ref={header}>
    <Link className="site-brand" href="/" onClick={()=>setOpen(false)}><span className="site-brand-mark" aria-hidden="true">R</span><span><strong>RANGER ATLAS</strong><small>LINE Rangers 資料站</small></span></Link>
    <button className="nav-toggle" ref={toggle} aria-expanded={open} aria-controls="module-navigation" onClick={()=>setOpen(!open)}>{open?"關閉選單":"開啟選單"}<span aria-hidden="true">{open?'×':'☰'}</span></button>
    <div className={`site-navigation ${open?"is-open":""}`} id="module-navigation"><p className="nav-section-label">資料查詢</p><nav className="module-nav" aria-label="資料模組">{modules.map(m=><Link className={`module-nav-link ${active?.href===m.href?"is-active":""}`} href={m.href} key={m.href} aria-current={active?.href===m.href?"page":undefined} onClick={()=>setOpen(false)}><span className="module-symbol" aria-hidden="true">{m.symbol}</span><span>{m.label}</span><span className="module-arrow" aria-hidden="true">›</span></Link>)}</nav><div className="nav-bottom"><span>LINE RANGERS</span><Link href="/data-status" onClick={()=>setOpen(false)}>資料更新狀態</Link></div></div>
  </header><div className="site-toolbar"><nav className="site-breadcrumbs" aria-label="目前位置"><Link href="/" aria-current={pathname==='/'?'page':undefined}>首頁</Link>{pathname!=='/'&&<><span aria-hidden="true">/</span>{active&&pathname!==active.href?<><Link href={active.href}>{currentLabel}</Link><span aria-hidden="true">/</span><span aria-current="page">詳細資料</span></>:<span aria-current="page">{currentLabel}</span>}</>}</nav><span className="toolbar-label">遊戲資料查詢</span></div></>;
}
