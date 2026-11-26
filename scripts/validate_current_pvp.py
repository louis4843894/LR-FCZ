"""Verify accepted ranking/defense relations against saved normal responses.

Offline only. Reports contain counts, template IDs and source hashes, never
native account IDs, credentials or raw game responses.
"""
import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

from local_game_database import ROOT,DEFAULT_DB
from native_layouts import NEW_SHA
from parse_http_defense import parse_response
from import_defense_teams import normalize
from ranking_database import private_directory


def validate(database=DEFAULT_DB,*,integrity=False):
    db=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        db.execute('BEGIN')
        rankings=[json.loads(p) for p, in db.execute('SELECT r.payload FROM current_rankings c JOIN ranking_snapshots r USING(snapshot_id)')]
        def document(name):
            row=db.execute('SELECT d.payload FROM current_documents c JOIN documents d USING(sha256) WHERE c.filename=?',(name,)).fetchone()
            if not row:raise ValueError('accepted document missing')
            return json.loads(row[0])
        doc=document('defense-teams.private.json')
        gear_ids={r['itemCode'] for r in document('verified-equipment.json')['records']}
        character_ids={r['characterId'] for r in document('verified-characters.json')['records']}
        attempts={}
        for sid,uid,payload in db.execute('SELECT ranking_snapshot_id,player_id,payload FROM ranking_defense_attempts ORDER BY attempted_at'):
            attempts[(sid,uid)]=json.loads(payload)
        checks=dict(db.execute('SELECT s.private_directory,c.checked_at FROM pvp_http_checks c JOIN pvp_http_sources s USING(capture_id)'))
        ranking_checks=dict(db.execute('SELECT snapshot_id,max(checked_at) FROM pvp_ranking_checks GROUP BY snapshot_id'))
        db_integrity=db.execute('PRAGMA quick_check').fetchone()[0] if integrity else 'not_rechecked'
        foreign_keys=len(db.execute('PRAGMA foreign_key_check').fetchall()) if integrity else None
    finally:
        db.close()
    if db_integrity not in ('ok','not_rechecked') or foreign_keys not in (0,None):raise ValueError('database integrity check failed')
    teams={(t['playerId'],t['snapshotId']):t for t in doc['snapshots']}
    cohorts=[];all_players=set();all_instances=set();validated_copies=set()
    for ranking in rankings:
        if ranking['moduleSha256']!=NEW_SHA or ranking['status']!='success':raise ValueError('ranking module/status differs')
        sid=ranking['snapshotId'];players=ranking['players'];seen=set();state=Counter();enhancements=Counter()
        rows=[];retrieved=[];checked=[];source_hashes=[]
        if [p['rank'] for p in players]!=list(range(1,len(players)+1)):raise ValueError('ranking positions not contiguous')
        for player in players:
            uid=player['playerId']
            if uid in seen:raise ValueError('duplicate ranked player')
            seen.add(uid);all_players.add(uid)
            attempt=attempts.get((sid,uid))
            if not attempt:state['not_read']+=1;continue
            state[attempt['status']]+=1
            if attempt['status']=='failed':continue
            folder=private_directory(ROOT/attempt['captureDirectory'])
            raw=(folder/'response.private.json').read_bytes();sha=hashlib.sha256(raw).hexdigest()
            if sha!=attempt['captureSha256']:raise ValueError('accepted HTTP source hash differs')
            meta=json.loads(raw)
            if meta['result']['player']['uid']!=uid or meta['moduleSha256']!=NEW_SHA:raise ValueError('HTTP owner/module differs')
            expected=normalize(parse_response(folder),'0'*64)
            if set(attempt['defenseSnapshotIds'])!={t['snapshotId'] for t in expected['snapshots']}:raise ValueError('HTTP team relation differs')
            if not expected['snapshots'] and attempt['status']!='unavailable':raise ValueError('empty response misclassified')
            for target in expected['snapshots']:
                actual=teams.get((uid,target['snapshotId']))
                if not actual:raise ValueError('accepted defense observation missing')
                for field in ['purpose','teamId','isSelected','unobservedPositionIndices','members','retrievedAt']:
                    if target[field]!=actual[field]:raise ValueError('accepted defense field differs from saved response')
                rows.append(actual)
            retrieved.append(meta['capturedAt']);checked.append(checks.get(attempt['captureDirectory'],meta['capturedAt']))
            validated_copies.add(sha);source_hashes.append(sha)
        members=[m for t in rows for m in (t['members'] or [])]
        equipment=[g for m in members for g in m['equipment'].values()]
        equipped=[g for g in equipment if g['state']=='equipped']
        effects=[e for g in equipped for e in (g.get('actualEffects') or {}).get('entries',[])]
        for team in rows:
            for member in team['members'] or []:
                for gear in member['equipment'].values():
                    if gear['state']!='equipped':continue
                    identity=gear.get('equipmentInstanceIdentity')
                    if not identity:raise ValueError('equipped item instance missing')
                    all_instances.add((team['playerId'],identity['namespace'],identity['value']))
                    enhancements[gear['enhancement']]+=1
        cohorts.append({'scope':ranking['scope']['label'],'phaseCode':ranking['scope'].get('phaseCode'),
                        'rankingSnapshotId':sid,'rankingCapturedAt':ranking['capturedAt'],
                        'rankingCheckedAt':ranking_checks.get(sid,ranking['capturedAt']),
                        'sources':len(players),'states':dict(state),'teams':len(rows),'characters':len(members),
                        'slots':len(equipment),'equipment':len(equipped),
                        'empty':sum(g['state']=='not_equipped' for g in equipment),
                        'unknown':sum(g['state']=='unknown' for g in equipment),
                        'matched':sum(g['equipmentId'] in gear_ids for g in equipped),
                        'enhancements':dict(enhancements),'attributeEntries':len(effects),
                        'numericValues':sum(e.get('valueVerified') is True and e.get('value') is not None for e in effects),
                        'unknownCharacterIds':sorted({m['characterId'] for m in members if m['characterId'] and m['characterId'] not in character_ids}),
                        'unknownGearIds':sorted({g['equipmentId'] for g in equipped if g['equipmentId'] not in gear_ids}),
                        'defenseRetrievedRange':[min(retrieved),max(retrieved)] if retrieved else None,
                        'defenseCheckedRange':[min(checked),max(checked)] if checked else None,
                        'sourceSetSha256':hashlib.sha256(json.dumps(sorted(source_hashes)).encode()).hexdigest(),
                        'wholeTierCoverageConfirmed':False})
    order=['傳奇','大師','鑽石','黃金','白銀','青銅'];cohorts.sort(key=lambda c:order.index(c['scope']))
    report={'verifiedAt':datetime.now(timezone.utc).isoformat(),'gameVersion':'12.4.2','moduleSha256':NEW_SHA,
            'cohorts':cohorts,'uniquePlayers':len(all_players),'validatedHttpCopies':len(validated_copies),
            'uniqueOwnerScopedEquipmentInstances':len(all_instances),'savedHistoricalTeams':len(doc['snapshots']),
            'databaseIntegrity':db_integrity,'foreignKeyErrors':foreign_keys,
            'wholeGameCoverageConfirmed':False,'credentialsIncluded':False,'uiNavigation':False}
    (ROOT/'reports/pvp-current-source-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (ROOT/'reports/pvp-current-cohorts.json').write_text(json.dumps(cohorts,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--integrity',action='store_true');args=parser.parse_args()
    report=validate(integrity=args.integrity)
    print(json.dumps({'verified':True,'scopes':len(report['cohorts']),'players':report['uniquePlayers'],
                      'teams':sum(c['teams'] for c in report['cohorts']),
                      'equipped':sum(c['equipment'] for c in report['cohorts']),
                      'matched':sum(c['matched'] for c in report['cohorts']),
                      'databaseIntegrity':report['databaseIntegrity'],'foreignKeyErrors':report['foreignKeyErrors']}))
