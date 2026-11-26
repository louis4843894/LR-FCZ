"""Recompute ordinary values from each player's own raw copies, using verified calibration.

Run after a collector completes: never run concurrent normalized-file writers.
"""
import argparse,json
from pathlib import Path
from parse_runtime_gear_values import enrich,ROOT
from import_defense_teams import import_file
from local_game_database import sync_database

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--factor',type=Path,required=True);a=p.parse_args()
    calibration=ROOT/'data/research/runtime.private/member-defense-capture-20261125T023755Z-ee891f'
    calibration_factor=ROOT/'data/research/runtime.private/gear-factor-20261125T031832Z.private.json'
    review=calibration/'ordinary-value-screen-review.private.json'
    module=ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so'
    translation=ROOT/'data/extracted/lr_20261116T212608096_7b99bdd0/assets/res/tutorial_res/db/lang_equip/lang_equip.ndb'
    factor=json.loads(a.factor.read_text(encoding='utf8'));doc=json.loads((ROOT/'data/normalized/defense-teams.private.json').read_text(encoding='utf8'))
    source_ids={r['sourceId'] for r in doc['snapshots']}
    total=0;processed=0;skipped=0
    for source in sorted(source_ids):
        capture=ROOT/'data/research/runtime.private'/source
        if capture==calibration or not (capture/'capture.json').exists():continue
        meta=json.loads((capture/'capture.json').read_text(encoding='utf8'))
        if meta['pid']!=factor['pid'] or meta['moduleSha256']!=factor['moduleSha256'] or not any(g.get('attributeReadState')=='captured' for r in meta['records'] for g in r['equipment']):
            skipped+=1;continue
        data=enrich(capture,a.factor,review,module,translation,calibration,calibration_factor)
        output=capture/'observations-values.private.json';output.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
        import_file(output,ROOT/'data/normalized/defense-teams.private.json')
        processed+=1;total+=data['captureEvidence']['ordinaryValues']['verifiedValueCount']
    sync_database(modules=['pvp'])
    print(json.dumps({'processedCaptures':processed,'skippedIncompatibleOrMissingAttributes':skipped,'newlyCalculatedValues':total,'currentGearVisuallyVerified':False}))

if __name__=='__main__':main()
