"""Offline regression against actual, private, visible guild copies."""
import json,hashlib,shutil,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from parse_runtime_guild import parse_capture
from native_layouts import NEW_SHA,layout_for_sha
CAPTURE=ROOT/'data/research/runtime.private/guild-members-20261123T033922Z-6a83ec'

@unittest.skipUnless((CAPTURE/'capture.private.json').exists(),'requires actual local capture')
class GuildCaptureTests(unittest.TestCase):
    def test_all_visible_members_and_source_scope(self):
        d=parse_capture(CAPTURE)
        self.assertEqual((d['name'],d['level'],d['observedMemberTotal'],d['memberCapacity'],d['membersRetrieved']),('YXGC',8,41,50,41))
        self.assertTrue(d['membershipComplete']);self.assertEqual(len({r['playerId'] for r in d['members']}),41)
        self.assertTrue(all(r['defenseStatus']=='not_read' and r['level'] is None for r in d['members']))
    def mutated(self,callback):
        with tempfile.TemporaryDirectory(dir=CAPTURE.parent) as directory:
            p=Path(directory)
            for f in CAPTURE.iterdir():
                if f.is_file():shutil.copyfile(f,p/f.name)
            callback(p);return parse_capture(p)
    def test_modified_raw_copy_is_rejected(self):
        def change(p):
            f=p/'member-000.bin';b=bytearray(f.read_bytes());b[0x50]^=1;f.write_bytes(b)
        with self.assertRaisesRegex(ValueError,'hash/length mismatch'):self.mutated(change)
    def test_duplicate_member_identity_is_rejected(self):
        def change(p):
            b=(p/'member-000-id.bin').read_bytes();f=p/'member-001-id.bin';f.write_bytes(b)
            m=json.loads((p/'capture.private.json').read_text());m['files']['member-001-id'].update(sha256=hashlib.sha256(b).hexdigest(),length=len(b));(p/'capture.private.json').write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError,'duplicate member identity'):self.mutated(change)
    def test_duplicate_indices_do_not_claim_complete(self):
        def change(p):
            f=p/'capture.private.json';m=json.loads(f.read_text());m['members'][1]['index']=0;f.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError,'invalid member index'):self.mutated(change)
    def test_prohibited_word_manager_is_excluded_and_move_type_is_separate(self):
        layout=layout_for_sha(NEW_SHA)
        self.assertNotIn('guildGlobal',layout);self.assertEqual(layout['excludedProhibitedWordGlobal'],0x1fe9a50)
        self.assertEqual((layout['unitType'],layout['unitMoveType']),(0x430,0x448))
    def test_general_member_visit_remains_unread_defense(self):
        observation=ROOT/'data/research/runtime.private/guild-session-20261123/member-general-team-observation.private.json'
        d=parse_capture(CAPTURE,observation)
        self.assertEqual(d['members'][0]['defenseStatus'],'not_read')
        self.assertEqual(d['members'][0]['defenseFailureReason'],'only_general_team_visible')
        self.assertTrue(all('equipment' not in r for r in d['members']))
    def test_general_team_cannot_be_promoted_to_defense(self):
        observation=ROOT/'data/research/runtime.private/guild-session-20261123/member-general-team-observation.private.json'
        d=json.loads(observation.read_text(encoding='utf8'));d['purpose']='guild_battle_defense'
        with tempfile.TemporaryDirectory(dir=CAPTURE.parent) as folder:
            file=Path(folder)/'visit.private.json';file.write_text(json.dumps(d),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'unverified member visit'):parse_capture(CAPTURE,file)
