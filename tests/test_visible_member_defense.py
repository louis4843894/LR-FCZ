"""Contract fixtures for source attribution only; never game observations."""
import copy,hashlib,json,struct,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from parse_runtime_defense import validate_member_context

class VisibleMemberContextTests(unittest.TestCase):
    def fixture(self,path,mode=5,roster_id=b'fixture-player'):
        base=0x10000000;profile_address=0x20000000;scene=bytearray(0x170);profile=bytearray(0x220);guild=bytearray(0x40)
        struct.pack_into('<Q',scene,0,base+0x1eee558-0x100000);struct.pack_into('<Q',profile,0,base+0x1e7d650-0x100000);struct.pack_into('<Q',guild,0,base+0x1eadb48-0x100000)
        struct.pack_into('<Q',scene,0x138,profile_address);struct.pack_into('<I',scene,0x168,mode);struct.pack_into('<I',scene,0x148,1);struct.pack_into('<I',profile,0x160,1)
        uid=b'fixture-player';profile[0x90]=len(uid)<<1;profile[0x91:0x91+len(uid)]=uid
        name=b'Fixture';profile[0x48]=len(name)<<1;profile[0x49:0x49+len(name)]=name
        blobs={'controller':scene,'profile':profile,'profile-id':uid,'profile-name':name,'roster-member-id':roster_id,'guild':guild,'guild-id':b'fixture-guild','roster-guild-id':b'fixture-guild'};files={}
        for name,blob in blobs.items():
            file=name+'.bin';(path/file).write_bytes(blob);files[name]={'file':file,'sha256':hashlib.sha256(blob).hexdigest()}
        return {'moduleBase':base,'ownerContextVerified':True,'playerId':uid.decode(),'usePvPTeamNo':1,'sourceContext':{'kind':'visible-guild-member','profileAddress':profile_address,'guildId':'fixture-guild','files':files}}
    def test_member_uid_is_verified_against_source_and_roster(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);m=self.fixture(p);self.assertEqual(validate_member_context(p,m)['guildId'],'fixture-guild')
    def test_general_team_mode_is_not_accepted_as_defense(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);m=self.fixture(p,mode=0)
            with self.assertRaisesRegex(ValueError,'not PVP defense'):validate_member_context(p,m)
    def test_another_player_cannot_borrow_own_or_members_team(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);m=self.fixture(p,roster_id=b'other-player')
            with self.assertRaisesRegex(ValueError,'identity mismatch'):validate_member_context(p,m)
    def test_modified_context_and_selected_team_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);m=self.fixture(p);m['usePvPTeamNo']=2
            with self.assertRaisesRegex(ValueError,'differs from display'):validate_member_context(p,m)
            m['usePvPTeamNo']=1;(p/'profile-id.bin').write_bytes(b'corrupted')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):validate_member_context(p,m)
    def test_unrelated_visible_player_is_accepted_without_claiming_saved_membership(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);m=self.fixture(p);c=m['sourceContext'];c['kind']='visible-player'
            for key in ['roster-member-id','roster-guild-id']:c['files'].pop(key)
            self.assertEqual(validate_member_context(p,m)['kind'],'visible-player')
            c['rosterCapturedAt']='2026-11-23T00:00:00Z'
            with self.assertRaisesRegex(ValueError,'cannot claim saved roster'):validate_member_context(p,m)
