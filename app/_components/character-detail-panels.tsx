import type {CharacterDetails} from '../../lib/character-details';
import type {NativeCharacterTalents} from '../../lib/character-native';
import './character-detail-panels.css';
import {CollapseControls} from './collapse-controls';
type Ability=NonNullable<CharacterDetails['abilities']>[number];
const number=(v:number|null)=>v===null?'尚未取得':v.toLocaleString('zh-TW',{maximumFractionDigits:6});
const yes=(v:boolean|null)=>v===null?'尚未確認':v?'適用':'不適用';

function AbilityCard({ability:a}:{ability:Ability}){
 return <details className="character-ability-card catalog-fold"><summary><h3>{a.name??'能力名稱尚未取得'}</h3></summary><p className="character-prose">{a.description??'能力敘述尚未取得'}</p>
  {a.triggerEffects?.map((e,i)=><div className="character-ability-trigger" key={i}><p><strong>{e.effect??'效果尚未對照'}</strong></p>
   <dl className="character-facts"><div><dt>發動時機</dt><dd>{e.phase??'尚未取得'}</dd></div><div><dt>發動機率</dt><dd>{e.chancePercent===null?'尚未取得':`${number(e.chancePercent)}%`}</dd></div>
    <div><dt>場合</dt><dd>{e.battleMode??'尚未取得'}</dd></div><div><dt>條件</dt><dd>{e.condition??'尚未取得'}</dd></div></dl>
   {e.additionalCondition&&<p>附加條件：{e.additionalCondition}</p>}</div>)}
  {a.triggerEffects===null&&<p className="catalog-note">觸發細節尚未取得。</p>}
 </details>;
}

