import base64
import re
import sys
import time
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/runtime'))
from bounded_equipment_reader import Reader
from equipment_memory import memory_read_command


class BatchedReadTests(unittest.TestCase):
    def reader(self,short=False):
        reader=Reader.__new__(Reader)
        reader.started=time.monotonic();reader.max_seconds=60
        reader.read_count=0;reader.read_bytes=0;reader.ranges=[(1000,2000)];reader.pid=1
        def shell(command):
            self.assertEqual(command.count('| base64'),1)
            return base64.b64encode(b'abcd' if short else b'abcde')
        reader.shell=shell
        return reader

    def test_binary_ranges_keep_order_lengths_and_budget(self):
        reader=self.reader()
        self.assertEqual(reader.read_many([(1000,3),(1100,2)]),[b'abc',b'de'])
        self.assertEqual((reader.read_count,reader.read_bytes),(2,5))

    def test_short_read_is_rejected_instead_of_using_partial_objects(self):
        with self.assertRaisesRegex(RuntimeError,'short'):
            self.reader(True).read_many([(1000,3),(1100,2)])

    def test_invalid_mapping_precedes_any_remote_read(self):
        reader=self.reader()
        reader.shell=lambda command:self.fail('must not contact device')
        with self.assertRaisesRegex(RuntimeError,'mapping'):reader.read_many([(1000,3),(1999,2)])
        self.assertEqual(reader.read_count,0)

    def test_bounded_count_and_expired_budget(self):
        reader=self.reader()
        with self.assertRaises(ValueError):reader.read_many([(1000,1)]*129)
        reader.started-=61
        with self.assertRaises(TimeoutError):reader.read_many([(1000,3)])

    def test_block_optimization_never_rounds_or_overreads(self):
        for address,count in [(0x100000,8),(0x104008,0x8e8),(0x104030,0x30),(0x104001,31)]:
            command=memory_read_command(1,address,count)
            numbers={k:int(v) for k,v in re.findall(r'(bs|skip|count)=(\d+)',command)}
            self.assertEqual(numbers['bs']*numbers['skip'],address)
            self.assertEqual(numbers['bs']*numbers['count'],count)


if __name__=='__main__':unittest.main()
