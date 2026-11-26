"""Consolidate saved evidence about Top 100 defense acquisition, offline only.

This report distinguishes confirmed tower defenses, attack teams, contribution
statistics and unestablished readers. It does not call or invent game APIs.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    names = [
        'guild-top100-defense-coverage.json', 'guildwar-reader-callers.json',
        'guild-defense-literal-readers.json', 'guild-defense-model-readers.json',
        'guild-profile-battle-phase-check.json', 'guild-ranking-battle-phase-check.json',
        'guild-history-battle-phase-check.json', 'guild-contribution-battle-phase-check.json',
        'public-guildwar-reference-shape.json',
        'ghidra/guild-target-transport-and-replay-model-1242.txt',
        'ghidra/guild-context-helpers-and-replay-caller-1242.txt',
    ]
    evidence = []
    for name in names:
        path = ROOT / 'reports' / name
        blob = path.read_bytes()
        evidence.append({'file': path.relative_to(ROOT).as_posix(),
                         'sha256': hashlib.sha256(blob).hexdigest()})
    calls = json.loads((ROOT / 'reports/guildwar-reader-callers.json').read_bytes())
    coverage = json.loads((ROOT / 'reports/guild-top100-defense-coverage.json').read_bytes())
    # These expected callers were checked against decompilation and ELF unwind
    # boundaries; a new binary or a new caller requires another review.
    tower_targets = {'0x133bc78', '0x133c388', '0x133c590'}
    callers = {r['functionStart'] for r in calls['references'] if r['target'] in tower_targets}
    if callers != {'0x132a808'}:
        raise ValueError('tower reader callers changed; conclusions require review')
    return {
        'checkedAt': datetime.now(timezone.utc).isoformat(),
        'target': 'Real deployed guild-war defenses of ranked guilds #1 through #100',
        'moduleSha256': calls['moduleSha256'], 'coverage': coverage['summary'],
        'confirmedReadChain': {
            'controller': '0132a808',
            'readers': {'registration': '0133bc78', 'ally': '0133c388', 'opponent': '0133c590'},
            'callback': '0133bd38', 'responseArray': 'guildWarDefenceDeckResponses',
            'modelType': '19GuildWarMemberModel', 'modelParser': '013486b4',
            'serializedTeamField': 'deckInfoJson',
            'towerArguments': ['seasonNo', 'battleNo', 'towerCode'],
            'arbitraryGuildIdArgumentEstablished': False,
        },
        'otherReaders': [
            {'entry': '0133c678', 'purpose': 'current account saved defense',
             'callback': '0133c6c8', 'arbitraryGuildIdArgumentEstablished': False},
            {'entry': '013411ec', 'caller': '0132adb8', 'purpose': 'selected defender replay list',
             'requiredInputs': ['current war context', 'defUid', 'defGid', 'deckId', 'seasonNo', 'matchNo'],
             'returns': ['win', 'replayKey', 'attackerName', 'attackerLevel'],
             'top100DefenseReaderEstablished': False, 'requestExecuted': False},
        ],
        'transportFinding': {
            'getWrapper': '0105a004', 'baseUrlBuilder': '01058760',
            'headerBuilder': '01058da8', 'requestDispatcher': '01a4be64',
            'guildSelectorHeaderEstablished': False,
            'credentialValuesInspectedByThisAudit': False,
        },
        'normalResponseFindings': {
            'profileAndRoster': {'ranks': [1, 5], 'requests': 4, 'defenseFound': False},
            'ranking': {'requests': 1, 'defenseFound': False},
            'history': {'requests': 2, 'types': ['GUILD_HIST_JOIN_RAID', 'GUILD_HIST_ATTENDANCE'], 'defenseFound': False},
            'contribution': {'rank': 1, 'requests': 1, 'memberRows': 50,
                             'fields': ['name', 'imageUrl', 'level', 'selfYn', 'winCount', 'bonusPoint'],
                             'defenseFound': False,
                             'note': 'A guildWar-prefixed key is not evidence of defense data.'},
        },
        'publicReference': {
            'repository': 'https://github.com/mti0224/rangerbook',
            'reviewedFiles': ['assets/js/guildwar-ranking.js', 'guildwar/index.html',
                              'tests/v2-pvp-guild-browser.cjs', 'scripts/check-public-boundary.mjs'],
            'declaredPurpose': 'guild war attack teams', 'importedAsDefense': 0,
            'collectorBackendPublished': False, 'adminModeEnabled': False,
            'protectedApiCalled': False,
        },
        'remainingGap': 'A verified normal reader selecting an arbitrary ranked guild and returning its deployed defense.',
        'scopeLimit': 'Exact known literals and readers in this module; indirect/other response formats and server-only routes are not proven absent.',
        'evidence': evidence, 'networkRequestsByThisAudit': 0,
        'priorPlayerTeam403PausePreserved': True,
        'top100Complete': False,
    }


if __name__ == '__main__':
    report = build()
    (ROOT / 'reports/guild-top100-defense-entrypoint-audit.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'coverage': report['coverage'], 'top100Complete': False,
                      'networkRequests': 0, 'evidenceFiles': len(report['evidence'])}))
