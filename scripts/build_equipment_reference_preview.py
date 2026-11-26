"""Build an attributed local preview from saved, user-confirmed public sources.
External numeric values are never promoted to locally verified fields.
"""
import datetime
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ReferenceLabels:
    """Catalog boundary rules from the reference's actually loaded V2 renderer."""
    def __init__(self, catalogs):
        self.catalogs = catalogs

    def argument(self, value):
        if isinstance(value, dict) and 'min' in value and 'max' in value:
            a, b = value['min'], value['max']
            suffix = {'PERCENT': '%', 'SECOND': '秒'}.get(value.get('unit'), '')
            return (str(a) if a == b else f'{a}～{b}') + suffix
        if isinstance(value, dict):
            return self.render(value)
        return '' if value is None else str(value)

    def render(self, ref):
        if isinstance(ref, str):
            # Only external catalogs use this documented multi-slash convention.
            return re.sub(r'\\+n', '\n', self.catalogs.get(ref, ref))
        if not isinstance(ref, dict):
            return str(ref)
        if 'parts' in ref:
            return ''.join(self.render(x) for x in ref['parts'])
        if 'templateKey' in ref:
            text, args, slot = self.render(ref['templateKey']), ref.get('args', []), 0
            def substitute(match):
                nonlocal slot
                token = match.group(0)
                digits = re.search(r'\d+', token)
                i = int(digits.group()) - 1 if digits else slot
                if not digits:
                    slot += 1
                if not 0 <= i < len(args):
                    raise ValueError('Unbound reference argument: ' + token)
                return self.argument(args[i])
            return re.sub(r'%(?:N\d*|d\d*|s|n)', substitute, text)
        if 'key' in ref:
            text = self.render(ref['key'])
            for code, value in ref.get('bindings', {}).items():
                text = text.replace('{' + code + '}', self.argument(value))
            if re.search(r'\{\$\d+[pf]\}', text):
                raise ValueError('Unbound native description: ' + ref['key'])
            return re.sub(r'<#(?:[0-9a-f]+)>|<->', '', text, flags=re.I)
        raise ValueError('Unknown external text reference')

def reference_key(value):
    return value if isinstance(value, str) else json.dumps(value, sort_keys=True, separators=(',', ':'))

