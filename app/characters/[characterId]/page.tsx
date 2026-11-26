import Link from 'next/link';
import {notFound} from 'next/navigation';
import {getCharacterDetail,roleName,elementName} from '../../../lib/character-reference';
import {SiteHeader} from '../../_components/site-header';
import {SiteFooter} from '../../_components/site-footer';
import {CharacterDetailPanels} from '../../_components/character-detail-panels';
import {CharacterPortrait} from '../../_components/character-portrait';
const time=(s:string)=>new Date(s).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false});

export default async function CharacterDetail({params}:{params:Promise<{characterId:string}>}){
 const {characterId}=await params;const source=await getCharacterDetail(characterId);if(!source)notFound();const {row,details}=source;
 return <div className="page-shell"><SiteHeader/><main className="page-main character-detail-page">
  <Link className="back-link" href="/characters">← 回到角色列表</Link>
  <section className="page-intro"><p className="eyebrow">RANGERS</p><h1>{row.name??'角色名稱尚未取得'}</h1><p className="page-lede character-prose">{row.description??'角色說明尚未取得'}</p></section>
  <section className="catalog-summary" aria-label="角色基本資料"><div><span>星等</span><strong>{row.starGrade===null?'尚未確認':`${row.starGrade} 星`}</strong></div><div><span>類型</span><strong>{roleName(row.roleType)}</strong></div><div><span>屬性</span><strong>{elementName(row.elementType)}</strong></div><div><span>登場日期</span><strong>{details?.releaseDate??'尚未取得'}</strong></div></section>
  <CharacterPortrait src={row.imageUrl} name={row.name??row.characterId} large/>
  <CharacterDetailPanels details={details} nativeTalents={source.nativeTalents} detailStatus={source.detailStatus}/>
  <details className="reference-panel character-identifiers"><summary>進階識別資料</summary><p>角色 ID：{row.characterId}</p><p>本機主技能 ID：{row.primarySkillCode??'尚未取得'}</p><p>本機主要能力 ID：{row.primaryAbilityCode??'尚未取得'}</p><p>技能 ID：{details?.skills?.map(s=>s.skillCode).filter(Boolean).join('、')||'尚未取得'}</p><p>能力 ID：{details?.abilities?.map(a=>a.abilityCode).filter(Boolean).join('、')||'尚未取得'}</p></details>
  <p className="catalog-note">基本資料取得：{time(source.retrievedAt)}。{source.detailsRetrievedAt?`詳細資料核對：${time(source.detailsRetrievedAt)}。`:''}</p>
 </main><SiteFooter/></div>;
}
