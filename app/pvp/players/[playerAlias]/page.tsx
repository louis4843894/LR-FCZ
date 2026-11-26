import {notFound} from 'next/navigation';
import {getRankedDefense,isRankingSnapshotId} from '../../../../lib/pvp-rankings';
import {DefenseTeamsPanel} from '../../../_components/defense-teams-panel';
import {readSiteDisplay} from '../../../../lib/site-display-data';
import type {DisplayDefense} from '../../../../lib/site-display-contract';

export default async function RankedPlayer({params,searchParams}:{params:Promise<{playerAlias:string}>;searchParams:Promise<{snapshot?:string}>}){
  const {playerAlias}=await params;const {snapshot}=await searchParams;
  if(!isRankingSnapshotId(snapshot))notFound();
  if(process.env.NODE_ENV==='production'){
    if(!/^[a-f0-9]{12}$/.test(playerAlias))notFound();
    const suffix=snapshot.slice(-24);
    const display=await readSiteDisplay<DisplayDefense>(`defense-${playerAlias}-${suffix}`);if(!display)notFound();
    return <DefenseTeamsPanel teams={[]} displayPlayers={display.displayPlayers} purpose="pvp_defense" rankingContext={display.rankingContext}/>;
  }
  const source=await getRankedDefense(playerAlias,snapshot);if(!source)notFound();
  return <DefenseTeamsPanel teams={source.teams} purpose="pvp_defense" rankingContext={source.rankingContext}/>;
}
