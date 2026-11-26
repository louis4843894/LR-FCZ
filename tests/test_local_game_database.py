import json
import copy
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from local_game_database import FILES, ROOT, guild_update_due, sync_database,connect,require_selected_guild


class LocalDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.normalized = self.root/'data/normalized'
        self.normalized.mkdir(parents=True)
        self.db = self.root/'data/local/test.private.sqlite'

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, module, document):
        (self.normalized/FILES[module]).write_text(json.dumps(document), encoding='utf8')

    def test_fast_pvp_update_still_preserves_valid_instances_and_rejects_removal(self):
        from parse_http_defense import parse_response
        from import_defense_teams import normalize
        capture=ROOT/'data/research/runtime.private/pvp-http-20261125T105002Z-456e04'
        if not (capture/'response.private.json').exists():self.skipTest('saved normal response unavailable')
        doc=normalize(parse_response(capture),'a'*64);self.save('pvp',doc)
        result=sync_database(self.root,self.db,['pvp'],verify_integrity=False)
        self.assertEqual(result['defense_snapshots'],2);self.assertEqual(result['equipment_observations'],30)
        self.assertEqual(result['databaseIntegrity'],'not_rechecked')
        with closing(sqlite3.connect(self.db)) as db:
            before=db.execute('SELECT sha256 FROM current_documents').fetchone()[0]
            self.assertEqual(db.execute('SELECT count(*) FROM equipment_observations WHERE enhancement=5').fetchone()[0],30)
        doc['snapshots'].pop();self.save('pvp',doc)
        with self.assertRaisesRegex(ValueError,'discard'):sync_database(self.root,self.db,['pvp'],verify_integrity=False)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('SELECT sha256 FROM current_documents').fetchone()[0],before)
            self.assertEqual(db.execute('SELECT count(*) FROM equipment_observations').fetchone()[0],30)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def real_sources(self):
        if not all((ROOT/'data/normalized'/f).exists() for f in FILES.values()):
            self.skipTest('local captures unavailable')
        for module, filename in FILES.items():
            (self.normalized/filename).write_bytes((ROOT/'data/normalized'/filename).read_bytes())

    def test_real_gear_instances_and_values_survive_storage(self):
        self.real_sources()
        result=sync_database(self.root,self.db)
        self.assertEqual(result['equipment_templates'],953)
        source=json.loads((self.normalized/FILES['pvp']).read_text(encoding='utf8'))
        expected=sum(len(m['equipment']) for t in source['snapshots'] for m in t.get('members') or [])
        self.assertEqual(result['equipment_observations'],expected)
        self.assertEqual(result['databaseIntegrity'],'ok')
        with closing(sqlite3.connect(self.db)) as db:
            rows=[json.loads(r[0]) for r in db.execute('SELECT payload FROM equipment_observations')]
            entries=[e for r in rows for e in (r.get('actualEffects') or {}).get('entries',[])]
            self.assertGreaterEqual(sum(e.get('valueVerified') is True for e in entries),90)
            self.assertGreaterEqual(sum(e.get('valueVisuallyVerified') is True for e in entries),6)
            self.assertIn(444.0,[e.get('value') for e in entries])
            self.assertTrue(any(e.get('value') is None for e in entries))
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
            # Repeated template IDs stay different observations / equipment instances.
            repeated=db.execute('SELECT equipment_id,count(DISTINCT equipment_instance_id) FROM equipment_observations GROUP BY player_id,equipment_id HAVING count(DISTINCT equipment_instance_id)>1').fetchall()
            self.assertTrue(repeated)
            self.assertEqual(db.execute('SELECT count(*) FROM equipment_references WHERE source_kind=?',('external-user-confirmed',)).fetchone()[0],953)

    def test_reimport_is_idempotent_and_removal_of_success_is_rejected(self):
        self.real_sources()
        first=sync_database(self.root,self.db)
        self.assertEqual(sync_database(self.root,self.db),first)
        doc=json.loads((self.normalized/FILES['pvp']).read_text(encoding='utf8'))
        doc['snapshots']=doc['snapshots'][1:]
        self.save('pvp',doc)
        with self.assertRaisesRegex(ValueError,'discard'):
            sync_database(self.root,self.db,['pvp'])
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM defense_snapshots').fetchone()[0],first['defense_snapshots'])

    def test_partial_roster_cannot_advance_current_snapshot(self):
        self.real_sources()
        sync_database(self.root,self.db)
        with closing(sqlite3.connect(self.db)) as db:
            before=db.execute('SELECT sha256 FROM current_documents WHERE filename=?',(FILES['guild'],)).fetchone()
        roster=json.loads((self.normalized/FILES['guild']).read_text(encoding='utf8'))
        roster['membershipComplete']=False
        self.save('guild',roster)
        with self.assertRaisesRegex(ValueError,'incomplete'):
            sync_database(self.root,self.db,['guild'])
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('SELECT sha256 FROM current_documents WHERE filename=?',(FILES['guild'],)).fetchone(),before)

    def test_weekly_boundary_and_late_catchup(self):
        def due(captured,now):return guild_update_due(captured,datetime.fromisoformat(now))
        self.assertFalse(due('2026-11-24T11:59:58+08:00','2026-11-24T11:59:59+08:00'))
        self.assertTrue(due('2026-11-24T11:59:58+08:00','2026-11-24T12:00:00+08:00'))
        self.assertFalse(due('2026-11-24T12:00:00+08:00','2026-11-24T12:00:00+08:00'))
        self.assertTrue(due('2026-11-24T12:00:00+08:00','2026-12-01T12:00:00+08:00'))
        self.assertTrue(due('2026-11-23T12:00:00+08:00','2026-11-25T09:00:00+08:00'))

    def test_equal_instance_and_snapshot_names_are_scoped_to_owner(self):
        self.real_sources()
        doc=json.loads((self.normalized/FILES['pvp']).read_text(encoding='utf8'))
        row=copy.deepcopy(doc['snapshots'][0]);row['playerId']='isolated-fixture-owner'
        doc['snapshots'].append(row)
        self.save('pvp',doc)
        sync_database(self.root,self.db,['pvp'])
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM defense_snapshots WHERE snapshot_id=?',(row['snapshotId'],)).fetchone()[0],2)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_new_selected_guild_rejects_the_previous_guild_before_import(self):
        db=connect(self.db)
        with db:db.execute("INSERT INTO collection_targets VALUES ('guild','fixture-target','user','2026-11-25T00:00:00Z')")
        db.close()
        require_selected_guild('fixture-target',self.db)
        with self.assertRaisesRegex(ValueError,'user-selected'):
            require_selected_guild('fixture-previous',self.db)

    def test_character_stars_require_native_evidence_and_retain_history(self):
        doc={'schemaVersion':1,'sourceKind':'verified-character-template','recordCount':1,'records':[{'characterId':'isolated-test-ranger','recordScope':'character-template','starCount':None,'fieldStatus':{'starCount':'ui-relation-unconfirmed'}}]}
        self.save('characters',doc);sync_database(self.root,self.db,['characters'])
        row=doc['records'][0];row['starCount']=9
        self.save('characters',doc)
        with self.assertRaisesRegex(ValueError,'native UI evidence'):sync_database(self.root,self.db,['characters'])
        row['fieldStatus']['starCount']='verified-native-ui-relation'
        self.save('characters',doc);sync_database(self.root,self.db,['characters'])
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM documents WHERE module='characters'").fetchone()[0],2)
        for invalid in [True,10,0,9.0]:
            row['starCount']=invalid;self.save('characters',doc)
            with self.assertRaisesRegex(ValueError,'native UI evidence'):sync_database(self.root,self.db,['characters'])


if __name__=='__main__':unittest.main()
