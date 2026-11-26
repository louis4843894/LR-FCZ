import 'server-only';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const execute=promisify(execFile);
export async function startLocalPvpUpdate(){
 if(process.platform!=='win32')throw new Error('local_task_platform_unavailable');
 await execute('schtasks.exe',['/Run','/TN','LR-Local-PVP-Auto-10min'],{windowsHide:true,timeout:10000});
}
