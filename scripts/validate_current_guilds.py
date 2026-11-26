"""Offline check of all accepted top-100 guild sources, IDs and roster boundaries."""
import hashlib,json
from datetime import datetime,timezone
from guild_rank_database import ROOT,connection,current_ranking,parse_rankings,parse_roster


def validate():
    ranking=current_ranking()
    if not ranking or ranking['status']!='success':raise ValueError('complete guild ranking missing')
    rebuilt=parse_rankings([ROOT/s['directory'] for s in ranking['sources']])
    if rebuilt['guilds']!=ranking['guilds']:raise ValueError('accepted guild ranks differ from saved game response')
    db=connection();rosters={};failures={};integrity={};war_sources=[]
    try:
        for gid,payload in db.execute('SELECT c.guild_id,r.payload FROM current_ranked_guild_rosters c JOIN guild_roster_sources r USING(source_id)'):rosters[gid]=json.loads(payload)
        for gid,status in db.execute("SELECT guild_id,status FROM guild_fetch_attempts WHERE part='roster' ORDER BY checked_at"):failures[gid]=status
        for table in ['guild_rank_sources','current_guild_rankings','guild_ranking_checks','guild_roster_sources','current_ranked_guild_rosters','guild_fetch_attempts']:
            integrity[table]=db.execute('PRAGMA quick_check('+table+')').fetchone()[0]
        foreign=sum(len(db.execute('PRAGMA foreign_key_check('+table+')').fetchall()) for table in ['current_guild_rankings','guild_ranking_checks','current_ranked_guild_rosters'])
        if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='guild_war_sources'").fetchone():
            ranked_ids={g['guildId'] for g in ranking['guilds']}
            war_sources=[json.loads(r[0]) for r in db.execute("SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id) WHERE c.kind='deployed_defense'")]
            war_sources=[r for r in war_sources if r['guildId'] in ranked_ids and r['sourceKind']=='verified-guildwar-tower-deployments']
    finally:db.close()
    members=0;complete=0;source_hashes=[];statuses={};unread=[]
    for guild in ranking['guilds']:
        doc=rosters.get(guild['guildId']);status=failures.get(guild['guildId'],'not_read');statuses[status]=statuses.get(status,0)+1
        if not doc:unread.append(guild['rank']);continue
        parsed=parse_roster(ROOT/doc['sourceDirectory'])
        if parsed!=doc or parsed['guildId']!=guild['guildId']:raise ValueError('accepted guild roster differs from saved response')
        members+=doc['membersRetrieved'];complete+=int(doc['membershipComplete']);source_hashes.append(doc['sourceSha256'])
    if any(s!='ok' for s in integrity.values()) or foreign:raise ValueError('guild storage integrity failed')
    report={'verifiedAt':datetime.now(timezone.utc).isoformat(),'snapshotId':ranking['snapshotId'],'rankRange':[1,100],'guilds':len(ranking['guilds']),'completeRosters':complete,'members':members,'rosterStates':statuses,'unreadRanks':unread,'tableIntegrity':integrity,'foreignKeyErrors':foreign,'defenseTeams':0,'defenseState':'not_read','nativeMemberDisplayLevelConfirmed':False,'internalIdsOrCredentialsIncluded':False,'sourceSetSha256':hashlib.sha256(json.dumps(sorted(source_hashes)).encode()).hexdigest()}
    report.update(defenseGuilds=sum(r['status']=='success' for r in war_sources),
                  defenseTeams=sum(len(d['teams']) for r in war_sources for t in r['towers'] for d in t.get('defenders') or []),
                  defenseState='partial_coverage' if war_sources else 'not_read')
    (ROOT/'reports/guild-top100-source-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    return report


if __name__=='__main__':
    report=validate();print(json.dumps({k:report[k] for k in ['guilds','completeRosters','members','rosterStates','unreadRanks','foreignKeyErrors','defenseTeams']}))
