"""Browser acceptance against next start (production), without local database use."""
import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from browser_session import Browser, ROOT


def load(name):
    return json.loads(gzip.decompress((ROOT/'data/site-display'/(name+'.json.gz')).read_bytes()))['data']


def main():
    characters = load('characters')
    details = load('character-details')
    sample = next(r for r in characters['records'] if details[r['characterId']]['details'] and details[r['characterId']]['details']['skills'] and details[r['characterId']]['nativeTalents'] and details[r['characterId']]['nativeTalents']['status'] == 'verified-native-group')
    guilds = load('guilds')
    guild = next(g for g in guilds['guilds'] if g['defenseState'] == 'success')
    manifest = json.loads((ROOT/'data/site-display/manifest.json').read_text(encoding='utf8'))
    defense_name = next(row['name'] for row in manifest['files'] if row['name'].startswith('defense-') and load(row['name'])['displayPlayers'][0]['teams'][0]['units'])
    defense = load(defense_name)
    alias = defense_name.split('-')[1]
    private_checks = {}
    for path, expected_status in [('/api/local-site-export?part=catalogs', 404), ('/api/local-research-assets/characters/'+sample['characterId'], 404), ('/api/local-updates/pvp', 403)]:
        try:
            with urllib.request.urlopen('http://127.0.0.1:3101'+path, timeout=30) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
        private_checks[path.split('?')[0]] = status == expected_status
    results = []
    with Browser('production-display', protocol_timeout=180) as b:
        for width in (1440, 390):
            cases = [
                ('home', '/', '2,405'),
                ('characters', '/characters?star=9&sort=star-desc', '筆結果'),
                ('character-detail', '/characters/'+urllib.parse.quote(sample['characterId'])+'#character-skills', sample['name']),
                ('gear-detail', '/gear/eq_2202_amr_06_nm?level=5', '6 星'),
                ('guilds', '/guild', '4,751'),
                ('guild-defense', '/guild/'+guild['alias']+'?tower=1', guild['name']),
                ('pvp', '/pvp?top=10', '排行榜'),
                ('pvp-defense', '/pvp/players/'+alias+'?snapshot='+defense['rankingContext']['snapshotId'], 'PVP 防禦隊伍'),
            ]
            for name, path, expected in cases:
                b.navigate('http://127.0.0.1:3101'+path, width, 'document.querySelector("main h1")?.getBoundingClientRect().height>0')
                # Wait for visible images rather than accepting blank lazy-loading tiles.
                b.evaluate('Promise.all(Array.from(document.images).filter(i=>{const r=i.getBoundingClientRect();return r.bottom>0&&r.top<innerHeight&&r.width>0}).map(i=>i.complete?Promise.resolve():new Promise(resolve=>{i.addEventListener("load",resolve,{once:true});i.addEventListener("error",resolve,{once:true})})))')
                b.evaluate('new Promise(r=>setTimeout(r,200))')
                checks = {
                    'expectedContent': expected in b.evaluate('document.querySelector("main").innerText'),
                    'noOverflow': b.evaluate('document.documentElement.scrollWidth<=innerWidth'),
                    'visibleImagesValid': b.evaluate('Array.from(document.images).filter(i=>{const r=i.getBoundingClientRect();return r.bottom>0&&r.top<innerHeight&&r.width>0}).every(i=>i.complete&&i.naturalWidth>0)'),
                    'noPrivateAssetEndpoint': b.evaluate('Array.from(document.images).every(i=>!i.src.includes("/api/local-research-assets/"))'),
                    'noPrivateResearchData': b.evaluate('!/(?:runtime\\.private|sourceFile|equipmentInstanceIdentity|characterInstanceIdentity|LF_AC)/.test(document.documentElement.outerHTML)'),
                }
                if name == 'character-detail':
                    checks['skillsAndStartup'] = b.evaluate('document.querySelectorAll(".character-skill-card").length>0&&document.querySelector("#character-skills").textContent.includes("前搖")')
                if name == 'guilds':
                    checks['real100Guilds'] = b.evaluate('document.querySelectorAll(".guild-ranking-row").length===100')
                if name in ('guild-defense', 'pvp-defense'):
                    checks['actualTeams'] = b.evaluate('document.querySelectorAll(".dv-shell").length>0')
                b.screenshot(name+'-'+str(width))
                results.append({'case': name+'-'+str(width), 'checks': checks})
                if not all(checks.values()):
                    break
        errors = b.errors
    report = {'passed': len(results) == 16 and all(all(r['checks'].values()) for r in results) and all(private_checks.values()) and not errors, 'cases': results, 'privateEndpointsDenied': private_checks, 'runtimeErrors': errors}
    (ROOT/'reports/site-display-production-ui.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'passed': report['passed'], 'cases': len(results), 'failedCases': [r['case'] for r in results if not all(r['checks'].values())], 'privateEndpointsDenied': private_checks, 'runtimeErrors': errors}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
