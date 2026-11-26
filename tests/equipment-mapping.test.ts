import {expect,it,vi} from "vitest";
vi.mock("server-only",()=>({}));
import {mappingDisplay} from "../lib/equipment-mapping";

it("keeps template candidates separate from verified actual values and strips raw proof fields",()=>{
 const result=mappingDisplay({status:"template_candidates_only",sourceKind:"external-reference",actualValueVerified:false,sourceSha256:"private-proof",nativeAttributeSha256:"private-native-proof",rawMemory:"private-memory",candidates:[{name:"測試效果",range:{min:5,max:8,unit:"PERCENT"},upgradeStep:2}]});
 expect(result?.actualValueVerified).toBe(false);expect(result?.status).toBe("template_candidates_only");expect(result?.candidates[0].range?.min).toBe(5);
 expect(JSON.stringify(result)).not.toContain("private-");
});
it("rejects mappings that attempt to mark external candidates as actual verified values",()=>{
 expect(mappingDisplay({status:"exact_attribute_id",sourceKind:"external-reference",actualValueVerified:true,candidates:[]})).toBeNull();
 expect(mappingDisplay({status:"guessed",sourceKind:"external-reference",actualValueVerified:false,candidates:[]})).toBeNull();
});
