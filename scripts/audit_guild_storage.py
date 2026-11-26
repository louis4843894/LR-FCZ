"""Reconcile the guild-wide storage survey from saved evidence, offline only."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT/'reports'/name).read_bytes())


def build():
    classes = read('guild-class-storage-inventory.json')
    routes = read('guild-all-route-index.json')
    runtime = read('guild-runtime-storage-caches.json')
    template = read('guild-template-storage-root-check.json')
    coverage = read('guild-top100-defense-coverage.json')
    sources = ['guild-class-storage-inventory.json', 'guild-all-route-index.json',
               'guild-runtime-storage-caches.json', 'guild-template-storage-root-check.json',
               'guild-battle-storage-root-check.json', 'guild-local-http-cache-check.json',
               'guild-existing-eson-format-check.json', 'guild-confirm-entry-references.json',
               'public-guildwar-reference-complete-schema.json',
               'guild-normal-embedded-schema-check.json',
               'guild-profile-to-war-context-check.json', 'guild-public-admin-code-check.json',
               'loading-unit-native-consumer-check.json',
               'guild-top100-defense-coverage.json',
               'ghidra/guild-complete-storage-roots-1242.txt',
               'ghidra/guild-whole-readers-and-cache-writers-1242.txt',
               'ghidra/guild-profile-search-confirm-semantics-1242.txt',
               'ghidra/guild-db-storage-writer-proof-1242.txt',
               'ghidra/guild-confirm-response-and-callers-1242.txt',
               'ghidra/guild-confirm-normal-ui-callers-1242.txt',
               'ghidra/loading-unit-storage-consumer-1242.txt']
    evidence = []
    functions = set()
    for source in sources:
        path = ROOT/'reports'/source
        raw = path.read_bytes()
        evidence.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(raw).hexdigest()})
        if source.endswith('.txt'):
            functions.update(re.findall(r'^FUNCTION ([0-9a-f]{8})$', raw.decode('utf8'), re.M))
    for field in ('0x78', '0x80'):
        cache = runtime['fields'][field]
        if cache['count'] != 10 or any(
            child['value']['type'] != 'N7cocos2d7CCArrayE' or
            any(value['type'] != 'N7cocos2d9CCIntegerE' for value in child['value']['children'])
            for child in cache['children']):
            raise ValueError('war cache shape differs; conclusions require review')
    return {
        'checkedAt': datetime.now(timezone.utc).isoformat(), 'moduleSha256': classes['moduleSha256'],
        'inventory': {'guildRttiClasses': len(classes['classes']), 'completeRouteLiterals': len(routes['routes']),
                      'routeReferences': sum(len(r['references']) for r in routes['routes']),
                      'targetedFunctionsDecompiledThisStorageSurvey': len(functions),
                      'allClassMethodsDecompiled': False, 'allServerEndpointsEnumerated': False},
        'confirmedDefenseRepresentation': {
            'normalResponseArray': 'guildWarDefenceDeckResponses',
            'serializedTeamField': 'deckInfoJson', 'snapshotIdentifier': 'deckId',
            'nativeModel': '19GuildWarMemberModel', 'parser': '013486b4',
            'knownAcquisitionContexts': ['own saved defense', 'own registered towers', 'normal visible matched opponent towers'],
            'serverDatabaseTableNameKnown': False,
        },
        'runtimeStorage': {
            'guildWarRoot': 'global0200a320 / AP01eb5c00',
            '0x18': 'current own GuildWarInfoModel', '0x20': 'current opponent GuildWarInfoModel',
            '0x28': 'GuildWarSeasonModel', '0x50': {'type': 'GuildWarReplayModel array', 'count': runtime['fields']['0x50']['count']},
            '0x78': {'sourceKey': 'fortressCount', 'kind': '10 tower keys -> arrays of CCInteger'},
            '0x80': {'sourceKey': 'enemyFortressCount', 'kind': '10 tower keys -> arrays of CCInteger'},
            'countParser': '0133fd94', 'defenseObjectsFoundInCountCaches': 0,
        },
        'guildDbStorage': {
            'root': 'global01fd7588 / AP01e4b938', 'retainedFieldsObserved': len(template['fields']),
            'sampleLimitPerContainer': 3,
            '0x30': {'provenSourceTable': 'guild_raid_stage_ai', 'class': '13GuildRaidAiDB',
                     'parseMethod': '00f46f08', 'getter': '00f4a598'},
            '0x40': {'provenSourceTable': 'guild_war_fortress', 'class': '18GuildWarFortressDB',
                     'parseMethod': '00f48ed0', 'getter': '00f4a638'},
            'playerDefenseEstablishedInThisRoot': False,
        },
        'otherFindings': {
            'guildRankingParser': '012a2814: 12 identity/rank/guild metadata fields, no unit/equipment fields',
            'guildProfileParser': '012e7e6c: guild metadata/member/guardian models, no defense team parser established',
            'confirm': {'entry': '01255908', 'method': 'POST via 01058198', 'callback': '01255bcc',
                        'observedResponseUse': 'numeric status passed to delegate; no defense parser',
                        'callers': ['01273f5c', '012756fc'], 'requestExecuted': False,
                        'uiContext': 'Same handler branches call guild admission and admission cancellation; no fortress selection or team response parsing.',
                        'postAloneDoesNotEstablishMutation': True},
            'defenseUiKeys': '01359730 -> 0132a950 -> 0133b66c: in-memory save notification, not a local defense file reader',
            'battleStorage': read('guild-battle-storage-root-check.json'),
            'localHttpCache': read('guild-local-http-cache-check.json'),
            'esonAssets': read('guild-existing-eson-format-check.json'),
            'publicLegendExportSchema': read('public-guildwar-reference-complete-schema.json'),
            'normalGuildEmbeddedSchema': read('guild-normal-embedded-schema-check.json'),
            'profileToWarContext': read('guild-profile-to-war-context-check.json'),
            'publicAdminSource': read('guild-public-admin-code-check.json'),
            'loadingUnitExpectedConsumer': read('loading-unit-native-consumer-check.json'),
        },
        'currentTop100DefenseCoverage': coverage['summary'],
        'remainingGaps': [
            'Verified normal acquisition selecting an arbitrary ranked guild is not established.',
            'Four current-opponent towers remain locked in the last verified normal view.',
            'The 7424-byte resource copy has unverified format and no established guild-defense link.',
        ],
        'evidence': evidence, 'networkRequestsByAudit': 0,
        'credentialsPersisted': False, 'wholeProcessDumpCreated': False,
        'priorPlayerTeam403PausePreserved': True,
    }


if __name__ == '__main__':
    report = build()
    (ROOT/'reports/guild-all-storage-review.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'inventory': report['inventory'], 'coverage': report['currentTop100DefenseCoverage'],
                      'networkRequests': 0}))
