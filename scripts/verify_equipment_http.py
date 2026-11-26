"""Check local page data and isolation of private files; does not contact external hosts."""
import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def verify(base_url, production=False):
    if urllib.parse.urlparse(base_url).hostname not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('Verification is limited to localhost')
    rows = []
    cases = [('/', 200), ('/gear', 200), ('/gear?q=eq_2202_amr_06&star=6&type=ARMOR', 200),
             ('/gear/eq_2202_amr_06_nm?level=5', 200), ('/characters', 200), ('/pvp', 200), ('/guild', 200),
             ('/data/gear.json', 404), ('/data/rangers.json', 404), ('/data/guilds.json', 404),
             ('/data/research/runtime.private/latest-capture.json', 404),
             ('/data/normalized/equipment-reference-preview.json', 404),
             ('/api/local-research-assets/gear/eq_2202_amr_06', 404 if production else 200)]
    for path, expected in cases:
        try:
            response = urllib.request.urlopen(base_url.rstrip('/') + path, timeout=45)
            status, body = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, body = error.code, error.read()
        text = body.decode('utf8', errors='replace')
        checks = {'expectedStatus': status == expected,
                  'noPrivateFields': not any(s in text for s in ['managerAddress', 'gradeCipherFile', 'rawRecordSha256', '"objectAddress"'])}
        if path == '/gear/eq_2202_amr_06_nm?level=5':
            checks.update({'targetName': '日暮永遠的制服' in text, 'sixStars': '6 星' in text,
                           'armor': 'ARMOR' in text, 'localEffectsUnknown': '尚未解析' in text,
                           'referenceModeCorrect': ('Rangerbook / WarmyCat' in text) != production})
        if path == '/gear':
            checks['hasActualCount'] = '953' in text
        if path.startswith('/api/') and not production:
            checks['validPng'] = body.startswith(bytes.fromhex('89504e470d0a1a0a'))
        rows.append({'path': path, 'status': status, 'checks': checks})
    return {'mode': 'production' if production else 'development', 'baseUrl': base_url,
            'cases': rows, 'passed': all(all(row['checks'].values()) for row in rows)}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url', default='http://127.0.0.1:3101')
    p.add_argument('--production', action='store_true')
    a = p.parse_args()
    result = verify(a.base_url, a.production)
    output = ROOT / ('reports/website-http-production-validation.json' if a.production else 'reports/website-http-validation.json')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'mode': result['mode'], 'cases': len(result['cases']), 'passed': result['passed']}))
    if not result['passed']:
        print(json.dumps(result, ensure_ascii=True, indent=2))
        raise SystemExit(1)
