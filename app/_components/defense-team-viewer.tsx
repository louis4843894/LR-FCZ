'use client';

import {useEffect,useId,useRef,useState} from 'react';
import Image from 'next/image';
import Link from 'next/link';
import {type ViewerTeam,type ViewerUnit,type ViewerGear,viewerTeams,viewerSelectedUnit,viewerTime,viewerSlotName,viewerElementName} from '../../lib/defense-viewer';
import {EquipmentReferencePanel} from './equipment-reference-panel';
import {CollapseControls} from './collapse-controls';
import './defense-team-viewer.css';

function starLabel(count:number|null){
  return count===null?'星等未知':`${count} 星`;
}

function StarBadge({count}:{count:number|null}){
  const label=starLabel(count);
  return <span className="dv-stars" data-stars={count??'unknown'} role="img" aria-label={label} title={label}>
    <span aria-hidden="true">{count===null?'☆':'★'}</span>{count??'?'}
  </span>;
}
function Portrait({unit,large=false}:{unit:ViewerUnit;large?:boolean}){
  return <span className={`dv-portrait${large?' dv-portrait-large':''}`}>
    {unit.imageUrl?<Image src={unit.imageUrl} width={172} height={188} alt="" unoptimized loading={large?'eager':'lazy'}/>:<span className="dv-image-missing">{unit.state==='not_present'?'空位':'◇'}</span>}
    <StarBadge count={unit.stars}/>
    <span className="dv-element" data-element={unit.element?.toUpperCase()??'unknown'} title={`${viewerElementName(unit.element)}屬性`} aria-label={`${viewerElementName(unit.element)}屬性`}>{viewerElementName(unit.element)}</span>
    {unit.progress?.talentGrade!=null&&unit.progress.talentGrade>0&&<span className="dv-talent-badge" title={`才能第 ${unit.progress.talentGrade} 階`}>{unit.progress.talentGrade}<span className="dv-sr"> 階才能</span></span>}
  </span>;
}
function GearPreview({gear:g}:{gear:ViewerGear}){
  const label=`${viewerSlotName[g.slot]}：${g.state==='not_equipped'?'確認未穿戴':g.state==='unknown'?'未取得':g.name}${g.state==='equipped'?`，${starLabel(g.stars)}，強化${g.enhancement===null?'未知':` +${g.enhancement}`}`:''}`;
  return <span className="dv-gear-preview" data-state={g.state} role="img" title={label} aria-label={label}>
    {g.state==='equipped'&&g.imageUrl?<Image src={g.imageUrl} width={56} height={56} alt="" unoptimized/>:<span className="dv-slot-placeholder">{g.state==='not_equipped'?'空':g.state==='unknown'?'?':viewerSlotName[g.slot]}</span>}
    {g.state==='equipped'&&<><StarBadge count={g.stars}/>{g.enhancement!==null&&<small className="dv-enhancement">+{g.enhancement}</small>}</>}
  </span>;
}
function GearDetail({gear:g}:{gear:ViewerGear}){
  const knownLevel=g.enhancement!==null&&Number.isInteger(g.enhancement)&&g.enhancement>=0&&g.enhancement<=5;
  return <details className="dv-equipment" aria-label={viewerSlotName[g.slot]}>
    <summary className="dv-equipment-heading"><GearPreview gear={g}/><span><span className="dv-label">{viewerSlotName[g.slot]}</span>
      {g.state==='not_equipped'?<strong className="dv-equipment-name">確認未穿戴</strong>:g.state==='unknown'?<strong className="dv-equipment-name">裝備尚未取得</strong>:<><strong className="dv-equipment-name">{g.dataCode?<Link href={`/gear/${encodeURIComponent(g.dataCode)}${knownLevel?`?level=${g.enhancement}`:''}`}>{g.name} <span className="dv-link-arrow">↗</span></Link>:g.name}</strong><span className="dv-equipment-meta">{g.stars===null?'星等未知':`${g.stars} 星`} · 實際強化 {g.enhancement===null?'未知':`+${g.enhancement}`}</span></>}
    </span></summary>
    {g.state==='equipped'&&<><p className="dv-section-label">此件裝備實際詞條</p>
      {g.effects?.length?<ul className="dv-effects">{g.effects.map((e,i)=><li key={i}><span>{e.label}</span><strong>{e.value}</strong>{e.note&&<small>{e.note}</small>}</li>)}</ul>:<p className="dv-note">{g.effectStatus}</p>}
      {g.special&&<div className="dv-special"><h5>特化效果 · {g.special.name}</h5><p>{g.special.description}</p><small>{g.special.note}</small></div>}
      {g.reference?<details className="dv-reference"><summary>模板參考範圍 · +{knownLevel?g.enhancement:0}</summary>{!knownLevel&&<p>實際強化未知，以下僅顯示模板 +0 基準。</p>}<EquipmentReferencePanel reference={g.reference} level={knownLevel?g.enhancement!:0} showLevelSelector={false}/></details>:<p className="dv-note">模板參考尚未取得。</p>}
    </>}
  </details>;
}
function UnitDetail({unit:u}:{unit:ViewerUnit}){
  const p=u.progress;
  return <div className="dv-unit-detail" data-unit-key={u.key}>
    <div className="dv-detail-hero"><Portrait unit={u} large/><div><h3>{u.characterId?<Link href={`/characters/${encodeURIComponent(u.characterId)}`}>{u.name} <span className="dv-link-arrow">↗</span></Link>:u.name}</h3>
      <p>等級：{p?.level!=null?`Lv. ${p.level}`:'尚未取得'}</p><p>雷納德點數：{p?.leonardPoints!=null?`${p.leonardPoints} 點`:'尚未取得'}</p>
      <p className="dv-note">{({STR:'力量型',AGI:'敏捷型',INT:'智慧型'} as Record<string,string>)[u.role??'']??'類型未知'} · {viewerElementName(u.element)}屬性{p?.maxLevel!=null?` · 等級上限 ${p.maxLevel}`:''}</p>
    </div></div>
    <details className="dv-awakening"><summary><span className="dv-awakening-icon" aria-hidden="true">✧</span><span><span className="dv-label">覺醒能力</span><strong>{p?.awakening.state==='present'?p.awakening.name??'能力名稱尚未對照':p?.awakening.state==='empty_observed'?'來源回傳空值':'來源未提供'}</strong></span></summary><p>{p?.awakening.state==='present'?p.awakening.description??'能力敘述尚未對照':p?.awakening.state==='empty_observed'?'來源明確回傳空值，不以模板候選填補。':'來源未提供實際覺醒能力。'}</p></details>
    <details className="dv-talents"><summary>解放才能 · {p?.talentGrade!=null?`第 ${p.talentGrade} 階`:'階段未知'}</summary>
      {u.talents?.status==='verified-native-group'?<ol>{u.talents.steps.map(s=><li key={s.stage} data-state={s.state}><strong>第 {s.stage} 階 · {s.state==='reached'?'已達階段':s.state==='locked'?'尚未解鎖':'階段未知'}</strong><p>{s.description??'效果尚未對照'}</p></li>)}</ol>:<p>{u.talents?.status==='not_configured'?'此角色模板未設定才能群組。':'才能效果尚未取得。'}</p>}
      <p className="dv-note">階段依此角色實例判定；實際發動仍須符合條件，戰鬥觸發尚未核對。</p>
    </details>
    <div className="dv-gear-details">{u.gear.map(g=><GearDetail gear={g} key={g.slot}/>)}</div>
    <p className="dv-note">角色與裝備數值已解析，尚未逐項目視核對。模板參考範圍與此件實際數值分開顯示。</p>
  </div>;
}

