import copy,json,sqlite3,sys,tempfile,unittest
from pathlib import Path
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from audit_equipment_reference import compare_value,build_audit,save_local
from sync_equipment_audit_supabase import upload
from import_supabase import SupabaseApiError

class ValueComparisonTests(unittest.TestCase):
    def entry(self,value=444,unit='PERCENT'):
        return {'index':0,'attributeId':40001,'attributeCode':'GATK_MUL','value':value,'unit':unit,'valueVerified':True,'enhancementIncluded':True}
    def ref(self,a=74,b=74):
        return {'normalOptions':[{'optionKey':'EQUIP:GEAR_FILTER_GATK_MUL_nm','range':{'min':a,'max':b,'unit':'PERCENT'}}]}
    def test_fixed_value_and_variable_range_are_different_claims(self):
        self.assertEqual(compare_value(self.entry(),{'enhancement':5},self.ref())['status'],'fixed_value_match')
        self.assertEqual(compare_value(self.entry(),{'enhancement':5},self.ref(70,80))['status'],'within_reference_range')
        self.assertEqual(compare_value(self.entry(500),{'enhancement':5},self.ref())['status'],'value_mismatch')
    def test_unknown_value_is_never_filled_from_reference(self):
        e=self.entry();e.update(value=None,unit=None,valueVerified=False)
        result=compare_value(e,{'enhancement':5},self.ref());self.assertEqual(result['status'],'unparsed_native');self.assertIsNone(result['nativeValue'])
    def test_negative_bounds_and_units_and_rounding(self):
        e=self.entry(-30);self.assertEqual(compare_value(e,{'enhancement':5},self.ref(-5,-5))['status'],'fixed_value_match')
        e=self.entry(-45);self.assertEqual(compare_value(e,{'enhancement':5},self.ref(-5,-8))['status'],'within_reference_range')
        self.assertEqual(compare_value(self.entry(444,'FLAT'),{'enhancement':5},self.ref())['status'],'unit_mismatch')
        e=self.entry(50.4);self.assertEqual(compare_value(e,{'enhancement':5},self.ref(8.4,8.4))['status'],'fixed_value_match')
    def test_exact_key_required_and_no_double_enhancement(self):
        e=self.entry();e['attributeCode']='OTHER'
        self.assertEqual(compare_value(e,{'enhancement':5},self.ref())['status'],'missing_reference')
        self.assertEqual(compare_value(self.entry(),{'enhancement':0},self.ref())['status'],'value_mismatch')

class ActualAuditTests(unittest.TestCase):
    def test_real_native_values_compare_and_roundtrip_without_overwriting_source_documents(self):
        folder=ROOT/'data/research/external-reference/audit-20261125T071751Z-240f51'
        if not folder.exists():self.skipTest('requires real local source copies')
        report,export=build_audit(folder)
        self.assertEqual(report['summary']['templatesMatched'],953)
        # This test uses the accepted current document, which can gain real
        # players. Preserve baseline coverage without assuming a frozen total.
        self.assertGreaterEqual(report['summary']['fixed_value_match'],498)
        self.assertGreaterEqual(report['summary']['within_reference_range'],388)
        text=json.dumps(export)
        doc=json.loads((ROOT/'data/normalized/defense-teams.private.json').read_text(encoding='utf8'))
        entries=[e for t in doc['snapshots'] for m in t.get('members') or [] for g in m['equipment'].values() for e in (g.get('actualEffects') or {}).get('entries',[])]
        self.assertEqual(report['summary']['unparsed_native'],sum(e.get('value') is None for e in entries))
        self.assertFalse(any(k.endswith('mismatch') and n for k,n in report['summary'].items()))
        for t in doc['snapshots']:self.assertNotIn(t['playerId'],text)
        with tempfile.TemporaryDirectory() as temp:
            db=Path(temp)/'audit.sqlite';save_local(report,export,db);save_local(report,export,db)
            with closing(sqlite3.connect(db)) as con:
                self.assertEqual(con.execute('SELECT count(*) FROM equipment_attribute_checks').fetchone()[0],len(entries))
                self.assertEqual(con.execute('SELECT count(*) FROM documents').fetchone()[0],0)
                self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(),[])
            bad=copy.deepcopy(report);bad['summary']['templatesMatched']=0
            with self.assertRaises(ValueError):save_local(bad,export,db)

