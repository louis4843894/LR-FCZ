import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from pvp_auto_update import classify,run_once,save,load

class PvpAutoUpdateTests(unittest.TestCase):
 def test_denial_and_rate_limit_pause_instead_of_being_overridden_by_partial_results(self):
  for reason in ['http_access_denied','http_error_429','normal_ranking_shape_differs','normal_ranking_row_shape_differs','unexpected_sensitive_response_field']:
   text=json.dumps({'stopReason':reason})+'\n'+json.dumps({'status':'failed','reason':'capture_or_validation_failed'})
   self.assertTrue(classify(text,1)['paused'])
 def test_paused_worker_makes_no_child_or_network_request(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
   path=Path(folder)/'state.json';save({'schemaVersion':1,'enabled':True,'paused':True,'intervalMinutes':10,'reason':'http_access_denied'},path)
   with patch('pvp_auto_update.subprocess.run') as call:
    result=run_once(path)
   self.assertEqual(result['networkRequests'],0);call.assert_not_called();self.assertTrue(load(path)['paused'])
 def test_disabled_worker_is_safe_and_success_requires_successful_exit(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
   with patch('pvp_auto_update.subprocess.run') as call:result=run_once(Path(folder)/'state.json')
   self.assertEqual(result['reason'],'automatic_update_disabled');call.assert_not_called()
  self.assertEqual(classify('{"status":"success"}',0)['lastStatus'],'success')
  self.assertEqual(classify('{"status":"success"}',1)['lastStatus'],'failed')
 def test_disabling_during_an_update_is_preserved_when_the_child_finishes(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'data/research/runtime.private') as folder:
   path=Path(folder)/'state.json';save({'schemaVersion':1,'enabled':True,'paused':False,'intervalMinutes':10},path)
   def finish(*args,**kwargs):
    state=load(path);state['enabled']=False;save(state,path)
    from subprocess import CompletedProcess
    return CompletedProcess(args[0],0,stdout='{"status":"success"}',stderr='')
   with patch('pvp_auto_update.subprocess.run',side_effect=finish):result=run_once(path)
   self.assertEqual(result['status'],'success');self.assertFalse(load(path)['enabled'])

if __name__=='__main__':unittest.main()
