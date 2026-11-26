import Image from "next/image";
import Link from "next/link";
import type {getDefenseTeams} from "../../lib/defense-teams";
import {equipmentName} from "../../lib/equipment-filters";
import {referenceRange} from "../../lib/reference-values";
import type {DisplayEquipmentMapping} from "../../lib/equipment-mapping";
import {EquipmentReferencePanel} from "./equipment-reference-panel";
type Team=NonNullable<Awaited<ReturnType<typeof getDefenseTeams>>>[number];
type Gear=NonNullable<Team['members']>[number]['slots'][number];

function MappingReference({mapping}:{mapping:DisplayEquipmentMapping|null}){
 if(!mapping)return null;
 return <div className="external-attribute-mapping"><p>模板對照：{mapping.status==='template_candidates_only'?'只有同裝備模板候選，實例關聯未確認':'效果種類對照，實際數值尚未確認'}。</p>
  {mapping.conditionLabel&&<p>模板條件：{mapping.conditionLabel}；實際是否生效尚未確認。</p>}
  <ul>{mapping.candidates.map((c,i)=><li key={i}>{c.name}{c.range&&<> · 模板 +0 範圍 {referenceRange(c.range)}{c.upgradeStep!==null&&<>；每級參考增量 {referenceRange({min:c.upgradeStep,max:c.upgradeStep,unit:c.range.unit})}</>}</>}</li>)}</ul>
 </div>;
}

export function DefenseEquipment({equipment:s}:{equipment:Gear}){
 if(s.state==='unknown')return <p>尚未取得</p>;
 if(s.state==='not_equipped')return <p>已確認未穿戴</p>;
 const level=s.enhancement!==null&&s.enhancement>=0&&s.enhancement<=5?s.enhancement:0;
 return <div className="defense-equipment">
  <div className="defense-gear-heading">{s.template?.iconUrl&&<Image src={s.template.iconUrl} width={48} height={48} alt="" title="圖示對應待確認" unoptimized/>}
   <div>{s.template?<Link className="defense-gear-name" href={`/gear/${s.template.dataCode}?level=${level}`}>{equipmentName(s.template)}</Link>:<strong>裝備名稱尚未取得</strong>}
   <p>{s.template?`${s.template.starCount} 星 · `:''}此件裝備實際強化 {s.enhancement===null?'尚未取得':`+${s.enhancement}`}</p></div>
  </div>
  <div className="instance-attributes"><h4>此件裝備實際詞條</h4>
   {s.actualEffects?<><ul>{s.actualEffects.entries.map(e=><li className="actual-attribute" key={e.index}>
    <span className="actual-attribute-label">{e.displayLabel}</span>：{e.value===null?<span>數值尚未解析</span>:<><strong className="native-attribute-value">{e.value>=0?'+':''}{e.unit==='PERCENT'?`${e.value.toFixed(1)}%`:e.value.toLocaleString('zh-TW')}</strong><small>（強化已計入；{e.valueVisuallyVerified?'已目視核對':e.valueSource==='native-definition-reconstruction'?'依原生定義與實例分級還原，未逐項目視':'已程式還原，未逐項目視'}）</small></>}
   </li>)}</ul><p>未解析項目保持未知；模板範圍不代表這件裝備抽到的數值。</p></>:<p>{s.attributeReadState==='read_failed'?'詞條讀取失敗，內容未知。':s.attributeReadState==='empty_observed_semantics_unknown'?'觀察到空詞條容器，效果語意尚未確認。':'實際詞條尚未解析。'}</p>}
  </div>
  {s.template?.reference?<details className="war-template-reference"><summary>查看中文裝備效果與範圍（模板參考 · +{level}）</summary><EquipmentReferencePanel reference={s.template.reference} level={level} showLevelSelector={false}/></details>:<p>模板效果尚未取得。</p>}
  <details className="defense-raw-identifiers"><summary>原始識別與對照資料（進階）</summary><p>裝備 ID：{s.equipmentId}</p>
   {s.actualEffects?.entries.map(e=><section key={e.index}><p>效果 ID {e.attributeId}／原始階級 {e.valueGradeRaw}{e.attributeCode?`／${e.attributeCode}`:''}；中文種類：{e.labelStatus==='unknown'?'尚未解析':'已由原生資料辨識'}</p><MappingReference mapping={e.externalMapping}/></section>)}
  </details>
 </div>;
}
