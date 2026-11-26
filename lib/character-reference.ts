import "server-only";
import {readCharacterTemplateDocument,readCharacterDetailStore,readCharacterNativeStore} from "./local-game-data";
import {publicNativeTalents,type NativeCharacterTalents} from './character-native';
import { displaySourceText } from "./display-text";
import {createHash} from "node:crypto";
import {publicCharacterDetails,type CharacterDetails} from "./character-details";

export type CharacterReference = {
  characterId: string; name: string | null; description: string | null;
  starGrade: number | null; evolution: string | null; roleType: string | null; elementType: string | null;
  releaseDate: string | null; abilityCodes: string[];
  primarySkillCode:string|null;primaryAbilityCode:string|null;
  imageUrl:string|null;
  skillCount:number|null;abilityCount:number|null;awakeningCount:number|null;talentsAvailable:boolean;detailsMatched:boolean;
  skills: { skillCode: string; name: string | null; description: string | null;
    activationRatePercent: number | null; cooldownSeconds: number | null;
    effects: { effectCode: string; name: string | null }[] }[] | null;
};
// External reference copies remain research-only; this reader uses local native fields.
export async function getCharacterReference(): Promise<{ retrievedAt: string; detailsRetrievedAt:string|null;nativeSha:string;gameVersion:string|null;loadedContainerTraversalEnded:boolean;coverage:{names:number;stars:number;images:number;primarySkills:number;primaryAbilities:number;skillDetails:number;abilityDetails:number;awakeningDetails:number;talentDetails:number;matchedDetails:number;notInReference:number;skillsAbsent:number|null;abilitiesAbsent:number|null;awakeningAbsent:number|null;talentsAbsent:number|null}; records: CharacterReference[] } | null> {
  if (process.env.NODE_ENV !== "development") return null;
  try {
    const document=await readCharacterTemplateDocument();const nativeSha=document.documentSha??createHash('sha256').update(document.text).digest('hex');const data = JSON.parse(document.text);
    if (data.sourceKind !== "verified-character-template" || data.localVerification !== true || !Array.isArray(data.records)) throw new Error("角色來源格式不正確");
    if (!data.records.length) return null;
    const [details,native]=await Promise.all([readCharacterDetailStore(nativeSha),readCharacterNativeStore(nativeSha)]);
    const records: CharacterReference[] = data.records.map((r: { characterId:string; name:string|null; description:string|null; starCount:number|null; unitCategory?:string|null; unitElement:string|null;primarySkillCode?:string|null;primaryAbilityCode?:string|null }) => ({
      characterId:r.characterId, name:r.name===null ? null : displaySourceText(r.name), description:r.description===null ? null : displaySourceText(r.description), starGrade:r.starCount,
      imageUrl:native?.index.get(r.characterId)?.imageSha?`/api/local-research-assets/characters/${encodeURIComponent(r.characterId)}`:null,
      evolution:null, roleType:r.unitCategory ?? null, elementType:r.unitElement, releaseDate:null, abilityCodes:[], skills:null,primarySkillCode:r.primarySkillCode ?? null,primaryAbilityCode:r.primaryAbilityCode ?? null,
      skillCount:details?.index.get(r.characterId)?.skillCount??null,abilityCount:details?.index.get(r.characterId)?.abilityCount??null,
      awakeningCount:details?.index.get(r.characterId)?.awakeningCount??null,talentsAvailable:details?.index.get(r.characterId)?.talentsAvailable===true,detailsMatched:details?.index.get(r.characterId)?.status==='matched-reference',
    }));
    return { retrievedAt: new Date(data.capturedAt * 1000).toISOString(), detailsRetrievedAt:details?.retrievedAt??null,nativeSha,gameVersion:typeof data.gameVersion==="string" ? data.gameVersion : null,loadedContainerTraversalEnded:data.loadedContainerTraversalEnded===true,
      coverage:{names:records.filter(r=>r.name!==null).length,stars:records.filter(r=>r.starGrade!==null).length,images:records.filter(r=>r.imageUrl!==null).length,primarySkills:records.filter(r=>r.primarySkillCode!==null).length,primaryAbilities:records.filter(r=>r.primaryAbilityCode!==null).length,skillDetails:details?.summary.skillsCharacters??0,
        abilityDetails:details?.summary.abilitiesCharacters??0,awakeningDetails:details?.summary.awakeningAbilitiesCharacters??0,talentDetails:details?.summary.talentsCharacters??0,matchedDetails:records.filter(r=>r.detailsMatched).length,notInReference:[...(details?.index.values()??[])].filter(r=>r.status==='not_in_reference').length,skillsAbsent:details?.summary.skills_absent??null,abilitiesAbsent:details?.summary.abilities_absent??null,awakeningAbsent:details?.summary.awakening_absent??null,talentsAbsent:native?.summary.talentsAbsent??null},records };
  } catch (error: unknown) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") return null;
    throw error;
  }
}
export async function getCharacterDetail(characterId:string):Promise<{row:CharacterReference;details:CharacterDetails|null;detailStatus:string;nativeTalents:NativeCharacterTalents|null;retrievedAt:string;detailsRetrievedAt:string|null}|null>{
 if(!/^[A-Za-z0-9_-]+$/.test(characterId))return null;
 const source=await getCharacterReference();const row=source?.records.find(r=>r.characterId===characterId);if(!source||!row)return null;
 const [store,native]=await Promise.all([readCharacterDetailStore(source.nativeSha,characterId),readCharacterNativeStore(source.nativeSha,[characterId])]);
 return {row,details:publicCharacterDetails(store?.detail,characterId),detailStatus:store?.index.get(characterId)?.status??'not_acquired',nativeTalents:publicNativeTalents(native?.details.get(characterId),characterId),retrievedAt:source.retrievedAt,detailsRetrievedAt:store?.retrievedAt??null};
}
export const roleName = (value: string | null) => ({STR:"力量型",AGI:"敏捷型",INT:"智慧型"} as Record<string,string>)[value?.toUpperCase() ?? ""] ?? value ?? "尚未確認";
export const elementName = (value: string | null) => ({NONE:"無屬性",FIRE:"火",WATER:"水",TREE:"木",LIGHT:"光",DARK:"暗"} as Record<string,string>)[value?.toUpperCase() ?? ""] ?? value ?? "尚未確認";
