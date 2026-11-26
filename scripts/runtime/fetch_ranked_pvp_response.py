"""Fetch one already-listed player's normal defense response, without UI changes.

Uses only the user's expressly authorized existing session in RAM. Credentials
and response headers are never written. This is source acquisition, not a claim
that every returned instance field has been parsed or semantically verified.
"""
import argparse,gzip,hashlib,io,json,re,sqlite3,time,urllib.error,urllib.parse,urllib.request,uuid
from datetime import datetime,timezone
from pathlib import Path
from pvp_session import load_session,Reader,NEW_SHA,ROOT,SessionUnavailable


class AcquisitionStopped(ValueError):pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise AcquisitionStopped('redirect_not_followed')


def ranked_player(snapshot_id,rank,database=None):
    database=database or ROOT/'data/local/lr.private.sqlite'
    db=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        row=db.execute('SELECT payload FROM ranking_snapshots WHERE snapshot_id=?',(snapshot_id,)).fetchone()
        if not row:raise AcquisitionStopped('accepted_ranking_source_missing')
        ranking=json.loads(row[0]);matches=[p for p in ranking['players'] if p['rank']==rank]
        if len(matches)!=1:raise AcquisitionStopped('rank_not_unique_in_accepted_source')
        return ranking,matches[0]
    finally:db.close()


def normal_json(session,path,*,purpose='pvp'):
    if session.base_url!='https://rangers-api.line-apps.com/v12.4':raise AcquisitionStopped('unexpected_normal_origin')
    allowed=False
    if purpose=='pvp':
        from pvp_league_codes import verified_mappings
        ranking_paths={'/pvp/league/rank/'+m['phaseCode'] for m in verified_mappings()}
        allowed=path.startswith('/player/units/team/equip/uid/') or path in ranking_paths
    elif purpose=='guild-ranking':
        # 012a386c formats this GET; 012a4db4 uses the same selector+1
        # with GUILD_LEVEL_TITLE_%d. Local zh-Hant key 1 is 傳奇.
        allowed=re.fullmatch(r'/guildwar/rank/total\?gradeId=[1-7]',path) is not None
    elif purpose=='guild-profile':
        # 0125386c substitutes the GuildInfoModel GID in /guild/${GID}
        # and uses the ordinary GET helper 0105a004.
        allowed=re.fullmatch(r'/guild/[A-Za-z0-9%._~\-]{1,768}',path) is not None
    elif purpose=='guild-roster':
        # 01259a0c -> /guild/${GID}/member/list -> GET 0105a004.
        allowed=re.fullmatch(r'/guild/[A-Za-z0-9%._~\-]{1,768}/member/list',path) is not None
    elif purpose=='guild-history':
        # 01259020 substitutes the selected GID in 007b8ef1
        # /guild/${GID}/history and calls the normal GET helper 0105a004.
        allowed=re.fullmatch(r'/guild/[A-Za-z0-9%._~\-]{1,768}/history',path) is not None
    elif purpose=='guild-contribution':
        # 013402e0 obtains GID from GuildWarInfoModel+58 and seasonNo
        # from SeasonModel+28, formats 00837336, and calls GET 0105a004.
        allowed=re.fullmatch(r'/guildwar/contribution/[A-Za-z0-9%._~\-]{1,768}/[1-9][0-9]{0,6}',path) is not None
    elif purpose=='guild-war-member-groups':
        # Existing public player GET, 015eab84 formats 007e89c2 with the
        # literal equip (007dae58). No guessed guild ID/mode/query parameter.
        # The caller verifies the visible member against a ranked guild roster
        # and retains only a returned guildwar branch; never imports PVP.
        allowed=re.fullmatch(r'/player/units/team/equip/uid/[A-Za-z0-9%._~\-]{1,768}',path) is not None
    elif purpose=='guild-war-bootstrap':
        # GET 0133adc0/0133af3c (main), GET 0133c678 (saved deck).
        # POST 00f91408 is /player/units/save/{mode}'s guild-war variant
        # and is deliberately never used by this read-only transport.
        allowed=path in ('/guildwar/main','/guildwar/defencedeck')
    elif purpose=='guild-war-tower':
        # 0133c388/0133c590: SeasonModel+28 seasonNo, 0133c470 battle,
        # and an actual fortress code from /guildwar/main. The collector
        # restricts requests to this session's ally/opponent war context.
        allowed=re.fullmatch(r'/guildwar/fortress/(ally|opponent)/[1-9][0-9]{0,6}/[1-3]/[1-9][0-9]{0,3}',path) is not None
    elif purpose=='guild-war-history-main':
        # 0133adc0 uses the remembered normal UI season/status, not a GID.
        # Caller additionally requires an actual saved same-guild context.
        allowed=re.fullmatch(r'/guildwar/main\?status=(first_battle|second_battle|third_battle|first_standby|second_standby|third_standby)&seasonNo=[1-9][0-9]{0,6}',path) is not None
    elif purpose!='pvp':allowed=False
    if not allowed:raise AcquisitionStopped('unverified_normal_path')
    url=session.base_url+path
    request=urllib.request.Request(url,headers=session.request_headers(),method='GET')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    try:
        with opener.open(request,timeout=25) as response:
            if response.status!=200:raise AcquisitionStopped('http_status_not_200')
            payload=response.read(4*1024*1024+1)
            if len(payload)>4*1024*1024:raise AcquisitionStopped('response_exceeds_bound')
            if response.headers.get('Content-Encoding','').lower()=='gzip':
                with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:payload=stream.read(8*1024*1024+1)
            if len(payload)>8*1024*1024:raise AcquisitionStopped('decoded_response_exceeds_bound')
    except urllib.error.HTTPError as error:
        # Do not print the exception, URL, headers, or body. Never retry a denial.
        raise AcquisitionStopped('http_access_denied' if error.code in (401,403) else 'http_error_'+str(error.code)) from None
    except urllib.error.URLError as error:
        # Class/errno only; exception text may include the private target URL.
        reason=error.reason
        label=type(reason).__name__
        number=getattr(reason,'winerror',None) or getattr(reason,'errno',None)
        raise AcquisitionStopped('network_or_tls_failed_'+label+('_'+str(number) if number is not None else '')) from None
    except TimeoutError:raise AcquisitionStopped('network_timeout') from None
    try:doc=json.loads(payload)
    except (ValueError,UnicodeError):raise AcquisitionStopped('response_is_not_json') from None
    return payload,doc


