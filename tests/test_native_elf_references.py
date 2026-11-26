import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from native_elf import NativeELF


class NativeReferenceTests(unittest.TestCase):
    def image(self,words):
        image=NativeELF.__new__(NativeELF)
        image.data=struct.pack('<'+'I'*len(words),*words)
        image.loads=[(0x1000,0x1000+len(image.data),0,5)]
        image._unwind_starts=[0x1000,0x1010]
        return image

    def test_bl_signed_relative_target_and_exact_instruction_kind(self):
        image=self.image([0x94000002,0x17ffffff,0x97fffffe,0xd503201f])
        self.assertEqual(image.direct_call_references(0x1008),[{'call':0x1000,'functionStart':0x1000}])
        self.assertEqual(image.direct_call_references(0x1000),[{'call':0x1008,'functionStart':0x1000}])
        image.loads=[(0x1000,0x1010,0,4)]
        self.assertEqual(image.direct_call_references(0x1008),[])

    def test_adr_signed_target_excludes_adrp(self):
        # ADR x0,+8; ADRP x0,same page; ADR x0,-8.
        image=self.image([0x10000040,0x90000000,0x10ffffc0,0xd503201f])
        self.assertEqual(image.adr_references(0x1008),[{'adr':0x1000,'functionStart':0x1000}])
        self.assertEqual(image.adr_references(0x1000),[{'adr':0x1008,'functionStart':0x1000}])

    def test_unwind_lookup_rejects_unbounded_address(self):
        image=self.image([0xd503201f]*8)
        self.assertEqual(image.function_start(0x1014),0x1010)
        for address in (0xfff,0x22011):
            with self.assertRaises(ValueError):image.function_start(address)


if __name__=='__main__':unittest.main()
