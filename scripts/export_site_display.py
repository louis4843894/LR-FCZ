"""Publish validated display DTOs and PNGs locally, never private SQLite/captures.

Uses the existing development server, not the game session or an external API.
All new data is staged/validated before updating the checked-in display snapshot.
"""
import concurrent.futures
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import urllib.parse
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'http://127.0.0.1:3101'
FORBIDDEN = {'playerId', 'guildId', 'characterInstanceId', 'characterInstanceIdentity', 'equipmentInstanceIdentity', 'equipmentInstanceHash', 'instanceHash', 'owner', 'sourceFile', 'captureDirectory', 'privateDirectory', 'sourceField', 'valueGradeRaw', 'cookie', 'token', 'password', 'secret', 'LF_AC'}
PRIVATE_VALUE = re.compile(r'(?:^|[^A-Za-z0-9])[Uu][a-f0-9]{32}(?:$|[^A-Za-z0-9])|LF_AC\s*=|eyJ[A-Za-z0-9_-]{20,}\.|runtime\.private|data[\\/]research|[A-Z]:[\\/]', re.I)
ASSET = re.compile(r'^/api/local-research-assets/(characters|gear)/([A-Za-z0-9_-]{1,160})$')
CACHE = None


def assert_safe(value, depth=0):
    if depth > 48:
        raise ValueError('display depth exceeded')
    if isinstance(value, dict):
        if FORBIDDEN.intersection(value):
            raise ValueError('private display field')
        for part in value.values():
            assert_safe(part, depth+1)
    elif isinstance(value, list):
        for part in value:
            assert_safe(part, depth+1)
    elif isinstance(value, str) and PRIVATE_VALUE.search(value):
        raise ValueError('private display value')


def get_part(part, **params):
    cache = CACHE/(hashlib.sha256(json.dumps([part, params], sort_keys=True).encode()).hexdigest()+'.json')
    if cache.is_file():
        data = json.loads(cache.read_text(encoding='utf8'))
        assert_safe(data)
        return data
    url = ORIGIN+'/api/local-site-export?'+urllib.parse.urlencode({'part': part, **params})
    with urllib.request.urlopen(url, timeout=300) as response:
        if response.headers.get_content_type() != 'application/json':
            raise ValueError('export did not return JSON')
        data = json.load(response)
    assert_safe(data)
    cache.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf8')
    return data


def validate_png(data):
    if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) > 2*1024*1024:
        raise ValueError('invalid PNG envelope')
    cursor = 8
    first = True
    while cursor+12 <= len(data):
        length = struct.unpack('>I', data[cursor:cursor+4])[0]
        kind = data[cursor+4:cursor+8]
        end = cursor+8+length
        if end+4 > len(data) or zlib.crc32(data[cursor+4:end]) != struct.unpack('>I', data[end:end+4])[0]:
            raise ValueError('invalid PNG chunk')
        if first:
            if kind != b'IHDR' or length != 13:
                raise ValueError('invalid PNG header')
            width, height = struct.unpack('>II', data[cursor+8:cursor+16])
            if not (0 < width <= 4096 and 0 < height <= 4096):
                raise ValueError('invalid PNG dimensions')
            first = False
        cursor = end+4
        if kind == b'IEND':
            if length or cursor != len(data):
                raise ValueError('invalid PNG tail')
            return
    raise ValueError('missing PNG end')


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for part in value.values():
            yield from strings(part)
    elif isinstance(value, list):
        for part in value:
            yield from strings(part)


def rewrite(value, urls):
    if isinstance(value, str):
        return urls.get(value, value)
    if isinstance(value, dict):
        return {key: rewrite(part, urls) for key, part in value.items()}
    if isinstance(value, list):
        return [rewrite(part, urls) for part in value]
    return value


