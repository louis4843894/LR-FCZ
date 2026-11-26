import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'scripts/runtime')]
from collect_ranked_pvp_http import main
from fetch_ranked_pvp_response import AcquisitionStopped

class PvpDenialStopTests(unittest.TestCase):
 def test_first_denial_is_preserved_and_no_second_request_is_issued(self):
  ranking={'snapshotId':'isolated-ranking','scope':{'label':'傳奇'},'players':[{'playerId':'fixture-a','rank':1},{'playerId':'fixture-b','rank':2}]}
  with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
   root=Path(folder);(root/'data/research/runtime.private').mkdir(parents=True)
   with patch('collect_ranked_pvp_http.ROOT',root),patch('collect_ranked_pvp_http.ranked_player',return_value=(ranking,ranking['players'][0])),patch('collect_ranked_pvp_http.recent',return_value={}),patch('collect_ranked_pvp_http.save_failure'),patch('collect_ranked_pvp_http.fetch',side_effect=AcquisitionStopped('http_access_denied')) as fetch:
    with self.assertRaisesRegex(AcquisitionStopped,'^http_access_denied$'):main(['--snapshot','isolated-ranking','--top','2','--use-authorized-runtime-session'],session=object())
    self.assertEqual(fetch.call_count,1)

if __name__=='__main__':unittest.main()
