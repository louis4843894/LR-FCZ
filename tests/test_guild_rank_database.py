import copy,json,sqlite3,sys,tempfile,unittest
from pathlib import Path
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from guild_rank_database import parse_rankings,parse_roster,accept_rankings,accept_roster,current_ranking

RANKS=[ROOT/'data/research/runtime.private/guild-ranking-http-20261125T131216Z-ed59ce',ROOT/'data/research/runtime.private/guild-ranking-http-20261125T131217Z-39fa81']


@unittest.skipUnless(all((p/'rank-response.private.json').exists() for p in RANKS),'saved game rankings required')
class GuildRankTests(unittest.TestCase):
    def test_uses_actual_global_ranks_across_native_grades(self):
        doc=parse_rankings(RANKS)
        self.assertEqual(doc['status'],'success');self.assertEqual(len(doc['guilds']),100)
        self.assertEqual([g['rank'] for g in doc['guilds']],list(range(1,101)))
        self.assertEqual({g['gradeId'] for g in doc['guilds'][:50]},{1});self.assertEqual({g['gradeId'] for g in doc['guilds'][50:]},{2})
        self.assertEqual(len({g['guildId'] for g in doc['guilds']}),100)

    def test_partial_ranking_cannot_replace_previous_complete(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
            path=Path(folder);database=path/'fixture.sqlite';complete=accept_rankings(RANKS,database)
            doc=json.loads((RANKS[1]/'rank-response.private.json').read_bytes());doc['result']['totalRank']['rankingList'].pop(0)
            partial=path/'partial';partial.mkdir();(partial/'rank-response.private.json').write_text(json.dumps(doc),encoding='utf8')
            result=accept_rankings([RANKS[0],partial],database)
            self.assertEqual(result['status'],'partial');self.assertEqual(current_ranking(database)['snapshotId'],complete['snapshotId'])

    def source(self):
        with closing(sqlite3.connect((ROOT/'data/local/lr.private.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
            row=db.execute('SELECT r.payload FROM current_ranked_guild_rosters c JOIN guild_roster_sources r USING(source_id) LIMIT 1').fetchone()
        return ROOT/json.loads(row[0])['sourceDirectory']

    def test_foreign_member_and_duplicate_member_are_rejected(self):
        source=self.source();original=json.loads((source/'guild-response.private.json').read_bytes())
        with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
            path=Path(folder);doc=copy.deepcopy(original);doc['guildMemberList'][0]['gid']='fixture-foreign-guild'
            (path/'guild-response.private.json').write_text(json.dumps(doc),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'owner/duplicate'):parse_roster(path)
            doc=copy.deepcopy(original);doc['guildMemberList'].append(copy.deepcopy(doc['guildMemberList'][0]))
            (path/'guild-response.private.json').write_text(json.dumps(doc),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'owner/duplicate'):parse_roster(path)

    def test_partial_roster_keeps_previous_complete_and_separate_attempt(self):
        source=self.source()
        with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
            path=Path(folder);database=path/'fixture.sqlite';complete=accept_roster(source,database)
            doc=json.loads((source/'guild-response.private.json').read_bytes());doc['guildMemberList'].pop()
            partial=path/'partial';partial.mkdir();(partial/'guild-response.private.json').write_text(json.dumps(doc),encoding='utf8')
            result=accept_roster(partial,database);self.assertEqual(result['status'],'partial')
            with closing(sqlite3.connect(database)) as db:
                self.assertEqual(db.execute('SELECT source_id FROM current_ranked_guild_rosters').fetchone()[0],complete['sourceId'])
                self.assertEqual(db.execute('SELECT status FROM guild_fetch_attempts ORDER BY checked_at DESC LIMIT 1').fetchone()[0],'partial')


if __name__=='__main__':unittest.main()
