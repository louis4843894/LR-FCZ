// The game displays 1–99 within each player grade. The defender list confirms
// the roster values 489 → L Lv. 93, 494 → L Lv. 98 and 500 → S Lv. 5.
const grades = ['', 'M', 'SM', 'UM', 'L', 'S'] as const;

export function guildDefenderLevel(rosterLevel: number | undefined) {
  if (rosterLevel === undefined || !Number.isInteger(rosterLevel) || rosterLevel < 1 || rosterLevel > grades.length * 99) return null;
  const zeroBased = rosterLevel - 1;
  return { grade: grades[Math.floor(zeroBased / 99)], level: zeroBased % 99 + 1 };
}
