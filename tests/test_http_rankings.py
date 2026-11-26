"""Real saved league responses; no device/session/network activity."""
import copy,hashlib,json,sqlite3,sys,tempfile,unittest
from contextlib import closing
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'scripts/runtime'))
from refresh_pvp_rankings_http import parse_source,native_integer,accept
from http_ranking_database import connect,recent,remember,save_batch,checked
from ranking_database import save_failure,latest_attempts
from parse_http_defense import parse_response
from pvp_league_codes import verified_mappings

CAPTURE=ROOT/'data/research/runtime.private/pvp-ranking-http-20261125T115856Z-6e5594'
DEFENSE=ROOT/'data/research/runtime.private/pvp-http-20261125T105002Z-456e04'


class NativeRankingNumberTests(unittest.TestCase):
    def test_only_gold_and_above_with_each_native_subdivision_are_requested(self):
        mapping={m['label']:m for m in verified_mappings()}
        self.assertEqual(set(mapping),{'傳奇',*[g+str(i) for g in ['大師','鑽石','黃金'] for i in (1,2,3)]})
        for label in ['大師1','大師2','大師3','鑽石1','鑽石2','鑽石3','黃金1','黃金2','黃金3']:
            self.assertEqual(mapping[label]['method'],'native-14-phase-array-and-local-translation')
            self.assertEqual(mapping[label]['minimumPlayers'],1)
            self.assertFalse(mapping[label]['wholeTierCoverageConfirmed'])

    def test_matches_proven_integral_predicate_without_truncating_bad_numbers(self):
        self.assertEqual(native_integer(199.0),199)
        self.assertEqual(native_integer(1988),1988)
        for value in [True,199.5,float('nan'),float('inf'),0x80000000,'199']:
            with self.assertRaises(ValueError):native_integer(value)


