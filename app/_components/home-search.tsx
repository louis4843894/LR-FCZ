"use client";

import { useState } from "react";

const targets = [
  { path: "/characters", label: "角色", placeholder: "角色名稱或角色 ID" },
  { path: "/gear", label: "裝備", placeholder: "裝備名稱或 itemCode" },
  { path: "/guild", label: "公會", placeholder: "公會名稱或排名" },
];

export function HomeSearch() {
  const [path, setPath] = useState("/characters");
  return <form action={path} className="home-search" role="search" aria-label="資料快速查詢">
    <label className="home-search-target"><span>查詢項目</span><select value={path} onChange={event => setPath(event.target.value)}>{targets.map(target => <option key={target.path} value={target.path}>{target.label}</option>)}</select></label>
    <label className="home-search-query"><span>搜尋關鍵字</span><input type="search" name="q" placeholder={targets.find(target => target.path === path)?.placeholder} required /></label>
    <button className="button button-primary" type="submit">搜尋</button>
  </form>;
}