def main():
    global CACHE
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume', type=Path)
    args = parser.parse_args()
    exported = dt.datetime.now(dt.timezone.utc).isoformat()
    private = (ROOT/'data/research/runtime.private').resolve()
    stage = args.resume.resolve() if args.resume else private/('site-display-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    if stage.parent != private or not stage.name.startswith('site-display-'):
        raise ValueError('resume folder outside known export directory')
    stage.mkdir(parents=True, exist_ok=bool(args.resume))
    CACHE = stage/'validated-parts'
    CACHE.mkdir(exist_ok=True)
    print('Reading validated local display models...', flush=True)
    catalog = get_part('catalogs')
    data = {'characters': catalog['characters'], 'equipment': catalog['equipment'], 'gear-icons': catalog['gearIcons'],
            'character-details': get_part('character-details'), 'guilds': get_part('guilds'), 'pvp-index': get_part('pvp-index')}
    if len(data['equipment']) != 953 or len(data['characters']['records']) != 2405 or len(data['character-details']) != 2405 or len(data['guilds']['guilds']) != 100:
        raise ValueError('accepted baseline count differs; old display data preserved')
    for guild in data['guilds']['guilds']:
        data['guild-'+guild['alias']] = get_part('guild', alias=guild['alias'])
    print('Guild display models: 100. Reading accepted PVP samples...', flush=True)
    for scope in data['pvp-index']:
        key = 'pvp-'+hashlib.sha256(scope.encode()).hexdigest()[:12]
        data[key] = get_part('pvp', scope=scope)
    defenses = get_part('defenses')
    for scope in data['pvp-index']:
        ranking = data['pvp-'+hashlib.sha256(scope.encode()).hexdigest()[:12]]['1000']
        for player in ranking['players']:
            if player['hasDefense'] and 'defense-'+player['alias']+'-'+ranking['snapshotId'][-24:] not in defenses:
                raise ValueError('ranked player display link is unresolved')
    data.update(defenses)
    data['status'] = get_part('status')
    assets = sorted({value for value in strings(data) if ASSET.fullmatch(value)})
    print(f'Display defenses: {len(defenses)}. Validating/copying {len(assets)} mapped PNGs...', flush=True)

    def copy_asset(url):
        match = ASSET.fullmatch(url)
        # A resumed run uses the same validated inputs. Reuse its checked PNGs.
        staged = list((stage/'public/site-assets'/match[1]).glob(match[2]+'.*.png'))
        if len(staged) == 1:
            content = staged[0].read_bytes()
            validate_png(content)
            digest = hashlib.sha256(content).hexdigest()
            if staged[0].name == f'{match[2]}.{digest[:12]}.png':
                return url, '/'+staged[0].relative_to(stage/'public').as_posix(), digest, len(content)
        with urllib.request.urlopen(ORIGIN+url, timeout=60) as response:
            if response.headers.get_content_type() != 'image/png':
                raise ValueError('mapped image not PNG')
            content = response.read(2*1024*1024+1)
        validate_png(content)
        digest = hashlib.sha256(content).hexdigest()
        relative = Path('site-assets')/match[1]/f'{match[2]}.{digest[:12]}.png'
        file = stage/'public'/relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(content)
        return url, '/'+relative.as_posix(), digest, len(content)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        copied = list(pool.map(copy_asset, assets))
    urls = {original: public for original, public, _, _ in copied}
    files = []
    (stage/'display').mkdir(exist_ok=True)
    for name, value in data.items():
        value = rewrite(value, urls)
        assert_safe(value)
        if any(s.startswith('/api/local-research-assets/') for s in strings(value)):
            raise ValueError('unresolved development asset URL')
        content = json.dumps({'schemaVersion': 1, 'kind': 'lr-site-display', 'name': name, 'data': value}, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
        compressed = gzip.compress(content, mtime=0)
        if len(compressed) > 12*1024*1024:
            raise ValueError('display artifact exceeds bound')
        (stage/'display'/(name+'.json.gz')).write_bytes(compressed)
        files.append({'name': name, 'sha256': hashlib.sha256(compressed).hexdigest(), 'bytes': len(compressed)})
    summary = {'schemaVersion': 1, 'kind': 'lr-site-display-manifest', 'exportedAt': exported,
               'counts': {'characters': 2405, 'equipment': 953, 'guilds': 100, 'guildDefenseComplete': data['guilds']['defenseGuilds'], 'guildDefensePartial': data['guilds']['partialDefenseGuilds'], 'rankedDefensePages': len(defenses), 'images': len(copied)},
               'sources': {'basicTemplates': 'verified-native', 'characterDetailsAndEquipmentRanges': 'user-confirmed-reference', 'playerConfigurationsAndGearValues': 'verified-local-observations', 'wholeGameCompleteness': 'unknown'},
               'files': files, 'assets': [{'url': public, 'sha256': digest, 'bytes': size} for _, public, digest, size in copied]}
    total = sum(f['bytes'] for f in files)+sum(row[3] for row in copied)
    if total > 55*1024*1024:
        raise ValueError('display publication total exceeds 55 MiB')
    # Every input, link, asset and privacy check passed; only now promote files.
    for folder, target in [('display', ROOT/'data/site-display'), ('public', ROOT/'public')]:
        for source in (stage/folder).rglob('*'):
            if source.is_file():
                destination = target/source.relative_to(stage/folder)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.is_file() and hashlib.sha256(destination.read_bytes()).digest() == hashlib.sha256(source.read_bytes()).digest():
                    continue
                temp = destination.with_suffix(destination.suffix+'.new')
                temp.write_bytes(source.read_bytes())
                os.replace(temp, destination)
    manifest = ROOT/'data/site-display/manifest.json'
    temp = manifest.with_suffix('.json.new')
    temp.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    os.replace(temp, manifest)
    (ROOT/'reports/site-display-export.json').write_text(json.dumps({'passed': True, 'counts': summary['counts'], 'totalBytes': total, 'source': 'existing-local-only'}, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'passed': True, 'counts': summary['counts'], 'totalBytes': total}), flush=True)


if __name__ == '__main__':
    main()
