import type { ReferenceEquipment, ReferenceOption } from "../../lib/equipment-reference";
import { referenceRange } from "../../lib/reference-values";
import { displaySourceText } from "../../lib/display-text";
import {CollapseControls} from './collapse-controls';
import {equipmentAvailability} from '../../lib/template-availability';
function Options({ options, level, mode }: { options: ReferenceOption[]; level: number; mode: "multiply" | "increment" }) {
  return <div className="reference-table-wrap"><table className="reference-table"><thead><tr><th>效果</th><th>模板數值範圍</th></tr></thead><tbody>{options.map((e,i)=><tr key={`${e.optionKey}-${i}`}><th scope="row">{displaySourceText(e.name)}</th><td>{referenceRange(e.range,level,mode,e.upgradeStep)}</td></tr>)}</tbody></table></div>;
}
export function EquipmentReferencePanel({ reference, level, showLevelSelector=true }: { reference: ReferenceEquipment; level: number; showLevelSelector?:boolean }) {
  const advanced = reference.advanced;
  const availability=equipmentAvailability(reference);
  return <section className="reference-panel" aria-label="裝備效果與範圍" data-collapse-scope>
    <header><h2>裝備效果</h2><p>以下為裝備模板的可能範圍；玩家實際詞條請查看防禦配置。</p></header>
    {showLevelSelector&&<form className="reference-level" key={level}><label>顯示強化等級<select name="level" defaultValue={level}>{[0,1,2,3,4,5].map(n=><option key={n} value={n}>{n===5?"+Max（+5）":`+${n}`}</option>)}</select></label><button className="button button-primary">切換等級</button></form>}
    <CollapseControls/>
    <details className="catalog-fold"><summary><h3>基本效果 · +{level}</h3></summary>{reference.normalOptions.length ? <Options options={reference.normalOptions} level={level} mode="multiply" /> : <p>{availability.normal==='absent'?'此裝備沒有基本效果。':'基本效果尚未解析。'}</p>}
    </details>
    <details className="catalog-fold"><summary><h3>高級效果 · +{level}</h3></summary>{advanced ? <><p>觸發條件：{displaySourceText(advanced.condition.label)}</p><h4>預設效果</h4><Options options={[{...advanced.defaultOption,upgradeStep:advanced.switchOptions.find(e=>e.optionKey===advanced.defaultOption.optionKey)?.upgradeStep ?? null}]} level={level} mode="increment"/><h4>可切換效果</h4><Options options={advanced.switchOptions} level={level} mode="increment" /></> : <p>{availability.advanced==='absent'?'此裝備沒有高級效果。':'高級效果尚未解析。'}</p>}
    </details>
    <details className="catalog-fold"><summary><h3>Skill+</h3></summary>{reference.skillPlus.length ? <ul>{reference.skillPlus.map((e,i)=><li key={i}>{displaySourceText(e.name)}（{e.dimension === "DURATION" ? "持續時間" : "係數"}）：{referenceRange(e.range,level,"increment",e.upgradeStep)}</li>)}</ul> : <p>{availability.skillPlus==='absent'?'此裝備沒有 Skill+。':'Skill+ 尚未解析，適用性未知。'}</p>}
    </details>
    <details className="catalog-fold"><summary><h3>Spec+ · +{level}</h3></summary>{reference.specPlus ? <><h4>{displaySourceText(reference.specPlus.name)}</h4><Options options={reference.specPlus.basicOptions} level={level} mode="increment" />{reference.specPlus.specialOptions.map((e,i)=><section key={i}>
      <p>效果說明（+0）：{e.description ? displaySourceText(e.description) : "敘述尚未解析"}</p>
      <p>條件：{e.conditions.map(c=>displaySourceText(c.label)).join("；") || "尚未解析"}</p>
      <p>啟動機率（+0）：{referenceRange(e.triggerChance)}</p>
      <p>效果：{e.effectName ? displaySourceText(e.effectName) : "尚無對照名稱"}</p>
      <dl className="equipment-field-status">
        <div><dt>效果觸發機率 · +{level}</dt><dd>{referenceRange(e.chance,level,"increment",e.chanceUpgrade)}</dd></div>
        <div><dt>係數 · +{level}</dt><dd>{referenceRange(e.magnitudeRange,level,"increment",e.magnitudeUpgrade)}</dd></div>
        <div><dt>持續時間 · +{level}</dt><dd>{referenceRange(e.durationRange,level,"increment",e.durationUpgradeSeconds)}</dd></div>
      </dl>
    </section>)}</> : <p>{availability.specPlus==='absent'?'此裝備沒有 Spec+。':'Spec+ 尚未解析，適用性未知。'}</p>}
  </details></section>;
}
