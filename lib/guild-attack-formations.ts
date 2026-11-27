import 'server-only';
import {createHash} from 'node:crypto';
import {getCharacterReference} from './character-reference';
import {viewerReference} from './defense-viewer-data';
import type {ViewerGear, ViewerTeam} from './defense-viewer';
import {displaySourceText} from './display-text';
import {equipmentName} from './equipment-filters';
import {readGuildAttackFormationStore} from './local-game-data';
import {getLocalGearIconUrl} from './local-research-assets';
import {getVerifiedEquipmentList} from './verified-equipment';

type Slot = ViewerGear['slot'];
type ObservedGear = {state: string; equipmentId: string | null; enhancement?: number};
type ObservedUnit = {position: number; characterId: string; level: number; equipment: Record<Slot, ObservedGear>};
type Observation = {
  guildId: string;
  playerId: string;
  playerName: string;
  capturedAt: string;
  sourceKind: string;
  purpose: string;
  status: string;
  defenseVerified: boolean;
  towerCode: number | null;
  teams: {teamNo: number; units: ObservedUnit[]}[];
};
export type GuildAttackFormation = {memberAlias: string; name: string; teams: ViewerTeam[]};

const slots = ['weapon', 'armor', 'accessory'] as const;
const displayKey = (...parts: unknown[]) => createHash('sha256').update(JSON.stringify(parts)).digest('hex');

export async function getGuildAttackFormations(guildId: string): Promise<GuildAttackFormation[]> {
  const observations = (await readGuildAttackFormationStore(guildId) as Observation[]).filter(row =>
    row.guildId === guildId && row.sourceKind === 'verified-public-guildwar-attack-formation' &&
    row.purpose === 'guildwar_attack_formation' && row.status === 'success' &&
    row.defenseVerified === false && row.towerCode === null && row.teams.some(team => team.units.length > 0));
  if (!observations.length) return [];

  const [characters, equipment] = await Promise.all([getCharacterReference(), getVerifiedEquipmentList()]);
  const characterById = new Map(characters?.records.map(character => [character.characterId, character]));
  const equipmentById = new Map(equipment.map(template => [template.itemCode, template]));
  const equipmentIds = new Set(observations.flatMap(row => row.teams.flatMap(team => team.units.flatMap(unit =>
    Object.values(unit.equipment).flatMap(gear => gear.equipmentId ? [gear.equipmentId] : [])))));
  const templates = new Map(await Promise.all([...equipmentIds].map(async id => {
    const template = equipmentById.get(id);
    return [id, template ? {
      name: equipmentName(template), dataCode: template.dataCode, stars: template.starCount,
      imageUrl: await getLocalGearIconUrl(template.dataCode), reference: viewerReference(template.reference),
    } : null] as const;
  })));

  return observations.map(row => {
    const memberAlias = displayKey(row.guildId, row.playerId).slice(0, 20);
    return {
      memberAlias,
      name: displaySourceText(row.playerName),
      teams: row.teams.map(team => ({
        key: displayKey(memberAlias, row.capturedAt, team.teamNo).slice(0, 24),
        label: `公會戰進攻 · 隊伍 ${team.teamNo}`,
        status: 'success',
        retrievedAt: row.capturedAt,
        note: '公開進攻編隊快照。可查看當時的角色、裝備及強化。',
        unobservedPositions: Array.from({length: 20}, (_, position) => position)
          .filter(position => !team.units.some(unit => unit.position === position)),
        units: team.units.map(unit => {
          const character = characterById.get(unit.characterId);
          return {
            key: displayKey(memberAlias, row.capturedAt, team.teamNo, unit.position).slice(0, 24),
            position: unit.position,
            state: 'present',
            characterId: character?.characterId ?? null,
            name: character?.name ?? '角色名稱尚未對照',
            imageUrl: character?.imageUrl ?? null,
            stars: character?.starGrade ?? null,
            element: character?.elementType ?? null,
            role: character?.roleType ?? null,
            observedLevel: unit.level,
            progress: null,
            talents: null,
            gear: slots.map(slot => {
              const gear = unit.equipment[slot];
              const template = gear.equipmentId ? templates.get(gear.equipmentId) : null;
              return {
                slot, state: gear.state,
                name: template?.name || '裝備名稱尚未對照',
                dataCode: template?.dataCode ?? null,
                imageUrl: template?.imageUrl ?? null,
                stars: template?.stars ?? null,
                enhancement: gear.enhancement ?? null,
                effects: null,
                effectStatus: '實際詞條數值尚未核對。',
                special: null,
                reference: template?.reference ?? null,
              };
            }),
          };
        }),
      })),
    };
  });
}