@unittest.skipUnless((CAPTURE/'ranking-response.private.json').exists(),'requires real saved normal ranking response')
class HttpRankingsTests(unittest.TestCase):
    def test_actual_phase_rows_and_coverage(self):
        doc=parse_source(CAPTURE)
        self.assertEqual(doc['status'],'success');self.assertEqual(doc['failedRowCount'],0)
        self.assertEqual(len(doc['players']),200)
        self.assertEqual({p['rank'] for p in doc['players']},set(range(1,201)))
        self.assertEqual(doc['scope']['phaseCode'],'LEGEND');self.assertFalse(doc['scope']['wholeRankingComplete'])
        self.assertTrue(all(type(p['score']) is int for p in doc['players']))

    def test_partial_duplicate_source_never_replaces_complete_and_is_not_same_identity(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
            path=Path(folder);database=path/'fixture.sqlite'
            complete=accept(CAPTURE,database)
            raw=json.loads((CAPTURE/'ranking-response.private.json').read_bytes())
            raw['result']['league']['rankingList'].append(copy.deepcopy(raw['result']['league']['rankingList'][0]))
            partial_dir=path/'partial';partial_dir.mkdir();(partial_dir/'ranking-response.private.json').write_text(json.dumps(raw),encoding='utf8')
            partial=accept(partial_dir,database)
            self.assertEqual(partial['status'],'partial');self.assertNotEqual(complete['snapshotId'],partial['snapshotId'])
            with closing(sqlite3.connect(database)) as db:self.assertEqual(db.execute('SELECT snapshot_id FROM current_rankings').fetchone()[0],complete['snapshotId'])

    def test_staging_complete_source_keeps_previous_current_pointer(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
            path=Path(folder);database=path/'fixture.sqlite';current=accept(CAPTURE,database)
            data=json.loads((CAPTURE/'ranking-response.private.json').read_bytes())
            data['result']['league']['rankingList'][0]['score']+=1
            staged=path/'staged';staged.mkdir();(staged/'ranking-response.private.json').write_text(json.dumps(data),encoding='utf8')
            next_source=accept(staged,database,activate=False)
            self.assertNotEqual(current['snapshotId'],next_source['snapshotId'])
            with closing(sqlite3.connect(database)) as db:
                self.assertEqual(db.execute('SELECT snapshot_id FROM current_rankings').fetchone()[0],current['snapshotId'])
                self.assertEqual(db.execute('SELECT count(*) FROM ranking_snapshots').fetchone()[0],2)

    def test_accepted_copy_links_new_ranking_without_reparse_and_cannot_hide_newer_failure(self):
        meta=json.loads((DEFENSE/'response.private.json').read_bytes());origin=meta['rankingSnapshotId'];uid=meta['result']['player']['uid']
        sha=hashlib.sha256((DEFENSE/'response.private.json').read_bytes()).hexdigest()
        with closing(sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)) as live:
            original=live.execute('SELECT * FROM ranking_snapshots WHERE snapshot_id=?',(origin,)).fetchone()
        with tempfile.TemporaryDirectory() as folder:
            database=Path(folder)/'fixture.sqlite';db=connect(database)
            with db:db.execute('INSERT INTO ranking_snapshots VALUES (?,?,?,?,?,?)',original)
            db.close();remember(DEFENSE,database);target=accept(CAPTURE,database,activate=False)
            doc=parse_response(DEFENSE);ids=[t['snapshotId'] for t in doc['snapshots']]
            prior={'status':'success','attemptedAt':meta['capturedAt'],'defenseRetrievedAt':meta['capturedAt'],
                   'defenseSnapshotIds':ids,'sourceRankingSnapshotId':origin,'cacheState':'normal-native-http-response',
                   'captureDirectory':DEFENSE.relative_to(ROOT).as_posix(),'captureSha256':sha,'selectedTeamId':'1'}
            db=connect(database)
            with db:
                db.execute('INSERT INTO documents VALUES (?,?,?,?,?)',('fixture-doc','pvp','defense-teams.private.json',meta['capturedAt'],'{}'))
                db.execute('INSERT INTO current_documents VALUES (?,?)',('defense-teams.private.json','fixture-doc'))
                for team in doc['snapshots']:
                    db.execute('INSERT INTO defense_snapshots VALUES (?,?,?,?,?,?,?,?)',('fixture-doc',team['snapshotId'],uid,'pvp_defense',team['teamId'],meta['capturedAt'],'success',json.dumps(team)))
                db.execute('INSERT INTO ranking_defense_attempts VALUES (?,?,?,?,?,?)',('fixture-prior',origin,uid,meta['capturedAt'],'success',json.dumps(prior)))
            db.close()
            with patch('http_ranking_database.parse_response',side_effect=AssertionError('accepted copy must not reparse')),patch('http_ranking_database.import_many',side_effect=AssertionError('accepted copy must not rewrite')):
                result=save_batch(target['snapshotId'],[DEFENSE],database)
                self.assertEqual(result,{'acceptedPlayers':1,'acceptedCopiesReused':1,'newSourceImports':0,'normalizedWrites':0})
                self.assertEqual(latest_attempts(target['snapshotId'],database)[uid]['sourceRankingSnapshotId'],origin)
                save_failure(target['snapshotId'],uid,'fixture_failure',database)
                failed=latest_attempts(target['snapshotId'],database)[uid]
                self.assertNotIn(uid,recent(origin,None,database))
                self.assertIn(uid,recent(origin,None,database,for_comparison=True))
                with self.assertRaisesRegex(ValueError,'newer successful source check'):save_batch(target['snapshotId'],[DEFENSE],database)
                self.assertEqual(latest_attempts(target['snapshotId'],database)[uid]['status'],'failed')
                checked(DEFENSE,(datetime.fromisoformat(failed['attemptedAt'])+timedelta(seconds=1)).isoformat(),database)
                with patch('http_ranking_database.stamp',return_value=(datetime.fromisoformat(failed['attemptedAt'])+timedelta(seconds=2)).isoformat()):
                    self.assertEqual(save_batch(target['snapshotId'],[DEFENSE],database)['normalizedWrites'],0)
                self.assertEqual(latest_attempts(target['snapshotId'],database)[uid]['status'],'success')

    def test_owner_scoped_defense_cache_survives_new_rank_snapshot(self):
        meta=json.loads((DEFENSE/'response.private.json').read_bytes());origin=meta['rankingSnapshotId'];uid=meta['result']['player']['uid']
        with closing(sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)) as live:
            old=live.execute('SELECT * FROM ranking_snapshots WHERE snapshot_id=?',(origin,)).fetchone()
        with tempfile.TemporaryDirectory() as folder:
            database=Path(folder)/'fixture.sqlite';db=connect(database)
            with db:db.execute('INSERT INTO ranking_snapshots VALUES (?,?,?,?,?,?)',old)
            db.close();remember(DEFENSE,database);new=accept(CAPTURE,database)
            self.assertIn(uid,{p['playerId'] for p in new['players']})
            self.assertEqual(recent(new['snapshotId'],None,database)[uid],DEFENSE.resolve())


if __name__=='__main__':unittest.main()
