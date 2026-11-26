import 'server-only';
import {createHash} from 'node:crypto';
import type {getDefenseTeams} from './defense-teams';
import type {guildWarPanelView} from './guild-war';
import {equipmentName} from './equipment-filters';
import {actualEffectText,type ViewerTeam,type ViewerGear} from './defense-viewer';
import type {ReferenceEquipment,ReferenceOption,ReferenceRange} from './equipment-reference';

type PvpTeam=NonNullable<Awaited<ReturnType<typeof getDefenseTeams>>>[number];
type WarTeams=NonNullable<ReturnType<typeof guildWarPanelView>>['savedConfigurations'][number]['teams'];
const key=(...parts:unknown[])=>createHash('sha256').update(JSON.stringify(parts)).digest('hex').slice(0,24);
const range=(r:ReferenceRange|null)=>r?{min:r.min,max:r.max,unit:r.unit}:null;
const option=(o:ReferenceOption):ReferenceOption=>({optionKey:o.optionKey,name:o.name,category:o.category,range:range(o.range),upgradeStep:o.upgradeStep,attributeId:o.attributeId});
/** Reference files may carry extra research metadata; never serialize it into this client view. */
export function viewerReference(r:ReferenceEquipment|null|undefined):ReferenceEquipment|null{
  return r?{itemCode:r.itemCode,normalOptions:r.normalOptions.map(option),
    advanced:r.advanced?{condition:{key:r.advanced.condition.key,label:r.advanced.condition.label},defaultOption:option(r.advanced.defaultOption),switchOptions:r.advanced.switchOptions.map(option)}:null,
    skillPlus:r.skillPlus.map(s=>({effectCode:s.effectCode,name:s.name,dimension:s.dimension,range:range(s.range),upgradeStep:s.upgradeStep})),
    specPlus:r.specPlus?{name:r.specPlus.name,basicOptions:r.specPlus.basicOptions.map(option),specialOptions:r.specPlus.specialOptions.map(s=>({description:s.description,conditions:s.conditions.map(c=>({key:c.key,label:c.label})),triggerChance:range(s.triggerChance),effectCode:s.effectCode,effectName:s.effectName,chance:range(s.chance),chanceUpgrade:s.chanceUpgrade,magnitudeRange:range(s.magnitudeRange),magnitudeUpgrade:s.magnitudeUpgrade,durationRange:range(s.durationRange),durationUpgradeSeconds:s.durationUpgradeSeconds}))}:null}:null;
}

export function pvpViewerTeams(teams:PvpTeam[]):ViewerTeam[]{
  return teams.map(t=>({key:key(t.playerId,t.snapshotId,t.teamId),
    label:(t.purpose==='guild_battle_defense'?'公會戰防禦隊伍':t.teamId==='pvpteam/1'?'PVP 防禦 A 隊':t.teamId==='pvpteam/2'?'PVP 防禦 B 隊':'PVP 防禦隊伍')+(t.isSelected===true?' · 採集時選用':t.isSelected===false?' · 備用':''),
    status:t.status,retrievedAt:t.retrievedAt,
    note:t.verification?.purposeConfirmed?'已核對防禦用途；角色與裝備數值尚未逐項目視核對。':'已解析防禦資料，尚未目視核對此隊。',
    unobservedPositions:t.unobservedPositionIndices??[],
    units:t.status==='success'?(t.members??[]).map(m=>({key:key(t.playerId,t.snapshotId,t.teamId,m.memberIndex),position:m.memberIndex,state:m.characterState,
      characterId:m.characterId,name:m.characterName??(m.characterState==='not_present'?'確認空位置':'角色尚未取得'),
      imageUrl:m.imageUrl,stars:m.starCount,element:m.elementType,role:m.roleType,
      progress:m.characterProgress,talents:m.talentProgress,
      gear:m.slots.map((s):ViewerGear=>({slot:s.slot,state:s.state,name:s.template?equipmentName(s.template):'裝備名稱尚未取得',
        dataCode:s.template?.dataCode??null,imageUrl:s.template?.iconUrl??null,stars:s.template?.starCount??null,enhancement:s.enhancement,
        effects:s.actualEffects?.entries.map(a=>({label:a.displayLabel,value:actualEffectText(a.value,a.unit),
          note:a.value===null?null:a.valueVisuallyVerified?'已目視核對':a.enhancementIncluded?'已含實際強化；尚未逐項目視核對。':'強化是否計入尚未確認。'}))??null,
        effectStatus:s.attributeReadState==='read_failed'?'詞條讀取失敗，內容未知。':s.attributeReadState==='empty_observed_semantics_unknown'?'觀察到空詞條容器，效果語意尚未確認。':'實際詞條尚未解析。',
        special:null,reference:viewerReference(s.template?.reference)}))
    })):[]
  }));
}

export function warViewerTeams(teams:WarTeams,scope:string,retrievedAt:string):ViewerTeam[]{
  return teams.map(t=>({key:key(scope,retrievedAt,t.teamNo),label:`公會戰防禦 · 隊伍 ${t.teamNo}`,status:'success',retrievedAt,
    note:'角色、裝備與部位已解析，尚未逐件目視核對。',unobservedPositions:[],
    units:t.units.map(u=>({key:key(scope,retrievedAt,t.teamNo,u.position),position:u.position,state:'present',characterId:u.characterId,name:u.characterName,
      imageUrl:u.imageUrl,stars:u.starCount,element:u.elementType,role:u.roleType,progress:u.characterProgress,talents:u.talentProgress,
      gear:u.slots.map((s):ViewerGear=>({slot:s.slot,state:s.state,name:s.template?.name??'裝備名稱尚未取得',dataCode:s.template?.dataCode??null,
        imageUrl:s.template?.iconUrl??null,stars:s.template?.starCount??null,enhancement:s.enhancement,
        effects:s.actualEffects?.map(a=>({label:a.label,value:actualEffectText(a.value,a.unit,a.modifierOperator),
          note:a.value===null?null:a.calculationKind==='native-conditional'?'已含進階強化；適用條件尚待核對。':a.calculationKind==='native-skillplus'?'技能追加參數變化，已含強化；最終技能與觸發狀態尚待核對。':'已含實際強化；尚未逐項目視核對。'}))??null,
        effectStatus:'實際詞條尚未解析，無法判定為沒有效果。',
        special:s.extraSpecial?{name:s.extraSpecial.name,description:[s.extraSpecial.normalText,s.extraSpecial.description].join('\n'),note:`已含特化強化 +${s.extraSpecial.specialEnhancement}；實際觸發尚待核對。`}:s.extraSpecialObserved?{name:'特殊效果',description:'已取得識別，數值尚未解析。',note:'實際觸發尚待核對。'}:null,
        reference:viewerReference(s.template?.reference)}))
    }))
  }));
}
