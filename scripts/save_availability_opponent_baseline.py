"""Preserve accepted character/war versions and the focused code/evidence.

Keeps source hashes and existing immutable input paths. Does not copy the live
database, PVP records, credentials or process memory. No network requests.
"""
import hashlib
import json
import sqlite3
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    reports = ['availability-opponent-ui-validation.json',
               'guild-top100-coverage-ui-validation.json']
    if not all(json.loads((ROOT/'reports'/n).read_bytes())['passed'] for n in reports):
        raise ValueError('affected UI acceptance required')
    database = ROOT/'data/local/lr.private.sqlite'
    with closing(sqlite3.connect(database.as_uri()+'?mode=ro', uri=True)) as db:
        details = db.execute('SELECT source_id FROM current_character_details').fetchone()[0]
        rolls = db.execute("SELECT source_id FROM current_gear_rolls WHERE scope='guildwar'").fetchone()[0]
        progress = db.execute('SELECT source_id FROM current_character_instance_sources').fetchone()[0]
        wars = [json.loads(p) for p, in db.execute(
            'SELECT s.payload FROM current_guild_war_sources c JOIN guild_war_sources s USING(source_id)')]
    inputs = {ROOT/'data/normalized/verified-characters.json',
              ROOT/'data/normalized/verified-equipment.json',
              ROOT/'data/research/runtime.private/character-detail-exports'/details/'details.private.json',
              ROOT/'data/research/runtime.private/gear-roll-exports'/rolls/'rolls.private.json',
              ROOT/'data/research/runtime.private/character-instance-exports'/progress/'instances.private.json'}
    for war in wars:
        directory = ROOT/war['sourceDirectory']
        inputs.add(directory/war['sourceFile'])
        inputs.update(directory/s['file'] for s in war.get('towerSources', []))
    input_hashes = []
    for path in sorted(inputs):
        if not path.resolve().is_relative_to(ROOT/'data'):
            raise ValueError('accepted source outside project data')
        input_hashes.append({'path': path.relative_to(ROOT).as_posix(),
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                             'bytes': path.stat().st_size})
    files = [
        'scripts/template_availability.py', 'scripts/audit_reference_availability.py',
        'scripts/build_character_details.py', 'scripts/sync_character_details_supabase.py',
        'scripts/audit_guild_defense_coverage.py', 'scripts/audit_guild_defense_entrypoints.py',
        'scripts/ghidra/find_guild_literal_readers.py', 'scripts/ghidra/find_guild_request_callers.py',
        'scripts/runtime/probe_guild_profile_during_battle.py',
        'scripts/runtime/fetch_ranked_pvp_response.py',
        'scripts/verify_availability_opponent_ui.py', 'scripts/save_availability_opponent_baseline.py',
        'lib/template-availability.ts', 'lib/character-details.ts', 'lib/local-game-data.ts',
        'lib/character-reference.ts', 'lib/guild-rankings.ts',
        'app/_components/character-detail-panels.tsx', 'app/_components/equipment-reference-panel.tsx',
        'app/characters/page.tsx', 'app/characters/[characterId]/page.tsx',
        'app/gear/[dataCode]/page.tsx', 'app/data-status/page.tsx', 'app/guild/page.tsx',
        'tests/template-availability.test.ts', 'tests/character-details.test.ts',
        'tests/character-detail-reader.test.ts', 'tests/guild-rankings.test.ts',
        'tests/test_character_details.py', '.vscode/settings.json',
        'docs/current-state.md', 'package.json', 'package-lock.json', 'tsconfig.json',
    ]
    files += ['reports/'+n for n in reports + [
        'reference-availability-audit.json', 'character-detail-validation.json',
        'guildwar-current-validation.json', 'guild-top100-defense-coverage.json',
        'guild-top100-defense-entrypoint-audit.json', 'guildwar-reader-callers.json',
        'guild-defense-model-readers.json', 'guild-profile-battle-phase-check.json',
        'guild-ranking-battle-phase-check.json', 'guild-history-battle-phase-check.json',
        'guild-contribution-battle-phase-check.json', 'public-guildwar-reference-shape.json',
        'guild-top100-supabase-receipt.json', 'character-details-supabase-receipt.json',
        'availability-opponent-build.log', 'availability-opponent-lint.log',
        'ghidra/guild-target-transport-and-replay-model-1242.txt',
        'ghidra/guild-context-helpers-and-replay-caller-1242.txt',
    ]]
    at = datetime.now(timezone.utc)
    folder = ROOT/'data/research/runtime.private/baselines'/('availability-opponent-'+at.strftime('%Y%m%dT%H%M%SZ'))
    folder.mkdir(parents=True, exist_ok=False)
    archive = folder/'code-and-validation.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name in files:
            z.write(ROOT/name, name)
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError('baseline CRC failed')
    report = {
        'savedAt': at.isoformat(), 'directory': folder.relative_to(ROOT).as_posix(),
        'archiveSha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'codeAndEvidenceFiles': len(files), 'crcVerified': True,
        'acceptedCharacterDetails': details, 'acceptedGuildGearRolls': rolls,
        'acceptedCharacterInstances': progress,
        'guildSourceIds': [w['sourceId'] for w in wars],
        'immutableInputHashes': input_hashes,
        'dataCopyStrategy': 'Existing immutable captures/exports retained and hashed; unchanged native/image baseline retained.',
        'includesLiveDatabase': False, 'includesProcessMemory': False,
        'includesCredentials': False, 'networkRequests': 0, 'deployed': False,
    }
    (folder/'manifest.private.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    (ROOT/'reports/availability-opponent-success-baseline.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'baseline': report['directory'], 'files': len(files),
                      'immutableInputs': len(inputs), 'crcVerified': True}))


if __name__ == '__main__':
    main()
