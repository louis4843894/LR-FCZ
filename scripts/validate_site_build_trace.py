"""Ensure Next deployment traces include display artifacts, never private inputs."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dist', default='.next-local-site-display-build')
    args = parser.parse_args()
    folder = (ROOT/args.dist).resolve()
    if folder.parent != ROOT or not folder.name.startswith('.next'):
        raise ValueError('unexpected build folder')
    manifest = json.loads((ROOT/'data/site-display/manifest.json').read_text(encoding='utf8'))
    expected = {f"data/site-display/{row['name']}.json.gz" for row in manifest['files']}
    traces = list((folder/'server/app').rglob('*.nft.json'))
    if not traces:
        raise ValueError('no server deployment traces')
    bad = []
    covered = set()
    for file in traces:
        for item in json.loads(file.read_text(encoding='utf8'))['files']:
            resolved = (file.parent/item).resolve()
            try:
                relative = resolved.relative_to(ROOT).as_posix()
            except ValueError:
                continue
            if relative in expected:
                covered.add(relative)
            if relative.startswith(('data/local/', 'data/research/', 'data/raw/', 'data/extracted/', 'reports/')) or '.private.' in relative or relative.startswith('.env') and relative != '.env.example':
                bad.append({'trace': file.relative_to(folder).as_posix(), 'path': relative})
    report = {'passed': not bad and covered == expected, 'traces': len(traces), 'expectedDisplayFiles': len(expected), 'coveredDisplayFiles': len(covered), 'privateFileFindings': bad}
    (ROOT/'reports/site-display-build-trace.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(json.dumps(report))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
