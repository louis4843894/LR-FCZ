import type {GuildAttackFormation} from '../../lib/guild-attack-formations';
import {DefenseTeamViewer} from './defense-team-viewer';

export function GuildAttackPanel({formations}: {formations: GuildAttackFormation[]}) {
  return <section className="reference-panel" id="attack" aria-labelledby="guild-attack-heading">
    <h2 id="guild-attack-heading">公會戰進攻隊伍</h2>
    {formations.length === 0 && <p>目前尚未取得此公會的公開進攻編隊。</p>}
    {formations.map((formation, index) => <details key={formation.memberAlias} open={index === 0} className="catalog-fold guild-attack-formation">
      <summary><h3>{formation.name || '名稱未知'}</h3></summary>
      <DefenseTeamViewer title={formation.name || '名稱未知'} kicker="公會戰進攻隊伍"
        teams={formation.teams} combinedLabel="全部進攻隊伍" embedded />
    </details>)}
  </section>;
}