def fetch(session,ranking,player,output_root=None,previous=None):
    from pvp_scope_policy import matches_scope
    if not matches_scope(ranking['scope']['label'],'all'):raise AcquisitionStopped('scope_excluded_by_user')
    uid=player['playerId']
    started=time.monotonic()
    payload,doc=normal_json(session,'/player/units/team/equip/uid/'+urllib.parse.quote(uid,safe=''))
    result=doc.get('result') if isinstance(doc,dict) else None
    if not isinstance(result,dict):raise AcquisitionStopped('normal_result_object_missing')
    owner=result.get('player');groups=result.get('playerUnitTeamGroupMap')
    if not isinstance(owner,dict) or owner.get('uid')!=uid:raise AcquisitionStopped('response_owner_differs')
    if not isinstance(groups,dict) or not isinstance(groups.get('pvpteam'),dict):raise AcquisitionStopped('pvpteam_object_missing')
    # Save only the requested target's public identity and PVP branch. No guild,
    # ordinary teams, session headers or unrelated account objects are exported.
    identity={k:owner[k] for k in ['uid','userName','usePvPTeamNo'] if k in owner}
    selected={'player':identity,'playerUnitTeamGroupMap':{'pvpteam':groups['pvpteam']}}
    def guard(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key.lower() in {'lf_ac','token','accesstoken','access_token','sessiontoken','session_token','refreshtoken','refresh_token','authorization','cookie','password','clientsecret','privatekey'}:
                    raise AcquisitionStopped('unexpected_sensitive_response_field')
                guard(item)
        elif isinstance(value,list):
            for item in value:guard(item)
    guard(selected)
    checked_at=datetime.now(timezone.utc).isoformat()
    if previous is not None:
        previous=Path(previous).resolve()
        if not previous.is_relative_to((ROOT/'data/research/runtime.private').resolve()):raise AcquisitionStopped('unsafe_cached_source')
        before=json.loads((previous/'response.private.json').read_bytes())
        if (before.get('sourceKind')!='verified-normal-pvp-http-branch'
                or before.get('moduleSha256')!=NEW_SHA
                or before['result']['player']['uid']!=uid):raise AcquisitionStopped('cached_source_scope_differs')
        if before['result']==selected:
            return previous,{'sourceFetched':True,'identityMatched':True,'rank':player['rank'],
                             'seconds':round(time.monotonic()-started,3),'unchanged':True,
                             'checkedAt':checked_at,'credentialsPersisted':False,'normalized':False}
    capture={'sourceKind':'verified-normal-pvp-http-branch','parserStatus':'source-only-not-normalized',
             'moduleSha256':NEW_SHA,'gameVersion':'12.4.2','capturedAt':checked_at,
             'rankingSnapshotId':ranking['snapshotId'],'rankingSourceCaptureSha256':ranking['sourceCaptureSha256'],
             'rank':player['rank'],'identityMatch':'exact-native-ranking-uid','responseSha256':hashlib.sha256(payload).hexdigest(),
             'sourcePath':'$.result','result':selected}
    root=output_root or ROOT/'data/research/runtime.private'
    folder=root/('pvp-http-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]);folder.mkdir(parents=True,exist_ok=False)
    text=json.dumps(capture,ensure_ascii=False,indent=2)+'\n';(folder/'response.private.json').write_text(text,encoding='utf8')
    return folder,{'sourceFetched':True,'identityMatched':True,'rank':player['rank'],
                   'pvpBranchKeys':list(groups['pvpteam']),'seconds':round(time.monotonic()-started,3),
                   'unchanged':False,'checkedAt':checked_at,'credentialsPersisted':False,'normalized':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',required=True);parser.add_argument('--rank',type=int,default=1)
    parser.add_argument('--use-authorized-runtime-session',action='store_true')
    args=parser.parse_args()
    if not args.use_authorized_runtime_session:parser.error('explicit session authorization flag is required')
    ranking,player=ranked_player(args.snapshot,args.rank)
    reader=Reader(r'C:\LDPlayer\LDPlayer9\adb.exe','emulator-5554',120);reader.expected_module_sha=NEW_SHA
    try:
        reader.refresh();session=load_session(reader,authorized=True)
        folder,result=fetch(session,ranking,player)
        result['privateCopy']=folder.name;print(json.dumps(result,ensure_ascii=True))
    except (AcquisitionStopped,SessionUnavailable) as error:
        print(json.dumps({'sourceFetched':False,'stopReason':str(error),'credentialsPersisted':False}));raise SystemExit(1)
    except Exception as error:
        print(json.dumps({'sourceFetched':False,'stopReason':'unexpected_context_or_transport_failure','errorType':type(error).__name__,'credentialsPersisted':False}));raise SystemExit(1)
    finally:reader.close()


if __name__=='__main__':main()