export function CharacterDetailPanels({details:d,nativeTalents,detailStatus}:{details:CharacterDetails|null;nativeTalents?:NativeCharacterTalents|null;detailStatus?:string}){
 const major=d?.talents?.major;
 return <div data-collapse-scope>
  <CollapseControls/>
  <nav className="character-section-nav" aria-label="角色詳細資料"><a href="#character-stats">基準數值</a><a href="#character-skills">技能效果</a><a href="#character-abilities">角色能力</a><a href="#character-awakening">覺醒能力</a><a href="#character-talents">才能</a></nav>
  <p className="character-template-note">以下為圖鑑模板參考，未套用玩家等級、裝備與培養。覺醒能力列出模板候選，不代表玩家已取得或啟用。</p>
  {detailStatus==='not_in_reference'&&<p className="catalog-note">目前詳細資料未收錄此模板；這不代表角色沒有技能、能力或覺醒。才能另依已確認的本機群組判定。</p>}
  <details className="reference-panel character-section" id="character-stats"><summary><h2>模板基準數值</h2></summary>
   {d?.stats?<><p className="catalog-note">保留模板的基準值；其等級基準尚未獨立確認，不作為玩家實際面板數值。</p><dl className="character-stat-grid">{d.stats.map(s=><div key={s.label}><dt>{s.label}</dt><dd>{number(s.value)}{s.value!==null&&s.unit?` ${s.unit}`:''}</dd></div>)}</dl></>:<p>基準數值尚未取得。</p>}
  </details>
  <details className="reference-panel character-section" id="character-skills"><summary><h2>技能與效果</h2></summary>
   {d?.skills?.length?d.skills.map((s,i)=><details className="character-skill-card catalog-fold" key={s.skillCode??i}><summary><span className="eyebrow">技能 {i+1}</span><h3>{s.name??'技能名稱尚未取得'}</h3></summary><p className="character-prose">{s.description??'技能敘述尚未取得'}</p>
    <dl className="character-facts"><div><dt>發動機率</dt><dd>{s.activationRatePercent===null?'尚未取得':`${number(s.activationRatePercent)}%`}</dd></div><div><dt>冷卻時間</dt><dd>{s.cooldownSeconds===null?'尚未取得':`${number(s.cooldownSeconds)} 秒`}</dd></div>
     <div><dt>技能前搖</dt><dd>{s.startupSeconds===null?'尚未取得':`${s.startupSeconds.toFixed(2)} 秒`}</dd></div>
     <div><dt>觸發基準</dt><dd>{s.triggerLabel??'尚未取得'}{s.searchRatio!==null?`（搜尋倍率 ${number(s.searchRatio)} 倍）`:''}</dd></div></dl>
    <p className="catalog-note">前搖取動畫資料標示的技能段長度，不含投射物飛行時間；戰鬥中的速度變化另計。</p>
    {s.status==='unresolved'&&<p>技能描述版本尚未一致，效果數值暫不套用。</p>}
    <div className="character-skill-effects">{s.effects?.map((e,j)=><details className="character-effect catalog-fold" key={j}><summary><h4>{e.name??'效果名稱尚未對照'}</h4></summary>
     <dl className="character-facts"><div><dt>效果係數</dt><dd>{e.magnitudeText??'未列係數'}</dd></div><div><dt>有效時間</dt><dd>{e.durationText??'未列持續時間'}</dd></div><div><dt>範圍</dt><dd>{e.rangePoints===null?'尚未取得':`${number(e.rangePoints)} 點`}</dd></div>
      {e.triggerChancePercent!==null&&<div><dt>此效果發動機率</dt><dd>{number(e.triggerChancePercent)}%</dd></div>}{e.targetLimitText&&<div><dt>對象上限</dt><dd>{e.targetLimitText}</dd></div>}</dl>
     <p className="character-effect-scope">活動關卡：{yes(e.availableEvents)} · 守護神：{yes(e.availableGuardian)}</p>
    </details>)}</div>{s.effects===null&&<p>效果細節尚未取得。</p>}
   </details>):<p>{d?.availability.skills==='absent'?'此角色沒有技能。':'技能詳細資料尚未取得。'}</p>}
  </details>
  <details className="reference-panel character-section" id="character-abilities"><summary><h2>角色能力</h2></summary><div className="character-ability-grid">
   {d?.abilities?.length?d.abilities.map((a,i)=><AbilityCard key={a.abilityCode??i} ability={a}/>):<p>{d?.availability.abilities==='absent'?'此角色沒有角色能力。':'角色能力尚未取得。'}</p>}</div>
  </details>
  <details className="reference-panel character-section" id="character-awakening"><summary><h2>覺醒能力候選</h2></summary><p className="catalog-note">僅列出可能獲得的能力，玩家實際覺醒結果另計。候選出現機率尚未確認；下方發動機率是各能力自身的觸發機率。</p><div className="character-ability-grid">
   {d?.awakeningAbilities?.length?d.awakeningAbilities.map((a,i)=><AbilityCard key={a.abilityCode??i} ability={a}/>):<p>{d?.availability.awakening==='absent'?'此角色沒有覺醒能力候選。':'覺醒能力候選尚未取得。'}</p>}</div>
  </details>
  <details className="reference-panel character-section" id="character-talents"><summary><h2>才能</h2></summary><p className="catalog-note">列出主要才能與強化才能的模板內容；玩家解鎖及培養階段另計。</p>
   {nativeTalents?.status==='not_configured'||d?.availability.talents==='absent'?<p>此角色未設定才能。</p>:<>
   {nativeTalents?.status==='verified-native-group'&&<><h3>四階段對照</h3><ol className="native-talent-stages">{nativeTalents.steps.map(s=><li key={s.stage}><strong>第 {s.stage} 階 · {s.kind==='major'?'主要才能':'強化才能'}</strong><p>{s.description??'效果尚未對照'}</p></li>)}</ol></>}
   {major?<details className="character-ability-card catalog-fold"><summary><h3>主要才能</h3></summary><p className="character-prose">{major.description??'敘述尚未取得'}</p>
    <dl className="character-facts"><div><dt>啟動條件</dt><dd>{major.condition??'尚未取得'}</dd></div><div><dt>啟動機率</dt><dd>{major.activationChancePercent===null?'尚未取得':`${number(major.activationChancePercent)}%`}</dd></div></dl>
    {major.additionalConditions.map((c,i)=><p key={i}>附加條件：{c}</p>)}<ul>{major.effects?.map((e,i)=><li key={i}>{e.description??'效果尚未對照'}{e.activationChancePercent!==null?`（此效果機率 ${number(e.activationChancePercent)}%）`:''}</li>)}</ul></details>:<p>{d?.talents?'本次模板資料未列主要才能。':'才能詳細資料尚未取得。'}</p>}
   {!!d?.talents?.enhancements?.length&&<details className="character-ability-card catalog-fold"><summary><h3>強化才能</h3></summary><ul>{d.talents.enhancements.map((t,i)=><li key={t.talentCode??i}>{t.description??'效果尚未對照'}</li>)}</ul></details>}
   </>}
  </details>
 </div>;
}
