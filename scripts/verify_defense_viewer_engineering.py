"""Run affected checks and persist outcomes; does not fetch or publish game data."""
import hashlib,json,os,shutil,subprocess,time
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
 env=dict(os.environ,LR_NEXT_DIST_DIR='.next-local-defense-viewer-build')
 npm=shutil.which('npm.cmd') or 'npm'
 commands=[('tests',[npm,'test','--','tests/defense-viewer.test.ts','tests/defense-label-reader.test.ts','tests/guild-war.test.ts','tests/pvp-rankings.test.ts']),('types',[npm,'run','typecheck']),('lint',[npm,'run','lint']),('build',[npm,'run','build'])]
 results=[]
 for label,command in commands:
  started=time.monotonic();r=subprocess.run(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',timeout=240)
  (ROOT/f'reports/defense-viewer-{label}.log').write_text(r.stdout,encoding='utf8')
  results.append({'check':label,'exitCode':r.returncode,'seconds':round(time.monotonic()-started,2),'log':f'reports/defense-viewer-{label}.log'})
  print(json.dumps(results[-1]),flush=True)
  if r.returncode:break
 baseline=ROOT/'data/research/runtime.private/baselines/team-viewer-before-20261126T112710Z/manifest.json'
 before={r['path']:r['sha256'] for r in json.loads(baseline.read_text(encoding='utf8'))['files']}
 dependencies={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==before[n] for n in ['package.json','package-lock.json']}
 report={'verifiedAt':datetime.now(timezone.utc).isoformat(),'passed':len(results)==4 and all(r['exitCode']==0 for r in results) and all(dependencies.values()),'checks':results,'dependenciesUnchanged':dependencies,'buildDirectory':env['LR_NEXT_DIST_DIR'],'gameRequests':0,'supabaseWrites':0,'deployed':False}
 (ROOT/'reports/defense-viewer-engineering.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