export function DefenseTeamViewer({title,subtitle,teams,combinedLabel='全部已取得的防禦隊伍'}:{title:string;subtitle?:string;teams:ViewerTeam[];combinedLabel?:string}){
  const [teamKey,setTeamKey]=useState('all');const [selectedKey,setSelectedKey]=useState<string|null>(null);const [expanded,setExpanded]=useState(false);
  const dialog=useRef<HTMLDialogElement>(null);const opener=useRef<HTMLButtonElement>(null);const detail=useRef<HTMLDetailsElement>(null);const id=useId();
  const visible=viewerTeams(teams,teamKey);const selected=viewerSelectedUnit(teams,teamKey,selectedKey);
  useEffect(()=>{if(!expanded||!dialog.current)return;const d=dialog.current;d.showModal();
    const previous=document.body.style.overflow;document.body.style.overflow='hidden';
    return()=>{d.close();document.body.style.overflow=previous;};
  },[expanded]);
  const close=()=>{setExpanded(false);requestAnimationFrame(()=>opener.current?.focus());};
  const select=(u:ViewerUnit)=>{setSelectedKey(u.key);if(detail.current)detail.current.open=true;if(window.matchMedia('(max-width: 760px)').matches)requestAnimationFrame(()=>detail.current?.scrollIntoView({block:'start',behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'}));};
  const content=<>
    <header className="dv-header"><div><p className="dv-kicker">防禦配置</p><h2 id={`${id}-title${expanded?'-modal':''}`}>{title}</h2>{subtitle&&<p className="dv-subtitle">{subtitle}</p>}</div>
      {expanded?<button className="dv-close" type="button" onClick={close} aria-label="關閉隊伍檢視">×</button>:<button className="dv-expand" type="button" ref={opener} onClick={()=>setExpanded(true)} aria-haspopup="dialog">⤢ <span>放大檢視</span></button>}
    </header>
    <div className="dv-controls"><label htmlFor={`${id}-team${expanded?'-modal':''}`}>顯示隊伍</label><select id={`${id}-team${expanded?'-modal':''}`} value={teamKey} onChange={e=>{setTeamKey(e.target.value);setSelectedKey(null);}}>
      {teams.length>1&&<option value="all">{combinedLabel}</option>}{teams.length===1&&<option value="all">{teams[0].label}</option>}{teams.length!==1&&teams.map(t=><option value={t.key} key={t.key}>{t.label}</option>)}
    </select><p>{visible.reduce((n,t)=>n+t.units.filter(u=>u.state!=='not_present').length,0)} 個已取得角色位置 · 點擊角色查看裝備</p></div>
    <CollapseControls/>
    <div className="dv-layout"><details className="dv-roster" aria-label="隊伍角色" open><summary className="dv-panel-summary"><h3>隊伍角色</h3></summary>
      {!visible.length&&<p>尚無可用隊伍資料，不代表沒有防禦。</p>}
      {visible.map(t=><details className="dv-team" key={t.key} open><summary className="dv-team-heading"><strong>{t.label} · {t.units.length} 個位置</strong><span>取得於 {viewerTime(t.retrievedAt)}</span></summary>
        {t.status!=='success'?<p>{t.status==='failed'?'讀取失敗':'資料尚不可取得'}；隊伍內容未知。</p>:!t.units.length?<p>{t.unobservedPositions.length?'未取得角色位置，是否空隊伍尚未確認。':'此次來源確認隊伍為空。'}</p>:<div className="dv-character-grid">{t.units.map(u=>{
          const level=u.progress?.level??null;
          const levelLabel=level===null?'等級尚未取得':`等級 ${level}`;
          const label=`位置 ${u.position+1}：${u.name}，${starLabel(u.stars)}${u.state==='not_present'?'':`，${levelLabel}`}`;
          return <button type="button" className="dv-card" key={u.key} data-unit-key={u.key} aria-pressed={selected?.key===u.key} aria-label={label} onClick={()=>select(u)}>
            <Portrait unit={u}/>
            {u.state!=='not_present'&&<span className="dv-card-level" title={levelLabel}>Lv. {level??'?'}</span>}
            <span className="dv-card-gear">{u.gear.map(g=><GearPreview gear={g} key={g.slot}/>)}</span>
            <strong className="dv-card-name" title={u.name}>{u.name}</strong>
            <span className="dv-position">位置 {u.position+1}</span>
          </button>;
        })}</div>}
        {t.unobservedPositions.length>0&&<p className="dv-note">未讀取位置：{t.unobservedPositions.map(n=>n+1).join('、')}；未讀取不代表空位置。</p>}<p className="dv-note">{t.note}</p>
      </details>)}
    </details><details className="dv-details" aria-label="角色詳細資料" ref={detail} tabIndex={-1} open><summary className="dv-panel-summary"><h3>角色詳細資料</h3></summary>{selected?<UnitDetail unit={selected} key={selected.key}/>:<div className="dv-detail-empty"><span aria-hidden="true">◇</span><p>點擊左側角色查看等級、雷納德點數、覺醒能力、解放才能與裝備。</p></div>}</details></div>
  </>;
  return <div className="dv-shell">{!expanded&&<div className="team-viewer" data-collapse-scope>{content}</div>}<dialog ref={dialog} className="team-viewer dv-dialog" data-collapse-scope aria-labelledby={`${id}-title-modal`} onCancel={e=>{e.preventDefault();close();}} onClick={e=>{if(e.target===e.currentTarget)close();}}>{expanded&&content}</dialog></div>;
}
