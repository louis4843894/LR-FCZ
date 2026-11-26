"""Isolated parser fixtures; never inserted into website or real game data."""
import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from native_layouts import NEW_SHA
from parse_runtime_rankings import parse_capture


class RankingParserTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.base=0x10000000
        self.meta={'sourceKind':'native-visible-pvp-ranking','schemaVersion':1,'moduleSha256':NEW_SHA,
                   'gameVersion':'12.4.2','moduleBase':self.base,'arrayAddress':0x20000000,
                   'capturedAt':'2026-11-25T08:00:00+00:00','consistent':True,
                   'loadedCount':2,'capturedCount':2,'loadedArrayFullyCaptured':True,
                   'rows':[],'errors':[],'files':{},'scopeLabel':'isolated test league'}
        layer=bytearray(0x1a0);struct.pack_into('<Q',layer,0,self.base+0x1f14af8-0x100000)
        struct.pack_into('<Q',layer,0x178,self.meta['arrayAddress']);self.save_blob('layer',layer)
        header=bytearray(0x20);struct.pack_into('<Q',header,0,self.base+0x1f6a7f8-0x100000)
        self.save_blob('array',header);self.save_blob('array-data',struct.pack('<IIQ',2,2,0x21000000))
        self.save_blob('row-pointers',struct.pack('<QQ',0x22000000,0x22000100))
        for i in range(2):
            prefix=f'row-{i:03d}';raw=bytearray(0xb0)
            struct.pack_into('<Q',raw,0,self.base+0x1e53d58-0x100000)
            struct.pack_into('<ii',raw,0x30,1500+i,1+i)
            for label,offset,value in [('player-id',0x18,f'fixture-player-{i}'),('name',0x58,f'test-{i}'),('league-phase',0x78,'TEST')]:
                text=value.encode();raw[offset]=len(text)*2;raw[offset+1:offset+1+len(text)]=text
                self.save_blob(prefix+'-'+label,text)
            self.save_blob(prefix,raw)
            self.meta['rows'].append({'index':i,'prefix':prefix,'objectAddress':0x22000000+i*0x100,'status':'captured'})

    def tearDown(self):self.temp.cleanup()

    def save_blob(self,key,data):
        data=bytes(data);name=key+'.bin';(self.root/name).write_bytes(data)
        self.meta['files'][key]={'file':name,'length':len(data),'sha256':hashlib.sha256(data).hexdigest()}

    def parse(self):
        (self.root/'capture.private.json').write_text(json.dumps(self.meta),encoding='utf8')
        return parse_capture(self.root)

    def test_exact_fields_do_not_invent_defense_or_global_coverage(self):
        doc=self.parse();self.assertEqual(doc['retrievedPlayerCount'],2)
        self.assertEqual(doc['rankRange'],{'minimum':1,'maximum':2})
        self.assertEqual(doc['players'][0]['score'],1500)
        self.assertEqual(doc['players'][0]['defenseState'],'not_read')
        self.assertFalse(doc['scope']['wholeRankingComplete'])
        self.assertNotIn('moduleBase',doc);self.assertNotIn('objectAddress',doc['players'][0])

    def test_wrong_version_inconsistent_and_empty_sources_are_rejected(self):
        self.meta['moduleSha256']='unverified'
        with self.assertRaisesRegex(ValueError,'unverified'):self.parse()
        self.meta['moduleSha256']=NEW_SHA;self.meta['consistent']=False
        with self.assertRaisesRegex(ValueError,'inconsistent'):self.parse()
        self.meta['consistent']=True;self.meta['rows']=[]
        with self.assertRaisesRegex(ValueError,'empty'):self.parse()

    def test_hash_and_string_dependency_conflicts_are_rejected(self):
        (self.root/'row-000.bin').write_bytes(b'altered')
        with self.assertRaisesRegex(ValueError,'hash/length'):self.parse()

    def test_row_pointer_and_index_relationship_is_required(self):
        self.meta['rows'][0]['objectAddress']=0x99999999
        with self.assertRaisesRegex(ValueError,'row position'):self.parse()

    def test_partial_capture_stays_partial(self):
        self.meta['rows']=self.meta['rows'][:1];self.meta['capturedCount']=1
        self.meta['loadedArrayFullyCaptured']=False;self.meta['errors']=[{'index':1,'reason':'read_failed'}]
        doc=self.parse();self.assertEqual(doc['status'],'partial');self.assertEqual(doc['failedRowCount'],1)
        self.assertEqual(doc['retrievedPlayerCount'],1);self.assertEqual(doc['loadedCount'],2)

    def test_false_completeness_is_rejected(self):
        self.meta['rows']=self.meta['rows'][:1];self.meta['capturedCount']=1
        with self.assertRaisesRegex(ValueError,'completeness'):self.parse()

    def test_duplicate_player_identities_are_rejected(self):
        raw=bytearray((self.root/'row-001.bin').read_bytes());value=b'fixture-player-0'
        raw[0x18]=len(value)*2;raw[0x19:0x19+len(value)]=value
        self.save_blob('row-001',raw);self.save_blob('row-001-player-id',value)
        with self.assertRaisesRegex(ValueError,'duplicate ranking identity'):self.parse()


if __name__=='__main__':unittest.main()