# Contract fixture only; never sent to the real remote service.
class RemoteFixture:
    def __init__(self):self.versions=[];self.tables={'ranger_research_records':[],'ranger_equipment':[]};self.posts=0
    def request(self,method,endpoint,params=None,payload=None,prefer=None):
        table=endpoint.rsplit('/',1)[-1];params=params or {}
        if method=='POST':
            self.posts+=1
            if table=='ranger_research_snapshots':self.versions.append(copy.deepcopy(payload))
            else:self.tables[table].extend(copy.deepcopy(payload))
            return None
        if method!='GET':raise AssertionError('no overwrite/delete methods permitted')
        if table=='ranger_research_snapshots':
            if params.get('status')=='eq.published':return []
            return copy.deepcopy(self.versions)
        return copy.deepcopy(self.tables[table])

class RemotePersistenceTests(unittest.TestCase):
    def plan(self):
        snap={'snapshot_id':'fixture-audit','module':'equipment','captured_at':'2026-11-25T00:00:00Z','content_sha256':'a'*64,'status':'draft'}
        r={'snapshot_id':'fixture-audit','source_record_identity':{'scope':'fixture','itemCode':'eq_fixture'},'normalized_record':{'value':444}}
        return {'snapshot':snap,'researchRows':[r],'equipmentRows':[]}
    def test_insert_only_readback_and_idempotent_resume(self):
        client=RemoteFixture();plan=self.plan();receipt=upload(plan,client)
        self.assertTrue(receipt['allPayloadsReadBack']);self.assertEqual(client.posts,2)
        upload(plan,client);self.assertEqual(client.posts,2)
    def test_changed_existing_payload_is_preserved_and_rejected(self):
        client=RemoteFixture();plan=self.plan();upload(plan,client)
        client.tables['ranger_research_records'][0]['normalized_record']['value']=999
        with self.assertRaisesRegex(ValueError,'no overwrites'):upload(plan,client)
        self.assertEqual(client.posts,2);self.assertEqual(client.tables['ranger_research_records'][0]['normalized_record']['value'],999)
    def test_private_access_must_be_proven_before_any_write(self):
        client=RemoteFixture()
        with self.assertRaisesRegex(ValueError,'access restrictions'):upload(self.plan(),client,RemoteFixture())
        self.assertEqual(client.posts,0)
    def test_character_templates_use_only_the_research_table_and_remain_private(self):
        client=RemoteFixture();plan=self.plan();plan['snapshot']['module']='characters'
        receipt=upload(plan,client)
        self.assertEqual(receipt['characterTemplatesVerified'],1)
        self.assertEqual(client.tables['ranger_equipment'],[])
        self.assertEqual(client.posts,2)
        self.assertEqual(client.versions[0]['status'],'draft')
    def test_character_plan_cannot_insert_equipment(self):
        client=RemoteFixture();plan=self.plan();plan['snapshot']['module']='characters';plan['equipmentRows']=[{'unexpected':True}]
        with self.assertRaisesRegex(ValueError,'equipment rows'):upload(plan,client)
        self.assertEqual(client.posts,0)
    def test_pvp_rows_use_private_research_storage_and_invalid_batches_cannot_write(self):
        client=RemoteFixture();plan=self.plan();plan['snapshot']['module']='pvp';plan['uploadBatchSize']=10
        receipt=upload(plan,client);self.assertEqual(receipt['pvpRecordsVerified'],1);self.assertEqual(client.tables['ranger_equipment'],[])
        bad=RemoteFixture();plan['uploadBatchSize']=0
        with self.assertRaisesRegex(ValueError,'batch size'):upload(plan,bad)
        self.assertEqual(bad.posts,0)

if __name__=='__main__':unittest.main()
