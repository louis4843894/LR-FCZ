import json,sys,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts/runtime'));sys.path.insert(0,str(ROOT/'scripts'))
from fetch_ranked_pvp_response import normal_json,AcquisitionStopped
from pvp_session import RuntimeSession
from collect_guildwar_http import tower_paths,historical_request
from native_layouts import NEW_SHA


class GuildReadTransportTests(unittest.TestCase):
    def test_history_request_requires_a_saved_same_guild_same_season_context(self):
        current={'myGuildInfo':{'gid':'fixture-guild'},'currentSeason':{'seasonNo':454,'status':'second_standby'}}
        prior={'moduleSha256':NEW_SHA,'sourceKind':'normal-visible-guildwar-main','result':{'myGuildInfo':{'gid':'fixture-guild'},'currentSeason':{'seasonNo':454,'status':'first_battle'}}}
        self.assertEqual(historical_request(prior,current)[0],'/guildwar/main?status=first_battle&seasonNo=454')
        current['myGuildInfo']['gid']='fixture-other-guild'
        with self.assertRaisesRegex(AcquisitionStopped,'not_this_guild'):historical_request(prior,current)
    def test_tower_parameters_are_bound_to_current_season_and_returned_codes(self):
        main={'currentSeason':{'seasonNo':454,'status':'second_standby'},'fortressCount':{'16':[0,0],'31':[0,0,0,0]}}
        self.assertEqual(tower_paths(main,'ally'),[(16,'/guildwar/fortress/ally/454/2/16'),(31,'/guildwar/fortress/ally/454/2/31')])
        main['currentSeason']['status']='register'
        with self.assertRaisesRegex(AcquisitionStopped,'not_in_verified_battle'):tower_paths(main,'ally')
    def test_guild_paths_require_explicit_purpose_and_save_paths_are_never_allowed(self):
        for path,purpose in [('/guildwar/main','pvp'),('/guildwar/defencedeck','pvp'),('/player/units/save/guildwar','guild-war-bootstrap'),('/guildwar/form/register','guild-war-bootstrap'),('/guildwar/rank/total?gradeId=8','guild-ranking')]:
            with self.assertRaisesRegex(AcquisitionStopped,'unverified_normal_path'):normal_json(RuntimeSession({}),path,purpose=purpose)

    def test_bootstrap_is_get_without_body_or_existing_browser_credentials(self):
        response=MagicMock();response.status=200;response.headers={};response.read.return_value=b'{"result":{}}'
        opener=MagicMock();opener.open.return_value.__enter__.return_value=response
        with patch('fetch_ranked_pvp_response.urllib.request.build_opener',return_value=opener):
            normal_json(RuntimeSession({}),'/guildwar/defencedeck',purpose='guild-war-bootstrap')
        request=opener.open.call_args.args[0]
        self.assertEqual(request.get_method(),'GET');self.assertIsNone(request.data)

    def test_member_group_probe_cannot_switch_to_guessed_defense_or_guild_modes(self):
        for path in ['/player/units/team/defense/uid/fixture','/player/units/team/guildwar/uid/fixture','/guildwar/defencedeck?uid=fixture','/guildwar/fortress/other/454/2/11']:
            with self.assertRaisesRegex(AcquisitionStopped,'unverified_normal_path'):normal_json(RuntimeSession({}),path,purpose='guild-war-member-groups')


if __name__=='__main__':unittest.main()
