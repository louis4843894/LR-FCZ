"""User-selected acquisition/display scopes; code evidence is checked separately."""
import json
from pathlib import Path
POLICY=json.loads((Path(__file__).resolve().parents[2]/'data/config/pvp-scope-policy.json').read_text(encoding='utf8'))
SCOPES=POLICY['scopes']
LABELS=[r['label'] for r in SCOPES]
ALIASES=POLICY['legacyScopeAliases']
CLI_SCOPES=['all',*LABELS,*ALIASES]

def canonical_scope(label):return ALIASES.get(label,label)

def matches_scope(label,selected):
 label=canonical_scope(label)
 return label in LABELS and (selected=='all' or label==selected or any(r['label']==label and r['group']==selected for r in SCOPES))

def migrate_current_scopes(db):
 """Remove only obsolete current pointers, retaining every immutable source."""
 with db:
  for label,snapshot in db.execute('SELECT scope_label,snapshot_id FROM current_rankings').fetchall():
   canonical=canonical_scope(label)
   if canonical not in LABELS:db.execute('DELETE FROM current_rankings WHERE scope_label=?',(label,))
   elif canonical!=label:
    db.execute('INSERT OR IGNORE INTO current_rankings VALUES (?,?)',(canonical,snapshot))
    db.execute('DELETE FROM current_rankings WHERE scope_label=?',(label,))
