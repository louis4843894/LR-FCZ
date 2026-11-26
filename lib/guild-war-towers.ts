// 01340bec reads zero-based indexes at 00858314; 01362abc renders index+1.
// runtime myFortressCode=16 also matches the game's displayed "6 / MY" tower.
// Keep native codes for acquisition; expose the game's 1–10 numbers in the UI.
const displayNumbers:Readonly<Record<number,number>>={11:1,12:2,13:3,14:4,15:5,16:6,21:7,22:8,23:9,31:10};
export function guildWarTowerNumber(code:number):number|null{return displayNumbers[code]??null;}
export function guildWarTowerLabel(code:number):string{const n=guildWarTowerNumber(code);return n===null?'塔號尚未確認':`第 ${n} 塔`;}
