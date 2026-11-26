"""Local catalogue acceptance: real guild ranks, no external branding/login gate."""
import argparse,hashlib,json,sqlite3,urllib.parse
from pathlib import Path
from browser_session import Browser,ROOT


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',action='append');args=parser.parse_args()
    db=sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)
    ranking=json.loads(db.execute("SELECT r.payload FROM current_guild_rankings c JOIN guild_rank_sources r USING(snapshot_id) WHERE c.scope='top100'").fetchone()[0])
    rosters={gid:json.loads(p) for gid,p in db.execute('SELECT c.guild_id,r.payload FROM current_ranked_guild_rosters c JOIN guild_roster_sources r USING(source_id)')}
    private_ids=[g['guildId'] for g in ranking['guilds']]+[m['playerId'] for r in rosters.values() for m in r['members']]
    first=ranking['guilds'][0];last=ranking['guilds'][-1]
    url=lambda g:'/guild/'+hashlib.sha256(g['guildId'].encode()).hexdigest()[:20]
    records=[]
    with Browser('catalog-acceptance') as b:
        cases=[('home-desktop','/',1440,'LINE Rangers 資料站'),('home-mobile','/',390,'LINE Rangers 資料站'),
               ('guild-desktop','/guild',1440,'公會排名'),('guild-mobile','/guild',390,'公會排名'),
               ('guild-master','/guild?grade='+urllib.parse.quote('大師'),390,'公會排名'),
               ('guild-rank100','/guild?q=100',390,'公會排名'),
               ('guild-first',url(first),1440,first['name']),('guild-last',url(last),390,last['name']),
               ('gear','/gear',1440,'裝備圖鑑'),('gear-detail','/gear/eq_2202_amr_06_nm?level=5',390,'6 星'),
               ('characters','/characters',390,'角色與技能'),
               ('pvp','/pvp?top=10',1440,'排行榜'),('status','/data-status',390,'完成度與尚未完成項目')]
        if args.case:cases=[c for c in cases if c[0] in args.case]
        if not cases:raise ValueError('requested catalogue cases unavailable')
        for name,path,width,text in cases:
            b.navigate('http://127.0.0.1:3101'+path,width,'document.body.innerText.includes('+json.dumps(text)+')')
            visible=b.evaluate('document.body.innerText');html=b.evaluate('document.documentElement.outerHTML')
            checks={'expectedText':text in visible,'noHorizontalOverflow':b.evaluate('document.documentElement.scrollWidth<=innerWidth'),
                    'noExternalSourceBranding':not any(x in visible.lower() for x in ['rangerbook','warmycat','外部來源','外部參考','外部對照']),
                    'noExternalSourceLinks':b.evaluate('!Array.from(document.querySelectorAll("a")).some(a=>a.href.includes("warmycat"))'),
                    'noRawGuildOrPlayerIds':all(value not in html for value in private_ids),
                    'noLoginGate':'需要登入' not in visible and '付費解鎖' not in visible}
            if name=='home-mobile':
                b.evaluate('document.querySelector(".nav-toggle").click()')
                b.evaluate('new Promise(r=>setTimeout(r,200))')
                checks['mobileMenuOpens']=b.evaluate('document.querySelector(".nav-toggle").getAttribute("aria-expanded")==="true"&&document.querySelector(".module-nav").getBoundingClientRect().height>0')
                b.evaluate('document.querySelector(".nav-toggle").click()')
                b.evaluate('new Promise(r=>setTimeout(r,100))')
                checks['mobileMenuCloses']=b.evaluate('document.querySelector(".nav-toggle").getAttribute("aria-expanded")==="false"')
            if name in ('guild-desktop','guild-mobile'):
                checks['actual100Guilds']=b.evaluate('document.querySelectorAll(".guild-ranking-row").length')==100
                checks['allRostersAndActualMembers']='100／100' in visible and '4,751' in visible
            if name=='guild-master':checks['keepsActualRanks51To100']=b.evaluate('JSON.stringify(Array.from(document.querySelectorAll(".rank-number")).map(n=>Number(n.innerText)))')==json.dumps(list(range(51,101)),separators=(',',':'))
            if name=='guild-rank100':checks['oneActualRank100']=b.evaluate('document.querySelectorAll(".guild-ranking-row").length===1&&document.querySelector(".rank-number").innerText==="100"')
            if name in ('guild-first','guild-last'):
                guild=first if name=='guild-first' else last;roster=rosters[guild['guildId']]
                checks['actualRosterRows']=b.evaluate('document.querySelectorAll(".guild-member-row").length')==len(roster['members'])
                checks['defenseUnknownNotEmpty']=('十座塔配置尚未取得' in visible or '塔內駐防尚未取得' in visible) and '沒有裝備' not in visible
                checks['noPvpFallback']=b.evaluate('document.querySelectorAll(".defense-member").length')==0
            if name=='gear-detail':checks['templateRangesRemainSeparate']='模板的可能範圍' in visible and '玩家實際詞條' in visible
            if name=='pvp':checks['rankingRows']=b.evaluate('document.querySelectorAll(".ranking-player").length')==10
            b.screenshot(name);records.append({'case':name,'checks':checks})
            if not all(checks.values()):break
        passed=len(records)==len(cases) and all(all(r['checks'].values()) for r in records) and not b.errors
        report={'passed':passed,'cases':records,'runtimeErrors':b.errors,'source':'local-game-data','referenceDataImported':False}
        report_name='catalog-guild-ui-focused-validation.json' if args.case else 'catalog-guild-ui-validation.json'
        (ROOT/'reports'/report_name).write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
        print(json.dumps({'passed':passed,'cases':len(records),'failedCases':[r['case'] for r in records if not all(r['checks'].values())],'runtimeErrors':b.errors}))
        if not passed:raise SystemExit(1)


if __name__=='__main__':main()
