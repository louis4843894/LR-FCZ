"""Apply the selected Gold-and-above current pointers, retaining all history."""
import json,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts/runtime'))
from pvp_scope_policy import migrate_current_scopes
def apply(database=ROOT/'data/local/lr.private.sqlite'):
 with sqlite3.connect(database) as db:
  before=db.execute('SELECT count(*) FROM ranking_snapshots').fetchone()[0]
  migrate_current_scopes(db)
  scopes=[r[0] for r in db.execute('SELECT scope_label FROM current_rankings')]
  after=db.execute('SELECT count(*) FROM ranking_snapshots').fetchone()[0]
  if before!=after:raise ValueError('immutable ranking history changed')
 return {'currentScopes':scopes,'historicalRankingSourcesPreserved':before==after,'lowerTierCurrentPointersRemoved':all(s not in ('白銀','青銅') for s in scopes)}
if __name__=='__main__':
 result=apply();(ROOT/'reports/pvp-gold-scope-policy.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
