// 01340bec reads zero-based indexes at 00858314; 01362abc renders index+1.
// runtime myFortressCode=16 also matches the game's displayed "6 / MY" tower.
// Keep native codes for acquisition; expose the game's 1–10 numbers in the UI.
type TowerElement = 'WATER' | 'FIRE' | 'TREE' | 'LIGHT' | 'DARK';

// The 12.4.2 fortress template has up to two buff elements. Both maps in
// season 454, battle 2 show the same elements for each fortress code.
const towers: Readonly<Partial<Record<number, { number: number; elements: readonly TowerElement[] }>>> = {
  11: { number: 1, elements: ['FIRE'] },
  12: { number: 2, elements: ['WATER'] },
  13: { number: 3, elements: ['TREE'] },
  14: { number: 4, elements: ['FIRE'] },
  15: { number: 5, elements: ['WATER'] },
  16: { number: 6, elements: ['TREE'] },
  21: { number: 7, elements: ['FIRE'] },
  22: { number: 8, elements: ['WATER'] },
  23: { number: 9, elements: ['TREE'] },
  31: { number: 10, elements: ['LIGHT', 'DARK'] },
};

export function guildWarTowerNumber(code:number):number|null{return towers[code]?.number??null;}
export function guildWarTowerLabel(code:number):string{const n=guildWarTowerNumber(code);return n===null?'塔號尚未確認':`第 ${n} 塔`;}
export function guildWarTowerElements(code: number): readonly TowerElement[] {
  return towers[code]?.elements ?? [];
}
