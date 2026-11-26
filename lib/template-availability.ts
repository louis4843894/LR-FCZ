/** Only an explicit empty list/null configuration proves absence; missing data stays unknown. */
export type TemplateAvailability='present'|'absent'|'unknown';
export function explicitAvailability(value:unknown,key:string,kind:'list'|'object'='list'):TemplateAvailability{
 if(!value||typeof value!=='object'||!Object.prototype.hasOwnProperty.call(value,key))return 'unknown';
 const field=(value as Record<string,unknown>)[key];
 if(kind==='list')return Array.isArray(field)?field.length?'present':'absent':'unknown';
 return field===null?'absent':typeof field==='object'&&!Array.isArray(field)&&Object.keys(field??{}).length>0?'present':'unknown';
}
export const equipmentAvailability=(r:unknown)=>({normal:explicitAvailability(r,'normalOptions'),advanced:explicitAvailability(r,'advanced','object'),skillPlus:explicitAvailability(r,'skillPlus'),specPlus:explicitAvailability(r,'specPlus','object')});
export function characterAvailability(r:Record<string,unknown>){
 const declared=r.availability&&typeof r.availability==='object'?r.availability as Record<string,unknown>:{};
 const field=(key:string,property:string,kind:'list'|'object'='list'):TemplateAvailability=>{
  const value=declared[key];
  if(value==='unknown')return 'unknown';
  const observed=explicitAvailability(r,property,kind);
  if(value==='present'||value==='absent')return value===observed?value:'unknown';
  // Older normalized talent=null also covered absent reference keys: no absence assertion.
  return kind==='object'&&observed==='absent'?'unknown':observed;
 };
 return {skills:field('skills','skills'),abilities:field('abilities','abilities'),awakening:field('awakening','awakeningAbilities'),talents:field('talents','talents','object')};
}
