"""Check the staged Git tree for excluded captures and literal credentials.

Reads staged blobs locally. Prints only rule names/locations, never matched
values. No login, remote request, unstaged secret read, or file modification.
"""
import hashlib
import gzip
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'literal-jwt': re.compile(rb'\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\b'),
    'literal-session-cookie': re.compile(rb'LF_AC\s*=\s*[A-Za-z0-9%._~+/=\-]{16,}'),
    'account-identifier': re.compile(rb'(?<![A-Za-z0-9])[Uu][a-fA-F0-9]{32}(?![A-Za-z0-9])'),
    'literal-secret-assignment': re.compile(
        rb'(?:key|secret|token|password)\s*=\s*(?:b)?["\x27][A-Za-z0-9+/=]{24,}["\x27]', re.I),
}


def git(*args, **kwargs):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=True, **kwargs).stdout


def check():
    entries = []
    for entry in git('ls-files', '--stage', '-z').split(b'\0'):
        if not entry:
            continue
        header, path = entry.split(b'\t', 1)
        mode, oid, stage = header.decode().split()
        if stage != '0':
            raise ValueError('unmerged index')
        entries.append((path.decode('utf8'), oid, mode))
    if not entries:
        raise ValueError('empty staged tree')
    batch = git('cat-file', '--batch', input=('\n'.join(oid for _, oid, _ in entries)+'\n').encode())
    cursor = 0
    total = 0
    findings = []
    for path, oid, mode in entries:
        end = batch.index(b'\n', cursor)
        actual_oid, kind, length = batch[cursor:end].decode().split()
        size = int(length)
        if actual_oid != oid or kind != 'blob':
            raise ValueError('staged blob identity differs')
        blob = batch[end+1:end+1+size]
        cursor = end+1+size+1
        total += size
        if size > 12*1024*1024 or total > 64*1024*1024:
            findings.append({'path': path, 'rule': 'publication-size-bound'})
        name = Path(path).name
        placeholder = name == '.gitkeep' and not blob
        forbidden = ((not placeholder and path.startswith(('data/raw/', 'data/extracted/', 'data/research/', 'data/inventory/',
                                     'data/local/', 'reports/', 'node_modules/', '.next'))
                     or name.startswith('.env') and name != '.env.example'
                     or any(tag in name for tag in ('.private.', '.personal.', '.secret.', '.credentials.', '.account.'))
                     or Path(path).suffix.lower() in ('.apk', '.apks', '.so', '.dex', '.bin', '.sqlite', '.db', '.ndb')
                     or mode not in ('100644', '100755')))
        if forbidden:
            findings.append({'path': path, 'rule': 'excluded-local-input'})
        scanned = blob
        if path.startswith('data/site-display/') and path.endswith('.json.gz'):
            if name == 'guilds.json.gz' or name.startswith('guild-'):
                findings.append({'path': path, 'rule': 'private-guild-display'})
            from export_site_display import assert_safe
            try:
                scanned = gzip.decompress(blob)
                if len(scanned) > 80*1024*1024:
                    raise ValueError('display output bound')
                document = json.loads(scanned)
                if document['schemaVersion'] != 1 or document['kind'] != 'lr-site-display':
                    raise ValueError('display schema')
                assert_safe(document)
            except Exception:
                findings.append({'path': path, 'rule': 'invalid-display-artifact'})
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(scanned):
                findings.append({'path': path, 'rule': label, 'line': scanned.count(b'\n', 0, match.start())+1})
    return {'stagedFiles': len(entries), 'stagedBytes': total,
            'indexManifestSha256': hashlib.sha256(json.dumps(entries).encode()).hexdigest(),
            'passed': not findings, 'findings': findings, 'networkRequests': 0}


if __name__ == '__main__':
    result = check()
    (ROOT/'reports/git-publication-check.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf8')
    print(json.dumps(result))
    if not result['passed']:
        raise SystemExit(1)
