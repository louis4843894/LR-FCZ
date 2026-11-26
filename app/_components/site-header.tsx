"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const modules=[{href:"/",label:"首頁",symbol:"⌂"},{href:"/characters",label:"Rangers 角色",symbol:"◇"},{href:"/gear",label:"裝備圖鑑",symbol:"◇"},{href:"/pvp",label:"PvP 排行與防禦",symbol:"◇"},{href:"/guild",label:"公會排名與防禦",symbol:"◇"}];

export function SiteHeader(){
  const pathname=usePathname();const [open,setOpen]=useState(false);
  const active=modules.find(m=>m.href==="/"?pathname==="/":pathname.startsWith(m.href));
  return <><header className="site-header">
    <Link className="site-brand" href="/" onClick={()=>setOpen(false)}><span className="site-brand-mark" aria-hidden="true">R</span><span><strong>RANGER ATLAS</strong><small>LINE Rangers 資料站</small></span></Link>
    <button className="nav-toggle" aria-expanded={open} aria-controls="module-navigation" onClick={()=>setOpen(!open)}>{open?"關閉選單":"開啟選單"}<span aria-hidden="true">☰</span></button>
    <div className={`site-navigation ${open?"is-open":""}`} id="module-navigation"><p className="nav-section-label">資料查詢</p><nav className="module-nav" aria-label="資料模組">{modules.map(m=><Link className={`module-nav-link ${active?.href===m.href?"is-active":""}`} href={m.href} key={m.href} aria-current={active?.href===m.href?"page":undefined} onClick={()=>setOpen(false)}><span className="module-symbol" aria-hidden="true">{m.symbol}</span><span>{m.label}</span><span className="module-arrow" aria-hidden="true">›</span></Link>)}</nav><div className="nav-bottom"><span>LINE RANGERS</span><Link href="/data-status" onClick={()=>setOpen(false)}>資料更新狀態</Link></div></div>
  </header><div className="site-toolbar"><Link href="/">首頁</Link>{active?.href!=="/"&&<><span aria-hidden="true">/</span><span>{active?.label??"詳細資料"}</span></>}<span className="toolbar-label">遊戲資料查詢</span></div></>;
}
