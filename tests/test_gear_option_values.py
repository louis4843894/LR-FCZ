"""Isolated tests; these fixtures are never accepted as game observations."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from native_gear_option_values import interpolate,reinforced,render_description,reconstruct


class GearOptionValues(unittest.TestCase):
 def test_native_placeholder_order_percent_seconds_and_integer(self):
  text,missing=render_description('<#78ff00>{$3p}<->／{$4f}秒／{$1n}',{0:2.9,2:.25,3:1.75})
  self.assertEqual(text,'25.0%／1.8秒／2');self.assertEqual(missing,[])
 def test_missing_and_unsupported_parameters_do_not_become_zero(self):
  text,missing=render_description('持續{$4f}秒',{})
  self.assertEqual(text,'持續（數值尚未解析）秒');self.assertEqual(missing,[3])
  with self.assertRaises(ValueError):render_description('{$3x}',{2:1})
 def test_invalid_grade_level_and_unknown_level_rejected(self):
  for grade in [-1,10,None,True]:
   with self.assertRaises(ValueError):interpolate(.1,.15,grade,10)
  for level in [-1,101,None,True]:
   with self.assertRaises(ValueError):reinforced(.1,.15,7,10,.02,level)
 def test_two_actual_definition_ranges_have_separate_special_enhancement(self):
  # Real 12.4.2 definitions; ordinary currentEnchant/maxEnchant is not an input.
  self.assertAlmostEqual(reinforced(.1,.15,7,10,.02,5),.23888889,places=6)
  self.assertAlmostEqual(reinforced(.08,.12,6,10,.016,0),.10666667,places=6)
  self.assertAlmostEqual(reinforced(.12,.18,4,10,.024,5),.26666667,places=6)
 def test_special_talent_group_order_is_preserved_and_identity_is_required(self):
  option={'specialOptionCode':'fixture','titleLangCode':'title','normalDescLangCode':'normal','specialDescLangCode':'special',
          'normalAttrNo':1,'normalAttrEnchantIncrease':0.,'equipTalentCode':'fixture-talent','equipTalentValueDivideGrades':10,'recordSha256':'fixture'}
  normal={'attributeId':1,'selector1':'none','selector2':'none','hasDependency68':False,'hasDependency70':False,
          'minValueRaw':.1,'maxValueRaw':.1,'valueDivideGrades':10,'typeEnum':26,'rawRecordSha256':'fixture'}
  actual={'specialOptionCode':'fixture','currentSpecialEnchant':0,'specialOptionAttrValueGrade':0,'specialOptionTalentValueGrade':0}
  def talent(name,value):
   return {'id':name,'equipTalentCode':'fixture-talent','targetAbilityCode':name,'rootAbilityCode':'root','recordSha256':'fixture',
           'buffFactorMin':value,'buffFactorMax':value,'buffFactorEnchantIncrease':0.,'subBuffFactorMin':2.,'subBuffFactorMax':2.,'subBuffFactorEnchantIncrease':0.}
  result=reconstruct(option,[talent('first',1),talent('second',.25)],normal,actual,{'title':'測試','normal':'命中 %s','special':'增加{$3p}，{$4f}秒'})
  self.assertEqual(result['description'],'增加25.0%，2.0秒');self.assertFalse(result['valueVisuallyVerified']);self.assertEqual(result['activationState'],'not_verified')
  self.assertIsNone(reconstruct(option,[talent('first',1)],normal,{**actual,'currentSpecialEnchant':None},{}))
  with self.assertRaises(ValueError):reconstruct(option,[],normal,{**actual,'specialOptionCode':'other'},{})


if __name__=='__main__':unittest.main()
