import {readPvpAutoUpdateState} from '../../lib/local-game-data';
import {PvpUpdateControls} from './pvp-update-controls';
export async function PvpAutoUpdateStatus(){
 const state=await readPvpAutoUpdateState();
 if(!state?.enabled)return <p>PVP 自動更新尚未啟用，現有資料與取得時間仍保留。</p>;
 return <div className="pvp-auto-update-status"><p>自動更新：每 {state.intervalMinutes} 分鐘嘗試取得黃金以上的排行與防禦；大師、鑽石、黃金各分 1／2／3 階。</p>
 <PvpUpdateControls initial={state}/>
 {state.lastFinishedAt&&<p>最近執行完成：{new Date(state.lastFinishedAt).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false})}。重新整理可查看最新已保存資料。</p>}
 <p>需遊戲維持有效工作階段；不自動登入，未完整更新不清空既有資料。</p></div>;
}
