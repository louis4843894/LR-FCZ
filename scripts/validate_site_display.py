"""Validate the actual production display snapshot and cross-page links."""
import gzip
import hashlib
import json
import re
from pathlib import Path
from export_site_display import ROOT, assert_safe, strings, validate_png


def main():
    folder = ROOT/'data/site-display'
    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf8'))
    assert manifest['kind'] == 'lr-site-display-manifest' and manifest['schemaVersion'] == 1
    data = {}
    private_guild_names = []
    for row in manifest['files']:
        name = row['name']
        source = folder/(name+'.json.gz')
        if re.fullmatch(r'guilds|guild-[a-f0-9]{20}', name):
            private_guild_names.append(name)
            if not source.is_file():
                continue
        content = source.read_bytes()
        assert len(content) == row['bytes'] and hashlib.sha256(content).hexdigest() == row['sha256']
        document = json.loads(gzip.decompress(content))
        assert document['schemaVersion'] == 1 and document['kind'] == 'lr-site-display' and document['name'] == row['name']
        assert_safe(document)
        data[row['name']] = document['data']
    images = set()
    for row in manifest['assets']:
        assert row['url'].startswith('/site-assets/') and '..' not in row['url']
        content = (ROOT/'public'/row['url'].lstrip('/')).read_bytes()
        assert len(content) == row['bytes'] and hashlib.sha256(content).hexdigest() == row['sha256']
        validate_png(content)
        images.add(row['url'])
    for value in strings(data):
        assert not value.startswith('/api/local-research-assets/')
        if value.startswith('/site-assets/'):
            assert value in images
    gear = {row['itemCode']: row for row in data['equipment']}
    characters = {row['characterId']: row for row in data['characters']['records']}
    assert len(gear) == 953 and len(characters) == 2405 and len(data['character-details']) == 2405
    assert gear['eq_2202_amr_06']['starCount'] == 6 and gear['eq_2202_amr_06']['equipType'] == 'ARMOR'
    assert gear['eq_2202_wpn_17']['starCount'] == 7
    assert sum(row['imageUrl'] in images for row in characters.values()) == 2405
    guild_count = sum(name in data for name in private_guild_names)
    assert guild_count in (0, len(private_guild_names)), 'Private guild display export is partial'
    guilds = data.get('guilds', {}).get('guilds', [])
    if guild_count:
        assert len(guilds) == 100 and sorted(row['rank'] for row in guilds) == list(range(1, 101))
    roster = units = equipped = empty = unknown = enhancements = progress = 0
    for guild in guilds:
        detail = data['guild-'+guild['alias']]
        assert detail['guild'] == guild
        roster += len(detail['roster']['members']) if detail['roster'] else 0
        war = detail['war']
        if not war:
            continue
        assert war['savedConfigurations'] == []
        if not war['deployment']:
            continue
        for tower in war['deployment']['towers']:
            assert tower['number'] is None or 1 <= tower['number'] <= 10
            for defender in tower['defenders'] or []:
                for team in defender['teams']:
                    positions = [unit['position'] for unit in team['units']]
                    assert len(set(positions)) == len(positions)
                    for unit in team['units']:
                        units += 1
                        assert unit['characterId'] in characters
                        progress += unit['characterProgress'] is not None
                        assert [slot['slot'] for slot in unit['slots']] == ['weapon', 'armor', 'accessory']
                        for slot in unit['slots']:
                            if slot['state'] == 'equipped':
                                equipped += 1
                                assert slot['equipmentId'] in gear
                                enhancements += slot['enhancement'] is not None
                            elif slot['state'] == 'not_equipped':
                                empty += 1
                            else:
                                unknown += 1
    defenses = 0
    for scope in data['pvp-index']:
        assert not any(label in scope for label in ['白銀', '青銅'])
        variants = data['pvp-'+hashlib.sha256(scope.encode()).hexdigest()[:12]]
        for top, ranking in variants.items():
            assert ranking is not None and ranking['top'] == int(top)
            assert len({p['alias'] for p in ranking['players']}) == len(ranking['players'])
            assert all(p['rank'] <= int(top) for p in ranking['players'])
            assert ranking['stats']['validPlayers'] <= len(ranking['players'])
        ranking = variants['1000']
        for player in ranking['players']:
            if not player['hasDefense']:
                continue
            display = data['defense-'+player['alias']+'-'+ranking['snapshotId'][-24:]]
            assert display['rankingContext']['snapshotId'] == ranking['snapshotId']
            assert display['rankingContext']['rank'] == player['rank']
            assert display['displayPlayers'] and display['displayPlayers'][0]['teams']
            defenses += 1
    report = {'passed': True, 'files': len(data), 'characters': len(characters), 'equipment': len(gear), 'images': len(images), 'guilds': len(guilds),
              'rosterMembers': roster, 'guildRoles': units, 'guildEquipped': equipped, 'guildEmptySlots': empty, 'guildUnknownSlots': unknown,
              'guildEnhancementKnown': enhancements, 'guildCharacterProgress': progress, 'pvpScopes': len(data['pvp-index']), 'pvpDefenseLinks': defenses}
    (ROOT/'reports/site-display-validation.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
