import base64,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_character_native_details import inline_string,png_size,public_talents,talent_stages


class CharacterNativeTests(unittest.TestCase):
 def test_captured_inline_group_and_missing_long_dependency(self):
  b=bytearray(24);s=b'tg1174_cony';b[0]=len(s)*2;b[1:len(s)+1]=s
  self.assertEqual(inline_string(b,0),'tg1174_cony');b[0]=1;self.assertIsNone(inline_string(b,0))

 def test_png_chunks_and_corruption(self):
  b=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXioAAAAASUVORK5CYII=')
  # Some encoders have a bad IDAT CRC; create a fully validated minimal file.
  import struct,zlib
  def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
  b=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00\xff\x00\x00\xff'))+chunk(b'IEND',b'')
  self.assertEqual(png_size(b),(1,1))
  with self.assertRaises(ValueError):png_size(b[:-1])
  with self.assertRaises(ValueError):png_size(b[:35]+b'x'+b[36:])

 def test_actual_grade_prefix_and_unknown_are_separate(self):
  row={'talents':{'status':'verified-native-group','steps':[{'stage':i,'kind':'major' if i==1 else 'enhancement','name':'才能','description':'說明','enhanceValueRaw':999,'abilityCode':'private'} for i in range(1,5)]}}
  for grade in (0,1,4):self.assertEqual([s['state'] for s in talent_stages(row,grade)['steps']],['reached']*grade+['locked']*(4-grade))
  for grade in (None,True,-1,5):self.assertEqual({s['state'] for s in talent_stages(row,grade)['steps']},{'unknown'})
  self.assertNotIn('enhanceValueRaw',json.dumps(public_talents(row)));self.assertNotIn('abilityCode',json.dumps(public_talents(row)))
  self.assertIsNone(public_talents(None));self.assertEqual(public_talents({'talents':{'status':'not_configured'}})['steps'],[])


if __name__=='__main__':unittest.main()
