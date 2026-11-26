"""Save validated snapshots to the local database; optionally capture a visible game page."""
import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path
from local_game_database import ROOT, DEFAULT_DB, FILES, connect, stamp, guild_update_due, sync_database,require_selected_guild,get_collection_target,counts


def capture_visible(module, own=False,database=DEFAULT_DB):
    if module=='pvp' and get_collection_target(database,'pvp')=='rankings':
        raise ValueError('verified ranking context is required; generic visible-player PVP capture is disabled')
    # Only documented, successful read-only capture paths. Never navigate or modify teams.
    sys.path.insert(0, str(ROOT / 'scripts/runtime'))
    from bounded_equipment_reader import Reader
    from native_layouts import NEW_SHA
    out = ROOT / 'data/research/runtime.private' / (module+'-update-'+stamp().replace(':','').replace('+','_')+'-'+uuid.uuid4().hex[:6])
    if module == 'guild':
        from read_guild_members import capture
        from parse_runtime_guild import parse_capture
        with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',180) as reader:
            reader.expected_module_sha=NEW_SHA
            reader.refresh()
            capture(reader,out)
        doc = parse_capture(out)
        require_selected_guild(doc['name'],database)
        if not doc['membershipComplete']:
            raise ValueError('incomplete guild roster')
        # Parser has the existing completeness guard and atomic replacement.
        subprocess.run([sys.executable,str(ROOT/'scripts/parse_runtime_guild.py'),'--capture',str(out)],cwd=ROOT,check=True,timeout=60,capture_output=True)
    else:
        from read_defense_team import capture
        from read_visible_member_defense import visible_context
        from parse_runtime_defense import parse_capture
        from import_defense_teams import import_file
        with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',600) as reader:
            reader.expected_module_sha=NEW_SHA
            reader.refresh()
            context = None if own else visible_context(reader,True)
            capture(reader,out,True,context)
        doc = parse_capture(out, all_teams=True)
        observations=out/'observations.private.json'
        observations.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf8')
        import_file(observations,ROOT/'data/normalized/defense-teams.private.json')


