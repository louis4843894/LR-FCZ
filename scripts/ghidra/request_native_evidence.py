"""Submit an explicit readonly evidence request to the one already-open Ghidra project."""
import argparse,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('report');p.add_argument('operations',nargs='+');p.add_argument('--queue',type=Path);a=p.parse_args()
 queue=(a.queue or ROOT/'data/research/runtime.private/native-evidence-queue').resolve()
 if not queue.is_relative_to((ROOT/'data/research/runtime.private').resolve()):raise ValueError('queue outside private workspace')
 if not (queue/'ready').exists() or (queue/'closed').exists():raise RuntimeError('read-only evidence session is not ready')
 report=(ROOT/'reports/ghidra'/a.report).resolve()
 if not report.is_relative_to((ROOT/'reports/ghidra').resolve()):raise ValueError('invalid report path')
 job=queue/(uuid.uuid4().hex+'.req');temporary=job.with_suffix('.tmp');temporary.write_text('\n'.join([str(report),*a.operations])+'\n',encoding='utf8');temporary.replace(job)
 for _ in range(720):
  if job.with_name(job.name+'.error').exists():raise RuntimeError(job.with_name(job.name+'.error').read_text())
  if job.with_name(job.name+'.done').exists():print('REPORT_READY',report,flush=True);break
  if (queue/'closed').exists():raise RuntimeError('session ended before completion')
  time.sleep(.25)
 else:raise TimeoutError('evidence job exceeded three minutes')
