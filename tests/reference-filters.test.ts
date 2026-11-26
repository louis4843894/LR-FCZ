import { describe, expect, it } from "vitest";
import { referenceFilterOptions } from "../lib/reference-filters";
import type { ReferenceEquipment } from "../lib/equipment-reference";

const row: ReferenceEquipment = { itemCode:"test-only", normalOptions:[], advanced:null, skillPlus:[{effectCode:"skill-id",name:"技能",dimension:"MAGNITUDE",range:null,upgradeStep:null}],specPlus:{name:"特殊",basicOptions:[],specialOptions:[{description:null,conditions:[{key:'{"args":[1],"templateKey":"count"}',label:"使用1次"}],triggerChance:null,effectCode:"effect-id",effectName:"特殊效果",chance:null,chanceUpgrade:null,magnitudeRange:null,magnitudeUpgrade:null,durationRange:null,durationUpgradeSeconds:null}]}};
describe("source-supported skill and spec filters",()=>{
  it("preserves source codes and structured condition keys",()=>{
    const result=referenceFilterOptions(row);
    expect(result.map(e=>e.effectId)).toEqual(["skill-id","effect-id"]);
    expect(result[1].conditionId).toBe('{"args":[1],"templateKey":"count"}');
    expect(result[1].conditionName).toBe("使用1次");
  });
  it("does not fabricate missing effect identifiers",()=>{
    const missing={...row,specPlus:{...row.specPlus!,specialOptions:row.specPlus!.specialOptions.map(e=>({...e,effectCode:null}))}};
    expect(referenceFilterOptions(missing).map(e=>e.effectId)).toEqual(["skill-id"]);
  });
});
