"""Offline regressions using saved real responses. Never sends HTTP requests."""
import copy,hashlib,json,sqlite3,sys,tempfile,unittest
from unittest.mock import patch,MagicMock
from urllib.error import HTTPError
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'scripts/runtime'))
from parse_http_defense import parse_response,compare_native
from import_defense_teams import normalize,import_many
from http_ranking_database import connect,remember,recent,checked
from collect_ranked_pvp_http import acquisition_lock
from fetch_ranked_pvp_response import fetch,AcquisitionStopped
from pvp_session import RuntimeSession

CAPTURE=ROOT/'data/research/runtime.private/pvp-http-20261125T105002Z-456e04'
NATIVE=ROOT/'data/research/runtime.private/ranked-defense-20261125T091925Z-026748/observations.private.json'


class HttpTransportTests(unittest.TestCase):
    def test_duplicate_updater_is_rejected_and_lock_is_released(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fixture.lock'
            with acquisition_lock(path):
                with self.assertRaisesRegex(AcquisitionStopped,'already_running'):
                    with acquisition_lock(path):pass
            with acquisition_lock(path):pass

    def test_denial_is_not_retried_or_reported_with_credentials(self):
        session=RuntimeSession({'Cookie':'fixture-secret-never-send','uid':'fixture-uid'})
        self.assertNotIn('fixture-secret',repr(session))
        opener=MagicMock();opener.open.side_effect=HTTPError('https://fixture.invalid',403,'denied',{},None)
        with patch('fetch_ranked_pvp_response.urllib.request.build_opener',return_value=opener):
            with self.assertRaisesRegex(AcquisitionStopped,'^http_access_denied$'):fetch(session,{}, {'playerId':'fixture-uid'})
        self.assertEqual(opener.open.call_count,1)

    def test_sensitive_response_fields_cannot_be_saved(self):
        response=MagicMock();response.status=200;response.headers={}
        response.read.return_value=json.dumps({'result':{'player':{'uid':'fixture-uid'},'playerUnitTeamGroupMap':{'pvpteam':{'1':[{'password':'fixture-secret'}]}}}}).encode()
        opener=MagicMock();opener.open.return_value.__enter__.return_value=response
        with tempfile.TemporaryDirectory() as folder:
            with patch('fetch_ranked_pvp_response.urllib.request.build_opener',return_value=opener):
                with self.assertRaisesRegex(AcquisitionStopped,'sensitive_response_field'):
                    fetch(RuntimeSession({}),{}, {'playerId':'fixture-uid'},Path(folder))
            self.assertEqual(list(Path(folder).iterdir()),[])


@unittest.skipUnless((CAPTURE/'response.private.json').exists(),'requires saved actual HTTP source')
class HttpDefenseTests(unittest.TestCase):
    def test_actual_response_matches_native_instances_slots_enhancement_and_attributes(self):
        doc=parse_response(CAPTURE)
        self.assertEqual(compare_native(doc,json.loads(NATIVE.read_text(encoding='utf8'))),
                         {'teams':2,'characters':10,'equipped':30,'emptySlots':0,'attributes':119})
        result=normalize(doc,'a'*64)
        gear=[g for t in result['snapshots'] for m in t['members'] for g in m['equipment'].values()]
        self.assertTrue(all(g['enhancement']==5 for g in gear))
        self.assertGreater(len({g['equipmentInstanceIdentity']['value'] for g in gear}),10)
        for g in gear:
            for entry in (g.get('actualEffects') or {}).get('entries',[]):
                self.assertIsNone(entry['attributeTypeRaw']);self.assertIsNone(entry['value']);self.assertFalse(entry['valueVerified'])
        self.assertTrue(all(t['verification'] is None for t in result['snapshots']))

    def modified(self,change):
        data=json.loads((CAPTURE/'response.private.json').read_bytes());change(data)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);(path/'response.private.json').write_text(json.dumps(data),encoding='utf8')
            return parse_response(path)

    def test_owner_and_duplicate_positions_cannot_be_accepted(self):
        def wrong_owner(data):data['result']['playerUnitTeamGroupMap']['pvpteam']['1'][0]['equipMap']['WEAPON']['unitInvenId']+=1
        with self.assertRaisesRegex(ValueError,'owner differs'):self.modified(wrong_owner)
        def duplicate(data):data['result']['playerUnitTeamGroupMap']['pvpteam']['1'][1]['slot']=0
        with self.assertRaisesRegex(ValueError,'placement'):self.modified(duplicate)

    def test_owner_verified_empty_response_is_unavailable_without_invented_empty_team(self):
        def absent(data):data['result']['playerUnitTeamGroupMap']['pvpteam']={}
        result=self.modified(absent)
        self.assertEqual(result['snapshots'],[])
        self.assertEqual(result['captureEvidence']['teamReadState'],'not_returned')

    def test_missing_enhancement_is_not_max_enchant_and_unknown_map_is_not_empty(self):
        def missing(data):del data['result']['playerUnitTeamGroupMap']['pvpteam']['1'][0]['equipMap']['WEAPON']['currentEnchant']
        with self.assertRaises(KeyError):self.modified(missing)
        def unknown(data):del data['result']['playerUnitTeamGroupMap']['pvpteam']['1'][0]['equipMap']
        result=self.modified(unknown)
        self.assertTrue(all(g['state']=='unknown' for g in result['snapshots'][0]['members'][0]['equipment'].values()))
        def empty(data):data['result']['playerUnitTeamGroupMap']['pvpteam']['1'][0]['equipMap']={}
        result=self.modified(empty)
        self.assertTrue(all(g['state']=='not_equipped' for g in result['snapshots'][0]['members'][0]['equipment'].values()))

    def test_batch_merge_preserves_other_versions_and_counts_all_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);doc=parse_response(CAPTURE);a=path/'a.json';a.write_text(json.dumps(doc),encoding='utf8')
            other=copy.deepcopy(doc);other['sourceId']='fixture-second-source'
            for team in other['snapshots']:team['snapshotId']='fixture-'+team['snapshotId']
            b=path/'b.json';b.write_text(json.dumps(other),encoding='utf8');out=path/'normalized.json'
            self.assertEqual(import_many([a,b],out)['counts']['snapshots'],4)
            self.assertEqual(import_many([a],out)['counts']['snapshots'],4)

    def test_failed_attempt_invalidates_fresh_cache_until_real_unchanged_check(self):
        meta=json.loads((CAPTURE/'response.private.json').read_bytes());sid=meta['rankingSnapshotId'];uid=meta['result']['player']['uid']
        with sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True) as live:
            source=live.execute('SELECT * FROM ranking_snapshots WHERE snapshot_id=?',(sid,)).fetchone()
        with tempfile.TemporaryDirectory() as folder:
            database=Path(folder)/'fixture.sqlite';db=connect(database)
            with db:db.execute('INSERT INTO ranking_snapshots VALUES (?,?,?,?,?,?)',source)
            db.close();remember(CAPTURE,database)
            self.assertIn(uid,recent(sid,None,database))
            sha=hashlib.sha256((CAPTURE/'response.private.json').read_bytes()).hexdigest()
            before=datetime.now(timezone.utc)-timedelta(seconds=20)
            success={'status':'success','attemptedAt':before.isoformat(),'defenseSnapshotIds':['fixture-team'],
                     'captureSha256':sha,'cacheState':'normal-native-http-response'}
            failed={'status':'failed','attemptedAt':(before+timedelta(seconds=10)).isoformat(),'defenseSnapshotIds':[]}
            db=connect(database)
            with db:
                for key,payload in [('fixture-success',success),('fixture-failure',failed)]:
                    db.execute('INSERT INTO ranking_defense_attempts VALUES (?,?,?,?,?,?)',(key,sid,uid,payload['attemptedAt'],payload['status'],json.dumps(payload)))
            db.close()
            self.assertNotIn(uid,recent(sid,None,database))
            checked(CAPTURE,datetime.now(timezone.utc).isoformat(),database)
            self.assertIn(uid,recent(sid,None,database))
            db=connect(database)
            self.assertEqual(db.execute('SELECT status FROM ranking_defense_attempts ORDER BY attempted_at DESC LIMIT 1').fetchone()[0],'success');db.close()


if __name__=='__main__':unittest.main()
