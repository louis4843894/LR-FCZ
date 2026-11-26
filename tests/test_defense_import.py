"""Isolated contract fixtures only; never import these into website data."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from import_defense_teams import normalize,import_file
class DefenseImportTests(unittest.TestCase):
    def test_import_cache_does_not_merge_equal_snapshot_names_across_players(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
            p=Path(folder);source=p/'source.json';output=p/'output.json';doc=self.observation()
            source.write_text(json.dumps(doc));import_file(source,output)
            doc['snapshots'][0]['playerId']='another-player';source.write_text(json.dumps(doc));result=import_file(source,output)
            self.assertEqual(result['counts']['successful'],2);self.assertEqual({s['playerId'] for s in result['snapshots']},{'test-player','another-player'})
    def test_actual_effect_identifiers_do_not_accept_unproven_values_or_private_fields(self):
        doc=self.observation();gear=doc['snapshots'][0]['members'][0]['equipment']['weapon']
        gear.update(actualEffects={'status':'identifiers_only','entries':[{'index':0,'attributeId':111,'valueGradeRaw':3,'attributeTypeRaw':2,'value':99999,'token':'private-fixture-sentinel'}]},fieldEvidence={'actualEffects':'isolated contract fixture; not captured data'},attributeReadState='captured')
        r=normalize(doc,'hash');text=json.dumps(r)
        self.assertNotIn('private-fixture-sentinel',text);self.assertNotIn('99999',text);self.assertFalse(r['snapshots'][0]['members'][0]['equipment']['weapon']['actualEffects']['numericalValuesVerified'])
    def test_partial_new_batch_preserves_prior_success_and_other_players(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
            p=Path(folder);source=p/'source.json';output=p/'output.json';doc=self.observation()
            source.write_text(json.dumps(doc));import_file(source,output)
            later=copy.deepcopy(doc);later['snapshots'][0].update(snapshotId='failed-later',status='failed',members=None,retrievedAt='2026-11-19T01:00:00+08:00')
            source.write_text(json.dumps(later));r=import_file(source,output)
            self.assertEqual(r['counts'],{'snapshots':2,'successful':1,'failedOrUnavailable':1})
            self.assertEqual(r['snapshots'][0]['members'][0]['characterId'],'fixture-unknown-template')
    def observation(self):
        return {'schemaVersion':1,'recordScope':'player-team-observations','sourceId':'fixture-only', 'snapshots':[
            {'snapshotId':'fixture-snapshot','teamId':'source-team-id','playerId':'test-player','purpose':'pvp_defense','status':'success','retrievedAt':'2026-11-19T00:00:00+08:00',
             'members':[{'memberIndex':0,'characterState':'present','characterId':'fixture-unknown-template',
                         'characterInstanceIdentity':{'value':'9007199254740993','sourceField':'invenId','namespace':'unknown'},
                         'equipment':{'weapon':{'state':'equipped','equipmentId':'fixture-unknown-equipment'},'armor':{'state':'not_equipped'},'accessory':{'state':'unknown'}}}]}]}
    def test_instance_id_precision_scope_and_unmatched_template_preserved(self):
        d=self.observation();d['snapshots'][0]['members'][0]['token']='must-not-export'
        result=normalize(d,'source-hash');member=result['snapshots'][0]['members'][0]
        self.assertEqual(member['characterInstanceIdentity']['value'],'9007199254740993')
        self.assertEqual(member['identityOwnerPlayerId'],'test-player')
        self.assertEqual(member['characterId'],'fixture-unknown-template')
        self.assertEqual(member['equipment']['weapon']['equipmentId'],'fixture-unknown-equipment')
        self.assertIsNone(member['equipment']['weapon']['actualEffects']);self.assertNotIn('must-not-export',json.dumps(result))
    def test_same_instance_value_for_different_players_is_not_global_collision(self):
        d=self.observation();r=copy.deepcopy(d['snapshots'][0]);r.update(snapshotId='another-snapshot',playerId='another-player');d['snapshots'].append(r)
        self.assertEqual(normalize(d,'hash')['counts']['successful'],2)
    def test_missing_actual_instance_or_team_id_is_rejected(self):
        d=self.observation();del d['snapshots'][0]['members'][0]['characterInstanceIdentity']
        with self.assertRaisesRegex(ValueError,'instance identity'):normalize(d,'hash')
        d=self.observation();del d['snapshots'][0]['teamId']
        with self.assertRaisesRegex(ValueError,'actual team identifier'):normalize(d,'hash')
    def test_failed_is_not_empty_and_guild_purpose_requires_membership(self):
        d=self.observation();r=d['snapshots'][0];r.update(status='failed',members=[])
        with self.assertRaisesRegex(ValueError,'must not contain members'):normalize(d,'hash')
        r['members']=None;self.assertIsNone(normalize(d,'hash')['snapshots'][0]['members'])
        d=self.observation();d['snapshots'][0]['purpose']='guild_battle_defense'
        with self.assertRaisesRegex(ValueError,'guild and membership'):normalize(d,'hash')
    def test_invalid_new_input_does_not_overwrite_previous_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as directory:
            p=Path(directory);source=p/'source.json';output=p/'output.json';output.write_text('prior-valid-version',encoding='utf8')
            source.write_text(json.dumps({'schemaVersion':1}),encoding='utf8')
            with self.assertRaises(ValueError):import_file(source,output)
            self.assertEqual(output.read_text(encoding='utf8'),'prior-valid-version')