def build():
    source = ROOT / 'data/research/external-reference'
    local = json.loads((ROOT / 'data/normalized/verified-equipment.json').read_text(encoding='utf8'))
    external = json.loads((source / 'equipment.json').read_text(encoding='utf8'))
    catalogs = {}
    for file in ['official-locales.json', 'custom-locales.json']:
        for row in json.loads((source / file).read_text(encoding='utf8')):
            catalogs[row['key']] = row.get('zh_TW') or row.get('en') or row['key']
    label = ReferenceLabels(catalogs).render
    def option(x, kind):
        return {'optionKey': x['optionKey'], 'name': label(x['optionKey']), 'category': kind,
                'range': x.get('range', x.get('valueRange')), 'upgradeStep': x.get('upgradeStep'), 'attributeId': None}

    target = {r['itemCode']: r for r in local['records']}
    records, conflicts, seen = [], [], set()
    for row in external['equipment']:
        code = row['equipCode']
        if code in seen:
            raise ValueError('Duplicate external equipment ID: ' + code)
        seen.add(code)
        if code not in target:
            continue
        own = target[code]
        if row['starGrade'] != own['starCount'] or row['equipType'] != own['equipType']:
            conflicts.append({'itemCode': code, 'local': {'star': own['starCount'], 'type': own['equipType']},
                              'reference': {'star': row['starGrade'], 'type': row['equipType']}})
            continue
        advanced = None
        high = row.get('highLevelOptions')
        if high:
            key = 'CUSTOM:EQUIP_RANGER_TYPE_' + high['targetCondition']['value']
            advanced = {'condition': {'key': key, 'label': label(key)},
                        'defaultOption': option(high['defaultOption'], 'advanced'),
                        'switchOptions': [option(e, 'advanced') for e in high['switchOptions']]}
        skills = [{'effectCode': x['effectCode'], 'name': label('CUSTOM:' + x['effectCode']),
                   'dimension': x['dimension'], 'range': x['range'], 'upgradeStep': x.get('upgradeStep')}
                  for x in row.get('skillPlus', [])]
        spec, sp = None, row.get('specPlus')
        if sp:
            spec = {'name': label(sp['nameKey']), 'basicOptions': [option(e, 'spec-plus') for e in sp['basicOptions']], 'specialOptions': []}
            for x in sp['specialOptions']:
                e = x.get('effect', {})
                description = {'key': x['descriptionKey'], 'bindings': x.get('descriptionBindings', {})} if x.get('descriptionKey') else None
                spec['specialOptions'].append({
                    'description': label(description) if description else None,
                    'conditions': [{'key': reference_key(k), 'label': label(k)} for k in x.get('conditionKeys', [])],
                    'triggerChance': x.get('triggerChance'), 'effectCode': e.get('effectCode'),
                    'effectName': label(e['nameKey']) if e.get('nameKey') else None,
                    'chance': e.get('chance'), 'chanceUpgrade': e.get('chanceUpgrade'),
                    'magnitudeRange': e.get('magnitudeRange'), 'magnitudeUpgrade': e.get('magnitudeUpgrade'),
                    'durationRange': e.get('durationRange'), 'durationUpgradeSeconds': e.get('durationUpgradeSeconds')})
        records.append({'itemCode': code, 'normalOptions': [option(e, 'basic') for e in row['normalOptions']],
                        'advanced': advanced, 'skillPlus': skills, 'specPlus': spec})
    manifest = json.loads((source / 'comparison.json').read_text(encoding='utf8'))
    urls = {
        'equipment.json': 'https://rangerbook.warmycat.com/res/v2/equipment.json',
        'gear-detail.js': 'https://rangerbook.warmycat.com/assets/js/gear-detail.js?v=20261102-number-format1',
        'public-script-1.js': 'https://rangerbook.warmycat.com/assets/js/v2-data.js?v=20261013-thai1',
        'official-locales.json': 'https://rangerbook.warmycat.com/res/v2/fast/locales/zh_TW.json',
        'custom-locales.json': 'https://rangerbook.warmycat.com/res/v2/locales/custom.json?v=20261013-thai1'}
    result = {'schemaVersion': 1, 'sourceKind': 'external-user-confirmed', 'userConfirmed': True,
              'localNumericVerification': False, 'publicationAllowed': False,
              'sourceUrl': 'https://rangerbook.warmycat.com/gear/', 'dataUrl': urls['equipment.json'],
              'retrievedAt': manifest['fetchedAt'], 'resourceVersion': None,
              'sources': [{'url': url, 'sha256': hashlib.sha256((source / file).read_bytes()).hexdigest()} for file, url in urls.items()],
              'rules': {'basic': 'base * (level + 1)', 'advanced': 'base + level * explicit upgradeStep',
                        'skillPlus': 'base + level * explicit upgradeStep', 'specBasic': 'base + level * explicit upgradeStep',
                        'specSpecial': 'effect chance/magnitude/duration use their explicit steps; description and outer trigger chance remain +0'},
              'matchedRecordCount': len(records), 'conflicts': conflicts, 'records': records}
    dest = ROOT / 'data/normalized/equipment-reference-preview.json'
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    (ROOT / 'reports/equipment-reference-identities.json').write_text(
        json.dumps({k: v for k, v in result.items() if k != 'records'}, ensure_ascii=False, indent=2), encoding='utf8')
    print('REFERENCE_PREVIEW', len(records), 'identity/star/type matched; conflicts', len(conflicts))

if __name__ == '__main__':
    build()
