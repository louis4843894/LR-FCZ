import {notFound} from 'next/navigation';
import {getRankedDefense,isRankingSnapshotId} from '../../../../lib/pvp-rankings';
import {DefenseTeamsPanel} from '../../../_components/defense-teams-panel';

export default async function RankedPlayer({params,searchParams}:{params:Promise<{playerAlias:string}>;searchParams:Promise<{snapshot?:string}>}){
  const {playerAlias}=await params;const {snapshot}=await searchParams;
  if(!isRankingSnapshotId(snapshot))notFound();
  const source=await getRankedDefense(playerAlias,snapshot);if(!source)notFound();
  return <DefenseTeamsPanel teams={source.teams} purpose="pvp_defense" rankingContext={source.rankingContext}/>;
}
