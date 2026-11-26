"""Validate saved public animation startup metadata, without inferring hit timing."""
import hashlib,json,math
from pathlib import Path


def load_startup(folder):
 folder=Path(folder).resolve();raw=(folder/'index.json').read_bytes()
 source=json.loads((folder/'index-source.json').read_bytes())
 if source['url']!='https://res.warmycat.com/animation_meta/index.json' or hashlib.sha256(raw).hexdigest()!=source['sha256']:
  raise ValueError('animation index provenance differs')
 data=json.loads(raw)
 if data.get('schema_version')!=2 or data.get('errors') or data.get('count')!=len(data['units']):raise ValueError('animation index incomplete/schema differs')
 manifest=json.loads((folder/'meta-source.json').read_bytes());alternate_raw=(folder/'alternate-meta-source.json').read_bytes()
 alternate=json.loads(alternate_raw);checked=[];alternate_checked=False
 for item in manifest['files']+alternate['files']:
  filename=item['file']
  if Path(filename).name!=filename or item['url']!='https://res.warmycat.com/animation_meta/'+filename:raise ValueError('animation sample path differs')
  b=(folder/filename).read_bytes()
  if hashlib.sha256(b).hexdigest()!=item['sha256']:raise ValueError('animation sample hash differs')
  sample=json.loads(b);code=sample['unit_id']
  if sample['startup']!=data['units'][code]['startup']:raise ValueError('animation sample/index differs')
  alternate_checked|=any(v.get('segment')=='s_action_attack_1' for v in sample['startup'].values())
  checked.append(code)
 if len(set(checked))<4 or not alternate_checked:raise ValueError('three ready-segment samples and an alternate-segment sample required')
 return data['units'],{**source,'sampleIds':checked,'sampleManifestSha256':hashlib.sha256((folder/'meta-source.json').read_bytes()).hexdigest(),
                       'alternateSampleManifestSha256':hashlib.sha256(alternate_raw).hexdigest(),
                       'meaning':'animation-index-startup-segment-duration','unit':'seconds','projectileTravelIncluded':False,'numericSource':'user-confirmed-reference'}


def startup_for(units,code,index):
 row=units.get(code)
 if row is None or row.get('unit_id')!=code or index not in (0,1):return None
 key='skill_'+str(index+1);value=row.get('startup',{}).get(key)
 if not isinstance(value,dict):return None
 seconds=value.get('seconds');frames=value.get('frames')
 if (value.get('meaning')!='segment_duration' or value.get('projectile_spawn_time') is not False
     or value.get('segment') not in (('s_attack_ready','s_action_attack_1') if index==0 else ('s2_attack_ready',))
     or type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<=seconds<=120
     or type(frames) is not int or frames<0):return None
 return {'seconds':seconds,'frames':frames,'segment':value['segment'],'meaning':'animation-index-startup-segment-duration','sourceKind':'user-confirmed-reference'}