def capture_ranked_http(args,db):
    sys.path.insert(0,str(ROOT/'scripts/runtime'))
    from collect_ranked_pvp_http import acquisition_lock,main as collect_http
    with acquisition_lock():
        if not args.use_authorized_runtime_session or args.own:raise ValueError('normal ranked HTTP acquisition needs explicit session authorization')
        if args.database.resolve()!=DEFAULT_DB.resolve():raise ValueError('normal ranked capture uses the existing default database')
        from pvp_scope_policy import matches_scope,migrate_current_scopes
        migrate_current_scopes(db)
        rows=[(sid,) for label,sid in db.execute('SELECT scope_label,snapshot_id FROM current_rankings ORDER BY scope_label') if matches_scope(label,args.scope)]
        if not rows and args.keep_ranking_source:raise ValueError('accepted ranking source missing')
        staged=[]
        session=None
        if args.resume_staged:
            from activate_completed_pvp_scopes import latest_staged,phase_ready
            from pvp_scope_policy import LABELS
            candidates=latest_staged(db)
            required=[label for label in LABELS if matches_scope(label,args.scope)]
            if not all(label in candidates for label in required):raise ValueError('requested staged phase sources missing')
            staged=[{'scope':label,'snapshotId':candidates[label][0],'status':'success'} for label in required]
            rows=[(r['snapshotId'],) for r in staged if not phase_ready(db,r['snapshotId'],candidates[r['scope']][1])[0]]
            print(json.dumps({'resumeStagedPhases':len(rows),'alreadyCompletePhasesReused':len(staged)-len(rows)}),flush=True)
        if not args.keep_ranking_source and not args.resume_staged:
            sys.path.insert(0,str(ROOT/'scripts/runtime'))
            from refresh_pvp_rankings_http import refresh
            from pvp_league_codes import verified_mappings
            from pvp_session import load_session,Reader,NEW_SHA
            from datetime import datetime,timezone
            table=db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pvp_ranking_checks'").fetchone()
            checked=[] if not table else [db.execute('SELECT max(checked_at) FROM pvp_ranking_checks WHERE snapshot_id=?',(row[0],)).fetchone()[0] for row in rows]
            expected=sum(matches_scope(m['label'],args.scope) for m in verified_mappings())
            ranking_fresh=len(checked)==expected and bool(checked) and all(at and 0<=(datetime.now(timezone.utc)-datetime.fromisoformat(at)).total_seconds()<60 for at in checked)
            if args.force or not ranking_fresh:
                with Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',120) as reader:
                    reader.expected_module_sha=NEW_SHA;reader.refresh();session=load_session(reader,authorized=True)
                staged=refresh(session,args.scope,apply=True,activate=False)
                print(json.dumps({'rankingRefresh':staged}),flush=True)
                if any(r['status']!='success' for r in staged):raise ValueError('partial new ranking source; previous current pointers retained')
                rows=[(r['snapshotId'],) for r in staged]
        for row in rows:
            command=[sys.executable,str(ROOT/'scripts/runtime/collect_ranked_pvp_http.py'),'--snapshot',row[0],
                     '--top',str(args.top),'--max-age-seconds',str(args.max_age_seconds),'--use-authorized-runtime-session']
            if args.force:command.append('--force')
            collect_http(command[2:],session=session)
            completed=next((r for r in staged if r['snapshotId']==row[0]),None)
            if completed:
                # Each phase is independently complete here. A later phase's
                # failure must not hide this phase's validated new observations.
                with db:db.execute('INSERT INTO current_rankings VALUES (?,?) ON CONFLICT(scope_label) DO UPDATE SET snapshot_id=excluded.snapshot_id',(completed['scope'],completed['snapshotId']))
        # Commit complete ranking sources only after their defense attempts
        # have been validated/saved. Failures leave the old view usable.
        if staged:
            with db:
                for row in staged:db.execute('INSERT INTO current_rankings VALUES (?,?) ON CONFLICT(scope_label) DO UPDATE SET snapshot_id=excluded.snapshot_id',(row['scope'],row['snapshotId']))
        if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='current_gear_definitions'").fetchone():
            from derive_http_gear_values import build as derive_values,save as save_values
            values=derive_values(args.database);save_values(values,args.database)
            print(json.dumps({'nativeGearReconstruction':values['summary'],'sourceId':values['sourceId'],'externalReferenceValuesUsed':False}),flush=True)
        from character_instance_progress import build as build_progress,save as save_progress
        progress=build_progress();save_progress(progress)
        print(json.dumps({'characterInstanceProgress':progress['summary'],'sourceId':progress['sourceId'],'networkRequests':0}),flush=True)
        if args.sync_supabase:
            subprocess.run([sys.executable,str(ROOT/'scripts/sync_pvp_rankings_supabase.py'),'--apply'],cwd=ROOT,check=True,timeout=600)
        return counts(db,verify_integrity=False) # Accepted hashes/results were already checked; no full DB recheck per update.


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module',choices=['all',*FILES],default='all')
    parser.add_argument('--database',type=Path,default=DEFAULT_DB)
    parser.add_argument('--capture',action='store_true',help='Capture the visible guild list, or use the authorized normal PVP ranking/defense requests')
    parser.add_argument('--own',action='store_true',help='Use the verified own-player PVP capture instead of the visible other-player context')
    parser.add_argument('--if-due',action='store_true',help='Guild only: skip when a snapshot is already captured since this Tuesday noon')
    parser.add_argument('--use-authorized-runtime-session',action='store_true',help='Use the expressly authorized in-memory session for the normal ranking defense path')
    parser.add_argument('--top',type=int,default=200)
    parser.add_argument('--max-age-seconds',type=int,default=300)
    parser.add_argument('--force',action='store_true')
    sys.path.insert(0,str(ROOT/'scripts/runtime'))
    from pvp_scope_policy import CLI_SCOPES
    parser.add_argument('--scope',choices=CLI_SCOPES,default='all',help='Gold and above, with distinct native subdivisions; old lower-tier sources retained only as history')
    parser.add_argument('--keep-ranking-source',action='store_true',help='Reuse the accepted ranking source instead of refreshing the proven normal ranking request')
    parser.add_argument('--resume-staged',action='store_true',help='Resume pending latest proven phases without refetching completed phases or changing source times')
    parser.add_argument('--sync-supabase',action='store_true',help='Also save/read back an insert-only private Supabase draft after local validation')
    args=parser.parse_args()
    if args.capture and args.module not in ('guild','pvp'):parser.error('--capture requires --module guild or pvp')
    if args.own and (not args.capture or args.module!='pvp'):parser.error('--own requires --module pvp --capture')
    if args.if_due and args.module!='guild':parser.error('--if-due requires --module guild')
    db=connect(args.database)
    with db:
        attempt=db.execute('INSERT INTO update_attempts(module,started_at,status) VALUES (?,?,?)',(args.module,stamp(),'running')).lastrowid
    try:
        if args.if_due:
            row=db.execute("SELECT d.payload FROM documents d JOIN current_documents c USING(sha256) WHERE c.filename=?",(FILES['guild'],)).fetchone()
            selected=db.execute("SELECT target_name FROM collection_targets WHERE module='guild'").fetchone()
            if row and (not selected or json.loads(row[0])['name']==selected[0]) and not guild_update_due(json.loads(row[0])['capturedAt']):
                with db:db.execute("UPDATE update_attempts SET finished_at=?,status='skipped',reason_code='current_week_already_captured' WHERE id=?",(stamp(),attempt))
                print(json.dumps({'status':'skipped','reason':'current_week_already_captured'}));return
        normal_http=args.capture and args.module=='pvp' and get_collection_target(args.database,'pvp')=='rankings'
        if normal_http:
            result=capture_ranked_http(args,db)
        elif args.capture and args.module=='guild' and get_collection_target(args.database,'guild')=='公會前100名':
            if not args.use_authorized_runtime_session:raise ValueError('explicit local guild session authorization required')
            if args.database.resolve()!=DEFAULT_DB.resolve():raise ValueError('ranked guild capture uses the existing default database')
            sys.path.insert(0,str(ROOT/'scripts/runtime'))
            from collect_guild_rankings_http import collect
            from collect_ranked_pvp_http import acquisition_lock
            from collect_guildwar_http import collect as collect_current_war
            from types import SimpleNamespace
            with acquisition_lock():
                result=collect(SimpleNamespace(force=args.force,ranking_copies=None))
                # Only the current normal ally/opponent war context. Never
                # substitute top-100 guild IDs into the fortress URL.
                try:result['currentWar']=collect_current_war(capture_towers=True)
                except Exception:result['currentWar']={'status':'unavailable','reason':'current_visible_war_unavailable','oldDataPreserved':True}
            if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='current_gear_definitions'").fetchone():
                from derive_guildwar_gear_values import build as derive_guild_values,save as save_guild_values
                values=derive_guild_values(args.database);save_guild_values(values,args.database)
                print(json.dumps({'guildWarNativeGearReconstruction':values['summary'],'sourceId':values['sourceId']}),flush=True)
            if args.sync_supabase:subprocess.run([sys.executable,str(ROOT/'scripts/sync_guild_rankings_supabase.py'),'--apply'],cwd=ROOT,check=True,timeout=600)
        else:
            if args.capture:capture_visible(args.module,args.own,args.database)
            result=sync_database(database=args.database,modules=None if args.module=='all' else [args.module])
        with db:db.execute("UPDATE update_attempts SET finished_at=?,status='success' WHERE id=?",(stamp(),attempt))
        print(json.dumps({'status':'success','counts':result}))
    except Exception as error:
        if str(error)=='update_already_running':
            with db:db.execute("UPDATE update_attempts SET finished_at=?,status='skipped',reason_code='update_already_running' WHERE id=?",(stamp(),attempt))
            print(json.dumps({'status':'skipped','reason':'update_already_running'}));return
        # Exceptions can contain device paths, account IDs, or raw memory diagnostics.
        # Keep them local, expose only a fixed reason code to status consumers.
        import traceback
        error_dir=ROOT/'data/research/runtime.private/update-errors'
        error_dir.mkdir(parents=True,exist_ok=True)
        (error_dir/(str(attempt)+'.private.txt')).write_text(traceback.format_exc(),encoding='utf8')
        reason=str(error) if str(error) in ('http_access_denied','http_error_429','normal_result_object_missing','response_owner_differs','pvpteam_object_missing','response_is_not_json',
                                          'normal_ranking_shape_differs','normal_ranking_row_shape_differs','unexpected_sensitive_response_field') else 'capture_or_validation_failed'
        with db:db.execute("UPDATE update_attempts SET finished_at=?,status='failed',reason_code=? WHERE id=?",(stamp(),reason,attempt))
        print(json.dumps({'status':'failed','reason':reason,'previousDatabaseRetained':True}))
        raise SystemExit(1)
    finally:db.close()


if __name__=='__main__':main()
