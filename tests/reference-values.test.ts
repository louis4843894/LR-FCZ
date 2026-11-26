import { describe, expect, it } from "vitest";
import { referenceRange } from "../lib/reference-values";
describe("user-confirmed external display rules", () => {
  it("keeps the target's external base range and uses its explicit basic rule", () => {
    const range = {min:5,max:8,unit:"PERCENT"};
    expect(referenceRange(range,0,"multiply")).toBe("+5.0 ～ +8.0%");
    expect(referenceRange(range,5,"multiply")).toBe("+30.0 ～ +48.0%");
  });
  it("uses only an explicitly supplied upgrade step", () => {
    expect(referenceRange({min:11,max:20,unit:"PERCENT"},2,"increment",4)).toBe("+19.0 ～ +28.0%");
    expect(referenceRange({min:11,max:20,unit:"PERCENT"},2,"increment",null)).toBe("該等級尚無對照規則");
  });
  it("preserves confirmed zero, unknown ranges and negative signs", () => {
    expect(referenceRange({min:0,max:0,unit:"PERCENT"})).toBe("0.0%");
    expect(referenceRange(null)).toBe("尚無對照數值");
    expect(referenceRange({min:-5,max:-5,unit:"PERCENT"},5,"multiply")).toBe("-30.0%");
  });
  it("renders source fixed values without a fabricated percentage unit", () => {
    expect(referenceRange({min:6,max:15,unit:"FLAT"},5,"increment",3)).toBe("+21 ～ +30");
    expect(referenceRange({min:3,max:3,unit:"SECOND"},5,"increment",0)).toBe("+3 秒");
  });
  it("rejects unrepresented enhancement levels", () => {
    expect(()=>referenceRange({min:1,max:1,unit:"NUMBER"},6,"multiply")).toThrow();
  });
});
