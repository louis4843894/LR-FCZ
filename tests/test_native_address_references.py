import struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from native_elf import NativeELF

class AddressReferenceTests(unittest.TestCase):
 def refs(self,words,target=0x100180):
  elf=NativeELF.__new__(NativeELF);elf.data=struct.pack('<'+'I'*len(words),*words)+b'\x1f\x20\x03\xd5'*8
  elf.loads=[(0x100000,0x100000+len(elf.data),0,1)]
  return elf.address_references(target)
 def test_adjacent_and_scheduled_unmodified_register_are_retained(self):
  self.assertEqual(len(self.refs([0x90000000,0x91060000])),1)
  self.assertEqual(len(self.refs([0x90000013,0xd503201f,0x91060273])),1)
 def test_overwritten_add_page_and_caller_saved_call_are_rejected(self):
  for words in [[0x90000000,0x91040000,0x91060000],
                [0x90000000,0x90000020,0x91060000],
                [0x90000000,0x94000000,0x91060000],
                [0x90000000,0xd2800000,0x91060000]]:
   self.assertEqual(self.refs(words),[])
 def test_actual_false_reference_window_is_not_classified_as_deck_info(self):
  # Same exact instruction pattern as the native ranking radio-button UI.
  self.assertEqual(self.refs([0x90000000,0x91040000,0x94000000,0xaa0003f5,0x90000020,0x91060000]),[])

if __name__=='__main__':unittest.main()
