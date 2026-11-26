import Link from 'next/link';
import type {CharacterInstanceProgress} from '../../lib/character-instance-progress';
import type {characterTalentStages} from '../../lib/character-native';
import './character-instance-panel.css';

export function CharacterInstancePanel({progress:p,characterId,talents}:{progress:CharacterInstanceProgress|null;characterId:string|null;talents?:ReturnType<typeof characterTalentStages>}){
 return <div className="instance-character-panel">
  <dl className="instance-character-facts">
   <div><dt>實際等級</dt><dd>{p?.level!=null?`Lv.${p.level}${p.maxLevel!==null?` / ${p.maxLevel}`:''}`:'尚未取得'}</dd></div>
   <div><dt>雷納德點數</dt><dd>{p?.leonardPoints!=null?`${p.leonardPoints} 點`:'尚未取得'}</dd></div>
   <div><dt>才能階段</dt><dd>{p?.talentGrade!=null?`第 ${p.talentGrade} 階`:'尚未取得'}</dd></div>
   <div><dt>實際覺醒能力</dt><dd>{p?.awakening.state==='present'?(p.awakening.name??'已取得能力，名稱尚未對照'):p?.awakening.state==='empty_observed'?'來源回傳空值':'來源未提供'}</dd></div>
  </dl>
  {p?.awakening.state==='present'&&<details className="instance-awakening"><summary>覺醒能力說明</summary><p>{p.awakening.description??'能力敘述尚未對照'}</p></details>}
  {talents?.status==='verified-native-group'&&<details className="instance-talents"><summary>才能階段與效果</summary><ol className="native-talent-stages">{talents.steps.map(s=><li key={s.stage} data-state={s.state}><strong>第 {s.stage} 階 · {s.state==='reached'?'已達階段':s.state==='locked'?'尚未解鎖':'階段未知'}</strong><p>{s.description??'效果尚未對照'}</p></li>)}</ol><p>階段依此角色實例判定；能力發動仍須符合條件，戰鬥觸發尚未逐項核對。此處不再次套用倍率到面板數值。</p></details>}
  <p className="instance-character-note">{p?'角色實例欄位已解析，尚未逐項目視核對。':'此份觀察未取得角色培養資料；未知值不代表 0。'}{characterId&&<> <Link href={`/characters/${encodeURIComponent(characterId)}#character-talents`}>查看圖鑑才能與能力說明</Link></>}</p>
 </div>;
}
