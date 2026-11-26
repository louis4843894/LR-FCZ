import policy from '../data/config/pvp-scope-policy.json';
export const pvpScopeOrder=policy.scopes.map(s=>s.label);
export function canonicalPvpScope(scope:string){return (policy.legacyScopeAliases as Record<string,string>)[scope]??scope;}
export function activePvpScope(scope:string){return pvpScopeOrder.includes(canonicalPvpScope(scope));}
