import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/runtime'))
from guildwar_visible_towers import authorize_codes,VisibilityUnavailable


class GuildWarVisibilityTests(unittest.TestCase):
 def test_selected_opponent_and_only_normal_unlocked_visible_towers(self):
  self.assertEqual(authorize_codes(1,[11,12,13],[{'code':11,'state':0},{'code':12,'state':3}]),{11})
  with self.assertRaises(VisibilityUnavailable):authorize_codes(0,[11],[{'code':11,'state':0}])
  with self.assertRaises(VisibilityUnavailable):authorize_codes(1,[11],[{'code':11,'state':3}])

 def test_unknown_ambiguous_and_unlisted_codes_stop(self):
  for rows in ([],[{'code':11,'state':4}],[{'code':99,'state':0}],[{'code':11,'state':0},{'code':11,'state':0}]):
   with self.assertRaises(VisibilityUnavailable):authorize_codes(1,[11],rows)


if __name__=='__main__':unittest.main()
