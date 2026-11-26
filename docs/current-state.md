# LR 目前可續接狀態（2026-11-27）

## 最新：角色頁 hydration 與公會防禦續查（11/27）

- 使用者回報server為skip-navigation按鈕、client為header。檢查現行SiteHeader沒有window／storage／matchMedia或掛載條件決定初始節點，角色頁與root沒有非法button巢狀。**本輪在當前3101與Vercel版本未重現該歷史console差異**；兩個dev實際回傳的header chunk SHA相同，不能把舊快取／版本混用當成已證實唯一根因。
- 實際測到3000預覽缺少React事件，三種進入方式的跳過導覽都不能聚焦；不是「console沒報錯所以通過」。辨識原Next程序後只重啟3000，改用獨立 `.next-local-hydration-dev3000`，保留舊.next與全部資料；重啟後三案例均真正互動成功。3101與雷電不受此重啟影響。
- **結構修正**：新增 `app/_components/skip-navigation.tsx`，root layout body固定先輸出全站唯一按鈕；SiteHeader只負責header／導覽，不再把全站按鈕放在每頁client元件的首節點。按鈕初次JSX固定，瀏覽器API只在啟用時執行；保留聚焦main／捲動功能與CSS顯示方式。未使用suppressHydrationWarning、停用SSR或刪除按鈕。
- 補上Browser的console.error／warning收集；先前僅收Runtime.exceptionThrown，不足以證明沒有React recoverable hydration錯誤。新 `verify_character_hydration.py` 比對停用JS的server結構與首次client結構，等待React事件掛載，驗證直接開網址／重新整理／列表點入與按鈕實際聚焦；失敗不以靜態HTML當成功。
- 修正後3000 dev、3101 dev及獨立production各3案例通過，hydration console錯誤0；型別、lint、2-worker production build通過。建置 `.next-local-hydration-build`，無套件／lock或資料改動。已推main **d38c7ab**，Vercel自動部署success後公開角色頁另3案例通過，**合計12個修正後案例，包含實際console收集及跳過按鈕互動**。報告 `character-hydration-{before,after,production,deployed}-*.json`、`character-hydration-build.log`。3101已恢復原development；3000沿用新的獨立dist，未刪除舊產物。
- 鍵盤補驗另處理headless焦點條件：初次瀏覽器document.hasFocus為false，activeElement雖是按鈕、:focus卻不成立，不能用這種背景視窗測可見性／Enter。加入Page.bringToFront及Emulation.setFocusEmulationEnabled，產品CSS／JS不變；本機及線上各3入口的按鈕focus可見、原生Enter聚焦main、SSR結構及console均通過。`verify_character_hydration.py`現已採此方式；`character-hydration-keyboard-{3000,deployed}.json`。最初失敗紀錄保留在`character-skip-keyboard-before-active-window.json`，不冒稱當時產品沒有可用的焦點功能。
- **公會新證據**：唯讀沿用Ghidra專案，-noanalysis/-readOnly、768MB／單程序，定向讀12個直接相關函式；`01328cac → 0133d0f8 → POST /guildwar/battle/enter → 0133d30c` 的預期對手回應會解析 `opponentBattlePlayerInfo.playerUnitTeams["1"]`，配置0x8e8 UnitData、經00e4ecf8及00f617f8註冊，再交目前BattleManager virtual660。**本輪沒有實際捕獲這份回應，不能當作新增防禦成功**。
- 輸入鏈已補齊至選取欄位：0132acac從事件dictionary取 `MEMBER_MODEL`，透過實機已確認BattlePresetDataManager(AP01dfebb0)的virtual198／00c9ca04保留到this+f8；virtual190／00c9c9fc讀回。呼叫端以該物件virtual88／98取得deckId／fortressCode，與GuildWarMemberModel AP01eb60e0的01349688（+80）／01349698（+88）相符。目前該選取指標為null，因此沒有謊稱直接觀察到選取物件型別。請求三欄已用模組原始位元組核對為 **fortressCode、deckId、itemCodes**；早期摘要暫記的unitCodes已修正，未據此送出請求。
- 實機只讀比對公會GID的雜湊，仍為 **復仇者總動員／にほーん（對照已保存排行分別16／5，不是新抓排名）**，沒有換成第三個公會；十塔11～16可見、21～23／31狀態3鎖定。一般Battle目前是基底BattleManager，未把其他模式或空選取當公會資料。沒有讀Cookie／金鑰、沒有遊戲HTTP／出戰／保存／解鎖／重試PVP拒絕；沒有重抓同樣六塔，**新增防禦0，覆蓋仍1完整／1部分／98未取得**。
- 證據彙整 `reports/guild-defense-battle-boundary-review.json`、`guild-defense-selected-context-check.json`、`guildwar-battle-entry-callers.json` 與 `ghidra/guild-battle-*-1242.txt`。`python scripts/audit_guild_battle_defense_boundary.py`可純離線核對；`python scripts/runtime/inspect_guild_defense_boundary.py`只讀已確認根與別名，不讀憑證。兩段Ghidra PIC警告只採局部可驗證getter／呼叫流，不把不可信的長內聯當新結論。直接BL/B不等於排除所有間接呼叫。**具體缺口仍是其他公會正常可取得的deckId／戰局上下文，尚未建立任意前百GID的防禦讀取；不能把戰鬥POST當純查詢。** 新Python腳本編譯與實際離線核對通過；網站、資料包與DB均未改，因此未重跑不受研究影響的建置或資料驗證。

## 最新：圖鑑操作優化與 Vercel 顯示資料（11/27）

- 本輪依參考網站公開的搜尋／進階篩選方式完善既有介面：首頁可切換角色／裝備／公會快速查詢；角色／裝備圖鑑新增可逐項移除的篩選標籤、結果範圍、數字分頁與直接跳頁，保留重複效果參數及 AND／OR。裝備多選改成可搜尋勾選清單，隱藏選項仍保留勾選；角色排序新增星等／中文名稱。長涵蓋說明收合、空結果可重設。手機選單支援 Escape／外部點擊關閉與鍵盤焦點返回，詳細頁有父層導覽。原防禦收合版型與資料判定保留。
- 使用者接著要求解決 Vercel 看不到。原因是角色、詳情、PVP／公會讀取依賴未提交的 SQLite／研究檔及 development 限制，圖片 API 又限定本機。現在 production 改讀 **`data/site-display/*.json.gz` 的顯示模型**，圖片改走 **`public/site-assets/`**；不把 NODE_ENV 設成 development、不上傳 SQLite、不開放擷取 API。新增顯示資料 reader／隱私檢查及本機專用只讀匯出路由，原研究流程不變。
- 已產生 **1,200 個壓縮模型、2,405 角色、953 裝備、100 公會／4,751 成員、1,083 個目前排名防禦頁、3,292 張 PNG（2,405 角色＋887 裝備）**，共35,076,401 bytes（約35 MB）。manifest 記錄來源類別、各檔／圖片SHA；參考技能／模板效果仍保留user-confirmed-reference類別，不改稱本機原生解析。未取得圖片仍用替代圖。
- 公會部署顯示驗證 **740角色／2,219裝備＋1確認空位，2,219件均有實際強化，740筆培養關聯齊**；完整1公會／部分1／未取得98維持原判定。**沒有新增公會或重新抓取遊戲**。原始玩家／公會識別、角色／裝備實例ID、原始階級、私有路徑與個人未確認部署儲存設定不進入公開模型；別名／時間／槽位及已確認中文實際效果保留。
- 重建：先讓既有development預覽在127.0.0.1:3101，再跑 `python scripts/export_site_display.py`、`python scripts/validate_site_display.py`。中斷可用 `--resume data/research/runtime.private/site-display-<時間>` 續接相同輸入；新來源應開新匯出。有效資料全部檢查後才更新輸出，失敗不先清空；原始副本／7GB DB／Supabase私有草稿均未修改。完整說明 `docs/site-display.md`。
- **驗證通過**：受影響TS6檔22測試、型別／lint／production build；圖鑑互動12案例與production桌面／手機16案例，無JS例外。正式預覽故意指定不存在的LR_LOCAL_DATABASE_PATH仍正常；本機匯出／圖片端點404，更新端點403。19份部署追蹤涵蓋1,200／1,200顯示檔，私人檔案0。報告 `catalog-tools-ui-validation.json`、`site-display-validation.json`、`site-display-production-ui.json`、`site-display-build-trace.json`、`site-display-build.log`。
- 依賴／lock未變；沒有Ghidra、遊戲請求、裝置操作、憑證讀取或手動部署。建置 `.next-local-site-display-build`、2 workers／1536MB；3101正式驗證結束後回復原本development預覽，使用者3000與雷電不動。Git檢查會解壓顯示模型再掃描，避免壓縮隱藏私人值。
- 修正已推main **bade3c8**；使用者提供 [lr-fcz.vercel.app](https://lr-fcz.vercel.app/) 後，匿名核對GitHub的Vercel狀態由pending轉success，公開角色頁由「尚未開放」切換為圖鑑。**公開網站另16個桌面／手機案例全部通過**，角色詳情／前搖、裝備、公會100名單／十塔及PVP深層防禦連結／可見圖片皆正常，JS例外0、本機端點維持拒絕。`reports/site-display-deployed-ui.json`；重現 `python scripts/verify_site_display_ui.py --origin https://lr-fcz.vercel.app`。沒有使用登入憑證或操作Vercel部署工具，為既有Git自動部署。
- **仍未完成**：其餘98公會任意防禦入口、部分對手4座鎖定塔、20角色名稱／118未收錄詳情、本機完整技能解析與戰鬥觸發；PVP原403後暫停仍保留。正式網站採已驗證顯示版本，資料採集仍在本機；新資料需匯出／驗證／推送，沒有新增雲端遊戲自動更新。

## 最新：整體公會儲存盤點與 GitHub main（11/27）

- 使用者要求擴大檢查整個公會資料流程，前百防禦仍為目標。新增索引涵蓋 **211個Guild RTTI類別、77個完整公會相關路徑字串及85處原生引用**；這是索引範圍，不等於已反編譯所有211類別或驗證77個API。腳本 `scripts/ghidra/inventory_guild_storage.py`、`index_guild_request_routes.py` 均只讀既有模組，沒有auto-analysis、全程序掃描或新增遊戲請求。
- 實機核對 `GuildWarDataManager`：+18/+20為己方／對手Info，+28為Season，+50為5筆ReplayModel；+78/+80各10個整數key的CCArray，僅含每塔2／3／4個CCInteger。已由 `0133af3c → 0133fd94` 確認它們來自 `fortressCount`／`enemyFortressCount`，並非跨公會隊伍快取。`guild-runtime-storage-caches.json`；只讀8,748 bytes／81物件，未保存記憶體傾印。
- 另定位 `GuildDBContainer` global01fd7588／AP01e4b938。11個持有欄位皆已觀察型別，每個容器僅抽3個值；+30已由 `GuildRaidAiDB(01e4bc10) → 00f46f08 → virtual68/00f4a598` 連到guild_raid_stage_ai；+40由 `GuildWarFortressDB(01e4bf30) → 00f48ed0 → virtual88/00f4a638` 連到guild_war_fortress。另見簽到、徽章、出怪、172守護神模板、buff及戰場機制。戰鬥管理器global01fd6fe8目前為null。證據 `guild-template-storage-root-check.json`、`guild-battle-storage-root-check.json`、`ghidra/guild-db-storage-writer-proof-1242.txt`。
- 保存檔盤點限已知遊戲files/cache：淺層125檔、databases檔名9個，未讀資料列；已開啟檔案40個，.ldb在WebView儲存目錄，未讀內容。唯一Volley快取驗證格式後來源不是遊戲API，沒有讀回應標頭或body。找到2個.eson：448bytes副本與APK內建SHA完全相同；另7424bytes副本格式未驗證，尚無公會關聯，不把它宣稱可讀。副本與檔名細目留runtime.private；安全摘要見 `guild-existing-eson-format-check.json`、`guild-local-http-cache-check.json`。
- 公會列表／搜尋皆轉成GuildInfoModel；排名模型 `012a2814` 讀12個識別／排名／公會基本欄位，沒有角色或裝備。另確認 `/guild/confirm/${GID}` 是POST，但POST本身不足以判定用途；回應只向delegate傳狀態數字，沒有解析防禦。正常UI兩個尾端caller（01273f5c／012756fc）已讀；同一handler另呼叫 `/guild/${GID}/admission` 與 `/guild/admission/cancel/${GID}`，屬於入會／申請相關流程，沒有塔號或防禦回應，**未呼叫此POST**。不能用改名、猜參數或重試403補足前百。
- 外部公開Legend檔完整schema檢查已補完：50公會、2,417成員觀察、44,194個帶角色代碼物件，未見defense／fortress／tower／deck／groupType欄位。`guildwar`實際是numeric-key dictionary，不是假設的array；對照公開UI仍標進攻編隊，匯入防禦0。純統計見 `public-guildwar-reference-complete-schema.json`，沒有原始玩家資料；曾修正Counter把欄位值作計數的暫存輸出錯誤，已移除值，且reports從未提交Git。空group的精確數量未保留，不能由key總數推算成空隊伍。
- 整體盤點整理為 `reports/guild-all-storage-review.json`，目前定向反編譯31個不同函式，保留每份證據SHA與範圍。**真正防禦的已確認表示是伺服器回應 `guildWarDefenceDeckResponses[*].deckInfoJson`／deckId，原生模型為GuildWarMemberModel；尚未知道伺服器實際資料表名稱，也未建立任意前百GID讀取。** 前百仍完整1／部分1／未取得98；沒有新增公會防禦配置，不將31函式／211類別索引說成已解決全前百。
- 為補齊字串內嵌JSON的檢查缺口，針對已接受排名第一公會的正常profile／roster另做2個GET；完整走訪所有物件／陣列／可解析JSON字串，內嵌JSON 0、防禦候選0，沒有保存回應或讀玩家編隊。`guild-normal-embedded-schema-check.json`；新CLI `probe_guild_embedded_fields.py` 保持拒絕即停，Cookie僅RAM。一般圖鑑／詞條／資料庫未變更，沒有重跑未受影響的Next檢查。
- 受影響檢查：公開schema保留值／內嵌JSON／識別鍵／深度上限／憑證形狀等5項合成測試通過；6個新分析腳本編譯及實際離線索引／摘要執行通過。延用既有18項TS、9項Python、型別／lint／build及18個桌面／手機UI驗證；它們未受本段純研究／Git變更影響，不再重跑。沒有新增自動輪詢、遊戲寫入或部署。
- 後續一次正常main GET觀察沒有切換成排名第一公會，回應仍屬既存戰局；當時畫面仍6開放／4鎖定，沒有再抓同樣的塔。`guild-profile-to-war-context-check.json` 未追蹤遊戲背景請求，因此只記錄該次結果，不宣稱排除所有伺服器上下文切換。另讀4份外站公開管理／隊伍JS，個人隊伍清單仍為team1～5、pvpteam、guildwar，文字明標公會戰進攻，沒有建立十塔防禦來源；未呼叫外站管理API。
- 補查兩個LoadingUnit類別的共同parser `00f5f950`：response陣列建立0x8e8的UnitData、經00e48f30解析，放UnitManager global01fd41e8的virtual158 dictionary。這是原生預期consumer證據，**沒有把7424bytes副本當作已解碼，也沒有觀察該副本實際進入parser**；沒有重追加密根路徑。`loading-unit-native-consumer-check.json`。
- 使用者詢問Vercel環境變數：網站現行只需 `NEXT_PUBLIC_SUPABASE_URL`、`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`（Production／Preview）。SUPABASE_SECRET_KEY為本機同步工具用途，LR_LOCAL_DATABASE_PATH／LR_NEXT_DIST_DIR為本機用途，不需給Vercel；不要設定development來繞過來源限制。**正式角色／PVP／公會／詳細詞條與私有圖片讀取尚未接齊**，Supabase研究資料仍私有草稿，填環境變數不會讓它們自動上線。已在.env.example與README明確分開用途，沒有部署。
- **GitHub已開始版本控管並推至使用者指定的 [LR-FCZ/main](https://github.com/louis4843894/LR-FCZ/tree/main)**，初始提交 `81597ab`。遠端原為空，沒有force push；342個檔案／約5.3MB staged blob檢查未發現憑證值，環境範本金鑰欄位全空。排除研究副本、reports、本機資料庫、原始遊戲檔、帳號資料與完整記憶體；保留本機全部資料。README已反映角色／公會實際狀態，沒有部署或改依賴。

## 進行中：前100公會防禦入口、明確沒有與未知的校對（11/27）

- **使用者最新要求持續挖前100公會防禦，不能只抓自己的對手。尚未完成；目前前100為完整1、部分1、未取得98。** 已進入454期second_battle，不再等待23:00。`reports/guild-top100-defense-coverage.json` 逐公會保存真實狀態；不把公開進攻隊伍當防禦，不清除先前玩家編隊GET的403暫停。
- 正常可見對手 **にほーん（排名5，alias c0ae8c24042b277ceb3f）**：6座可讀、4座遊戲鎖定；12份防禦／240角色／720裝備，全實例+5。副本 `guildwar-main-20261126T153434Z-a46248`，部署source `guildwar-a8e3f93a10b51f10fdb1bd6e`；`opponent-visibility.private.json` 逐塔狀態0/3，僅讀allowedCodes的6座。正向驗證了既有擷取器，Cookie只在RAM、不附加、不出戰、不改隊伍。這份樣本不代表前百已完成。
- 新裝備還原source **guild-gear-rolls-4d603a306f5a42016210a144**。己方＋對手共740角色／2,219裝備＋1確認空位；9,883項一般／條件／Skill+值都有中文、未知數值0，145件特殊效果可顯示。舊己方500／1,499保持；新增對手3,162項值及37件特殊效果。全角色／裝備ID關聯成功，駐防成員37/37名單相符；實際觸發、適用條件及逐件目視仍未驗證。`validate_current_guildwar.py`已驗證。
- 入口證據：`0133c590`只帶seasonNo／battleNo／towerCode，唯一已分析直接caller `0132a808`；尚未建立指定任意GID的塔讀取流程。`00f91408`的0x0b是**保存編隊**，一般分支字串為 `/player/units/save/%s`，不呼叫POST。新唯讀Ghidra證據 `guild-top100-war-target-references-1242.txt`、`guild-top100-defense-save-boundary-1242.txt`；均768MB、單程序、-noanalysis/-readOnly，已結束，不開常駐掃描。
- 另讀指定網站**公開JS** `guild-read-interface-20261126T155357Z/guildwar-ranking.js`；其介面明標「公會戰進攻隊伍」，不能當防禦證據。沒有啟用其管理員模式、沒有登入或呼叫受限資料API。正式對戰期間另做排名1／5的正常profile與roster共4個GET及一次正常rank GET，防禦候選欄位均0；`guild-profile-battle-phase-check.json`、`guild-ranking-battle-phase-check.json`。這只排除這些回應，不能推論所有伺服器入口不存在。新方向繼續從防禦回應解析器與其真正讀取使用端查起，避免重追保存、進攻與已拒絕路線。
- **續查的實際結論**：已對已驗證模組的18,702,168-byte `.text` 做精確BL/B比對，補足既有targeted專案未建立的xref；三種塔GET仍只有控制器 `0132a808` 呼叫。`deckInfoJson` 的兩個實際字串使用端為自己的保存回應 `0133c6c8` 與塔內 `19GuildWarMemberModel` parser `013486b4`；該模型建構與解析均由 `0133bd38` 使用。重播 `0132adb8 → 013411ec` 需要已選駐防者、defUid／defGid／deckId及目前對戰上下文，沒有建立任意排名公會讀取。GET／header／dispatcher亦未找到另一個公會選擇欄位。唯讀證據 `guildwar-reader-callers.json`、`guild-defense-model-readers.json` 與 `ghidra/guild-*-transport-and-replay-model-1242.txt`／`guild-context-helpers-and-replay-caller-1242.txt`；不把直接引用檢查說成已排除所有間接路徑。
- 排名第一正常history兩次檢查只有公會raid及簽到事件；正常contribution一次回傳50筆名稱／等級／勝場／貢獻，無隊伍或裝備。報告中的 `guildWarContributionInfoList` 只是寬鬆候選鍵，**不是找到防禦**。公開原始碼 `mti0224/rangerbook` 的公會首頁及測試也明確使用進攻編隊，維護邊界明確排除backend；未啟用admin或嘗試受限API。整合證據與具體缺口集中 `reports/guild-top100-defense-entrypoint-audit.json`。前百仍1完整／1部分／98未取得，不能靠重開畫面或把進攻改名補齊。
- 11/27 00:28（台灣）僅重驗正常對手畫面狀態，仍開放11～16、鎖定21～23與31，沒有重新請求同一批塔。最新角色實例source為 `character-instances-e3b7b4526b1f9882c73dcf92`。新增公會覆蓋摘要桌面／手機2項UI驗證通過（`guild-top100-coverage-ui-validation.json`）；Ghidra與瀏覽器均已退出，只留3101預覽。package／lock與本輪修改前副本逐byte相同。
- 成功基準 `reports/availability-opponent-success-baseline.json`：54份程式／驗證檔封存且CRC通過；24份既有不可變輸入保留並記錄SHA，沒有複製7GB live DB、Cookie或整份記憶體。覆蓋狀態與研究入口報告均可離線重建；目前沒有新證據支持對其餘98公會發出塔請求，不重試403或批次猜端點。
- **模板比對已完成**：公開角色／能力／翻譯／裝備5份JSON與既有副本SHA完全相同。`reference-availability-audit.json`：2,287精準對照角色中無技能403、無能力547、無覺醒候選2,086、無才能1,984；原生全2,405角色才能另確認303有／2,102未設定。裝備953全部星等／類型相符；無高級效果576、無Skill+786、無Spec+918，改成「此裝備沒有…」，不再誤稱尚未解析。未收錄118仍未知，不稱全都缺少技能；空主技能欄位不足以證明全部技能不存在。20名稱仍未對照。
- 角色詳細parser v3將`availability`（present/absent/unknown）存入新不可變source **character-details-6ab288756e325c4c2b232624**；原基本模板SHA、1,884角色／3,081技能前搖及數值未改。省略欄位≠空陣列／null配置；模板沒有候選不代表玩家回應的未知能力，實例欄位保持原判定。頁面、圖鑑摘要及完成度已修正。TS18項、Python9項、型別、lint及2-worker production build通過；16個受影響桌面／手機UI案例通過，`availability-opponent-ui-validation.json`。
- **Supabase僅私有草稿且完整回讀**：角色 `characters-details-5a0a58e36518564466a41a97` 2,405列；公會 `guild-top100-22a806279b537ee678b66fe3` 107研究列（不是107公會；排名仍100公會）。舊版本及published保留、匿名封鎖，沒有部署。
- 記憶體盤點未見閒置LR程序可終止（不是宣稱釋放了幾GB）。新增 `.vscode/settings.json` 排除.next*/node_modules與大型raw/extracted/research/local資料的檔案監看及搜尋；不隱藏檔案、不關VSCode／OneDrive／雷電。建置以`CIRCLE_NODE_TOTAL=3`限制2 workers、Node1536MB；期間暫停預覽，已恢復唯一3101。最新dev session40863，dist `.next-local-character-guild-native-dev`；build `.next-local-availability-opponent-build`。package及lock未變。

```powershell
python scripts/audit_reference_availability.py --directory data/research/external-reference/availability-audit-20261126T121516Z-33c73c
python scripts/audit_guild_defense_coverage.py
python scripts/verify_availability_opponent_ui.py
# 下列均離線，不重試已排除或已拒絕的遊戲請求
python scripts/ghidra/find_guild_request_callers.py
python scripts/audit_guild_defense_entrypoints.py
python scripts/audit_guild_storage.py
```

## 最新：參考布局、全站深色樣式與可收合內容（11/26）

- PVP／公會戰使用共用 `DefenseTeamViewer`：桌面左側五欄角色卡＋三個裝備縮圖，右側選中角色的實際等級、雷納德、覺醒、才能及中文裝備詞條；手機改三欄與上下排列。支援放大 dialog、Escape／關閉、焦點復原、實際隊伍選單；切換隊伍清除舊選取。PVP A／B的選用／備用分開，不新增沒有資料的隊伍1～5；公會20位置不切成假隊伍。
- **長內容皆可收合**：角色清單、各隊、角色詳細欄、覺醒、才能、武器／防具／飾品；覺醒及裝備詞條預設收起，摘要保留中文名稱／星等／實際強化。公會成員各自收合，預設只開第一位駐防者；成員名單、排行表、統計各組、角色技能／能力／覺醒候選／才能及裝備模板效果也可收合。`CollapseControls` 提供區域內全部展開／收合，錨點會展開目標及祖先，不影響其他區域。
- 首頁、圖鑑、詳細頁、公會及PVP排行統一深色／青綠配色（`styles/dark-catalog.css`）。圖鑑改圖片卡片、進階篩選收合；查詢／分頁與資料來源不變。UI不顯示外站品牌，內部來源仍如實保留。未解析／未取得／確認空位保持區分，模板範圍與實際詞條分開。
- `defense-viewer-data.ts` 在server建立顯示白名單；角色／裝備實例ID、owner、原始階級及研究欄位不傳client。穩定顯示鍵以觀察／成員／隊伍／位置雜湊，重複模板仍是不同位置。PVP只補既有模板圖片、星等、屬性及原生才能的唯讀關聯，沒有重新擷取或改動快照。角色基本2,405、裝備953、公會500角色／1,499裝備的來源版本維持不變。無遊戲請求、無Supabase寫入、未部署、套件及lockfile未改。
- 修正新client邊界的Node／Chromium ICU空白差異：隊伍時間用臺灣時區formatToParts固定組字，避免hydration錯誤。卡片圖片固定容器比例，屬性按原生小寫代碼正規化顯示；星數保留真實值，才能角標明示階段，不冒充未知的遊戲皇冠標記。覺醒用通用圖形，尚無已驗證能力圖示映射。
- 檢查：4個受影響TS檔 **16項**、typecheck／lint／production build通過，`reports/defense-viewer-engineering.json`。PVP10位置／90項已知值、公會20位置／260項已知值，逐位置對照實例、部位、強化、星等、才能；桌面1440／手機390各一次。完整UI結果集中 `reports/defense-viewer-ui-validation.json`；最初全站配色通過副本 `defense-viewer-theme-validation.json`，後續只重驗受變更或可見性疑慮影響的案例。截圖必須等可見的h1及導覽列，避免將串流隱藏DOM當作已顯示頁面；不改圖片loading屬性。
- 本機仍 **http://127.0.0.1:3101**，既有dev `.next-local-character-guild-native-dev`；最新build `.next-local-defense-viewer-build`。Next僅增加此dist的tsconfig型別路徑，其他既有路徑保留。修改前備份 `data/research/runtime.private/baselines/team-viewer-before-20261126T112710Z`；成功基準見 `reports/defense-viewer-success-baseline.json`。
- **未完成與優先序不變**：其他99公會真實防禦等待今晚23:00正常可見的對手塔；之前不輪詢。PVP擷取仍放最後且403暫停保留。20角色中文名、118角色完整詳細資料、部分實例詞條／實際觸發、覺醒圖示映射及原始.db解密仍未知；本輪UI完成不代表這些資料已取得。

```powershell
python scripts/verify_defense_viewer_ui.py
python scripts/verify_defense_viewer_engineering.py
# 只重驗受影響項目可使用 --only；--resume保留同資料版本已通過的其他案例
python scripts/verify_defense_viewer_ui.py --resume --only pvp-team-viewer,guild-team-viewer
```

## 最新：角色完整本機圖片、原生才能四階段與最新公會防禦（11/26）

- **優先順序：角色 → 公會防禦 → 最後才PVP。使用者告知對手防禦要等今晚23:00；之前不再查詢／輪詢對手，待正常對手畫面可見再接續。** 本輪沒有PVP擷取請求，也沒有更新PVP雲端草稿；原403後暫停保留。
- 角色基本模板仍 **2,405筆**（本輪新增基本角色0筆），原始基本文件／星等SHA保持不變。新增 **2,405／2,405本機角色圖片**：重用73張APK圖，從正常遊戲快取 `/sdcard/Android/data/com.linecorp.LGRGS/files/.res` 批次複製精準ID對應的2,332張PNG；沒有從圖檔名推斷角色欄位，也沒有下載或熱連結外站圖片。Native 00f00998以UnitManager查角色，virtual+50／00c14694取得UnitData+50代碼，傳0194709c組 `.res/%s/%s-thum.png`；原生程式證明路徑映射。逐檔PNG chunk／CRC／尺寸／SHA驗證，73張重用圖也與目前遊戲快取SHA一致。縮圖副本 `character-thumbnails-20261126T104341Z-8a37dc`，公開端點只回驗證過的PNG，不回研究檔或檔案路徑。
- **303角色的才能群組及四階段順序已有原生證據**：UnitManager+98的100筆UnitTalentData（size58、AP01e36240）、+a0的84組UnitTalentGroupData（size48、AP01e362c8）完整null_tail擷取。來源 `character-talent-definitions-20261126T102941Z-013341`。角色群組代碼UnitData+668，getter00c15958／virtual830；talentGrade在+680，getter00c15990／virtual840。00e5e798按群組代碼查a0，00e62820按四階段索引查定義，**00e5fa60從index0至talentGrade-1累加已達階段的強化值**。不夾到maxTalentGrade，也不把模板當成已解鎖。83個已使用主要才能的能力代碼／敘述取本機lang_unit；16種強化值按float32與已確認參考值逐項相符，中文效果標籤保留user-confirmed-reference來源。100定義中99筆被這303角色使用，未引用定義保留；99筆敘述皆齊且沒有未替換placeholder。
- 原生補充source **character-native-36bbf554d74b8600044c82c8**，新表 **character_native_sources／current_character_native_sources／character_native_details**，scope=native-templates。2,102角色的群組欄位觀察為空，標not_configured；不是把缺定義補空。`build_character_native_details.py`只讀保存的模板／才能／圖片副本，核對既有角色版本、翻譯及參考manifest雜湊，SQLite2,405列全部重建相同，未改寫原verified-characters.json。原技能／能力詳細source仍e8a85c830912cfe533627e18（1,884角色／3,081技能含前搖），並非重新原生解析整份技能表。
- 已重新取得 **復仇者總動員十塔10／10、25真人、500角色、1,499裝備＋1確認空位**；來源 `guildwar-main-20261126T100529Z-4195c5`，部署source **guildwar-e7d3f2899485c867b9ee5fa9**，完成時間 **2026-11-26 18:05:41臺灣**。25／25成員相符、角色及裝備ID未知0，裝備皆實例+5。一般／條件／Skill+6,721項數值已重新按新觀察ID重建，另108件特殊效果有中文數值；裝備觸發與條件是否生效仍未驗證。新的裝備source **guild-gear-rolls-829fcd0b5d28c27b81d759db**；角色實例source **character-instances-4d33bdcc861356fac88bb29b**。
- 公會500角色的等級／雷納德／才能階段關聯全部維持正確，**500／500有本機圖片；321個位置有才能群組，共515個已達階段**。頁面逐階標示「已達階段／尚未解鎖／階段未知」並顯示中文內容，發動條件及實際戰鬥觸發另計，不再次套用倍率到面板。另20角色個人儲存設定仍不當作已部署。角色圖鑑新增本機縮圖及原生四階段對照；公會角色卡同步，圖片缺少時仍有替代圖與基本資料。
- 其他公會：本次正常 `/guildwar/main` 回應仍為454期second_standby，enemyGuildInfo及enemyFortressCount為null。**沒有因此取得銀刀等其他99公會的防禦**。已補好 `guildwar_visible_towers.py` 與collector前置檢查：0132a808依manager+60（virtualf8）==1才走0133c590的opponent GET；01364d10遇FortressLayer+16c（virtual3f8）==3會拒絕普通入口。擷取器只走實際GuildWarMainController可見節點、核對21GuildWarFortressLayer／FortressModel+170及塔碼，排除隱藏／鎖定／未知狀態，並在每塔請求前重驗場景、父節點可見性與塔狀態。可部分成功，未讀取塔不當空塔，不覆蓋前次完整資料。現場只驗證到「current_opponent_model_not_loaded」且0HTTP；**對手正常畫面的正向驗證留待23:00**，未繞過鎖定或存取限制。
- 網站驗收：角色頁與列表、本機圖片端點、桌面1440／手機390、公會第1塔40角色的圖片與每個才能階段，共7案例通過，無JS例外／水平溢出／原始欄位外洩。時間差異僅Node ICU使用U+2009而Edge使用一般空白；驗收比對完整日期與秒數並正規化Unicode空白。驗收腳本不再修改圖片loading DOM，避免干擾React hydration。`reports/character-guild-native-ui-validation.json`，兩張手機圖已目視檢查。
- 公會頁只將目前塔的隊伍交給顯示元件，十塔計數與全公會總數照舊：元件模型 **8,572,566 → 969,480 bytes**，HTML內容大小相同801,689 bytes。測試涵蓋未讀取／確認空塔／未顯示塔的數量，不把減少傳遞內容改成沒有駐防。`guild-render-profile*.json`。本機development冷載入仍曾超過60秒，暖機純HTTP量測17.5秒；資料讀取約0.3秒、純React渲染約0.7秒，開發模式整體延遲未完全消除。此大型頁驗收單獨容許180秒協定等待，其他腳本預設60秒保持。沒有升級框架或改相關除錯設定。
- **Supabase完整回讀**：角色私有草稿 `characters-details-4f842d9d682572a0743f0381` **2,405筆**（18:51:05臺灣），公會私有草稿 `guild-top100-71cc9a13ee73440e859577bd` **105筆**（18:51:19）。保存圖片雜湊／尺寸及才能關聯白名單，不上傳本機路徑、PNG原始檔、帳號憑證或記憶體副本。主要才能本機翻譯、強化中文對照來源分開保留。舊草稿／published均保留、匿名仍封鎖；暫不部署。
- Python12項（角色原生3、公會來源7、可見塔2）、TS5檔16項、typecheck／lint／production build通過。build `.next-local-character-guild-native-build`；本機3101用 `.next-local-character-guild-native-dev`（exec session87662）。`reports/character-guild-native-engineering.json`。package.json及lockfile與本輪前相同。Ghidra只對直接相關函式做-noanalysis反編譯，專案已保存，不存在仍在跑的分析任務。
- 本輪前備份 `character-guild-before-20261126T102519Z`；最新成功基準見 `reports/character-guild-native-success-baseline.json`，只封存角色／公會必要副本、圖片及精選SQLite輸入，不複製7GB live DB或PVP實例。**剩餘：20角色中文名稱（目前翻譯表SHA與已保存副本相同，未重抓）、118角色完整技能／能力詳情、本機完整技能數值與戰鬥觸發；其他99公會的真實防禦待正常可見來源。PVP與原始.db解密留後續。**

```powershell
# 純離線重建角色補充與圖片；不需要遊戲登入工作階段
python scripts/build_character_native_details.py --capture data/research/runtime.private/character-talent-definitions-20261126T102941Z-013341 --thumbnails data/research/runtime.private/character-thumbnails-20261126T104341Z-8a37dc --apply
python scripts/validate_current_guildwar.py
python scripts/verify_character_guild_native_ui.py
python scripts/save_character_guild_native_baseline.py
# 只有23:00後遊戲正常開啟可見對手塔，才執行以下擷取；拒絕／鎖定即停止
python scripts/runtime/collect_guildwar_http.py --use-authorized-runtime-session --capture-towers --side opponent
# 有新塔觀察後才離線更新數值與私有草稿，不因純頁面重整重新請求
python scripts/derive_guildwar_gear_values.py --apply
python scripts/sync_guild_rankings_supabase.py --apply
```

## 最新：全部已對照技能前搖、PVP／公會角色實例資料（11/26）

- **技能前搖：1,884角色／3,081技能，全部已補齊**。沿用已保存角色對照；另取得公開動畫索引 `data/research/external-reference/character-startup-20261126`（2,897個unit ID），比對怪獸8號、熊大、潔西卡及特殊段落角色u1216e-towa的4個獨立動畫副本。頁面ranger.js以skillSet順序對應startup.skill_1／skill_2.seconds；時間單位為秒。3,059筆為s_attack_ready／s2_attack_ready，另22筆為索引標記的s_action_attack_1；後者已取實體副本核對，沒有因段落名稱不同丟棄。保留原始秒數、frames、segment及hash，畫面顯示小數2位。這是動畫索引定義的前搖，不是實測命中時間；不含投射物飛行，也未套入戰鬥速度變化。數值來源仍是user-confirmed-reference，沒有改稱本機原生解析。
- 角色詳細新source **character-details-e8a85c830912cfe533627e18**；本機基本2,405模板與SHA未變。未對照的118模板仍維持未知。`build_character_details.py --startup ...`、`character_skill_startup.py`可純離線重建；`validate_character_details.py`逐列比對已通過。各版原始副本與上一版source保留。
- **PVP／公會角色實例：已加入實際等級、實際等級上限、雷納德點數、才能階段、實際覺醒的中文名稱與敘述**。來源分別是同一角色物件的unitLevel、playerUnitMaxLevel、leonardPoint、talentGrade、awakeAbilityCode；沒有取maxLevel／maxLeonardPoint／maxTalentGrade補值。原生12.4.2既有證據 `reports/ghidra/version1242-unit-fields-annotated.txt`：leonardPoint傳virtual+b28、talentGrade傳+848，awakeAbilityCode／Icon／Category交給00e538f4。未跑Ghidra、未重新擷取、未呼叫遊戲HTTP或讀工作階段。
- 新增SQLite **character_instance_sources／current_character_instance_sources／character_instance_progress**，scope=accepted-defense，source **character-instances-8d610c3776a119b61b64d13f**。`scripts/character_instance_progress.py --apply --validate`只讀已接受來源副本，逐筆驗證玩家、來源、隊伍、位置、角色模板、實例ID與採集時間；以玩家命名範圍雜湊綁定實例。新版本另存，未改寫原防禦紀錄或裝備詞條。
- 覆蓋：全部保存PVP歷史 **18,187個角色位置紀錄**（同一實例在不同時間／隊伍可重複，不是唯一角色數），四個數值欄位均有；實際覺醒14,468筆有ID且中文全部對上、3,719筆來源未提供。另345個舊原生位置紀錄缺HTTP副本，沒有跨時間硬接。**目前接受排行榜的2,135隊／10,566角色位置，10,566筆全部關聯成功**；9,051筆有實際覺醒，1,515筆未提供。此筆數以當前SQLite重算，先前2,127隊是較早報告，未因此重新採集。
- 公會駐防 **500／500角色**有等級／上限／點數／才能階段；**421筆覺醒ID全數中文對照，79筆未提供**。另20角色的個人儲存設定單獨處理（14筆覺醒），不計入500部署數。來源仍為復仇者總動員10塔／25真人／1,499裝備及1空位；不是新增其他公會防禦。採集時間保留原值：駐防2026-11-26 07:34:39–07:34:49臺灣；PVP逐隊時間另列，不能把本次補欄位時間稱為新抓取時間。
- 網站共用CharacterInstancePanel，PVP及公會皆顯示上述實例欄位；0點／第0階是實際值，缺少欄位不補0。缺少awakeAbilityCode標「來源未提供」，明確空字串另為「來源回傳空值」，不拿awakeYn或模板候選填入。才能只顯示實際階段，模板才能說明仍在角色詳細頁；**尚未證明各階段啟用效果／倍率，沒有把整份模板當作已解鎖**。覺醒中文採本機lang_unit，不輸出帳號／角色實例ID、原始物件、sourceFile或內部hash到新顯示欄位。
- 後續一般PVP批次流程 `update_local_game_data.py`、公會十塔成功採集 `collect_guildwar_http.py` 已接入同一離線補欄位流程，每批完成後更新一次，不逐名重新快照。原始副本快取上限8份；前端按觀察key分批查詢，查詢500筆約17ms，公會資料組裝約274ms（`reports/character-read-profile.json`，單次本機量測，不是效能保證）。**PVP自動採集仍維持403後暫停，未解除拒絕存取保護**。
- **Supabase全讀回成功**：角色 `characters-details-a1beba05b942d574ef3d127f` 2,405筆（17:46:13臺灣）；PVP `pvp-ranked-0a08c9e6af1af903915b5334` 3,231筆（17:36:46）；公會 `guild-top100-dd467abbb060b3f5202b59fa` 105筆（17:37:03）。新草稿含角色實例白名單，舊草稿／published保留、匿名仍封鎖；不是部署。沒有遊戲Cookie或raw memory上傳。
- 驗證：Python新增5項＋角色詳細7項＋拒絕後停止1項＋自動更新4項通過；TS相關5檔16項、typecheck／lint／最後production build通過。build `.next-local-character-instances-build`，`reports/character-instance-build-validation.json`。桌面1440／手機390共8案例通過（PVP各10角色、公會第1塔各40角色，以及一般／特殊動畫前搖）；新增22筆後僅重驗受影響前搖，PVP／公會4案例依來源ID與程式hash未變沿用。無JS例外、無水平溢出，已目視檢查兩張手機截圖；這是網站對副本核對，不冒充遊戲逐件目視確認。報告 `character-instance-validation.json`、`character-instance-ui-validation.json`。
- 開發服務仍在 **http://127.0.0.1:3101**，新dist `.next-local-character-instances-dev`（exec session92962）。舊dev曾出現公會頁60秒CDP逾時／HTTP113秒；資料讀取量測<0.3秒，僅重啟已驗證屬於LR的3101程序後全部案例通過，根因未獨立證實。沒有升級Next或依賴；package.json／lockfile hash與變更前一致，Next自動新增tsconfig的dist types項保留。
- 變更前副本 `data/research/runtime.private/baselines/character-instance-before-20261126T091734Z`；本輪成功基準見 `reports/character-instance-success-baseline.json`，含精準來源副本壓縮檔、接受的防禦文件、解析版本與程式，不複製7GB live DB。**未完成：來源未提供的實際覺醒、才能階段→實際啟用效果、戰鬥修正後前搖；118角色完整詳細資料／圖片映射；其他99公會防禦、PVP未涵蓋裝備詞條分支與觸發判定、原始.db解密。此輪無需使用者操作。**

```powershell
# 純離線；沿用已保存副本
python scripts/build_character_details.py --reference data/research/external-reference/character-details-20261126T082045Z --startup data/research/external-reference/character-startup-20261126 --apply
python scripts/validate_character_details.py
python scripts/character_instance_progress.py --apply --validate
python scripts/verify_character_instance_ui.py
# 只重驗前搖：須已有來源／程式版本未變的成功實例畫面驗證
python scripts/verify_character_instance_ui.py --startup-only
# 需要另存新雲端草稿時才執行，保留舊版
python scripts/sync_character_details_supabase.py --apply
python scripts/sync_pvp_rankings_supabase.py --apply
python scripts/sync_guild_rankings_supabase.py --apply
python scripts/save_character_instance_baseline.py
```

## 最新：角色詳細資料、技能／能力／覺醒候選／才能（11/26）

- 本輪依使用者指定的 Rangerbook 公開角色頁對照，將「鳩興能力」按頁面用語「覺醒能力」實作。**2,405筆本機基本模板與星等保持不變**；其中 **2,287筆** 通過角色ID、星等、類型、屬性及已知主技能／主要能力ID的關聯檢查，0衝突。另118筆無完整對照，保留原角色及未知；沒有把34筆僅存在參考資料的角色新增成原生角色，也不從ID推定素材／NPC用途。
- 詳細覆蓋：**1,884角色／3,081技能／8,509技能效果；1,740角色／2,458能力項目；201角色／655覺醒候選；303角色有才能**。技能顯示係數、持續時間、範圍、機率、冷卻、觸發基準、效果個別機率與上限、活動關卡／守護神適用；能力顯示時機、場合、條件與效果。等級公式保持公式，不代入猜測玩家等級。全部3,081技能的中文敘述用本機lang_unit；數值結構保留user-confirmed-reference來源，**不是原生數值解析成果**。
- 新公開來源副本 `data/research/external-reference/character-details-20261126T082045Z`：rangers.json／abilities.json／official-locales.json／custom-locales.json及公開載入器／頁面。v2-data.js證明公開/res/v2/{name}.json路徑；角色頁有動態base=/ranger/，不可直接依/ranger/ranger/解相對腳本。最新rangers內容hash與舊副本相同；不必重抓。`datasets-source.json`保存URL、取得時間、檔案hash及ETag。未登入對照站或存取管理區，未讀遊戲Cookie／帳號資料、未跑Ghidra或重新擷取角色。
- 本機新增版本表 **character_detail_sources／current_character_details／character_template_details**，scope=`native-matched-reference`，source=`character-details-d8948abdaedffc8810c9ef40`。各角色內容在`character_template_details.payload`的skills／abilities／awakeningAbilities／talents／stats；118筆status=`not_in_reference`，上述詳細欄位為null，與已核對模板的空陣列分開。資料有原始翻譯hash、來源manifest hash、關聯證據及欄位來源。基本資料仍是current_documents的verified-characters.json，SHA **82bb54a1f8ab3bf328a3f36e558bb76c62ac5bb5a2e902e49cff53e7fc03e082**，未覆寫。
- 覺醒是模板候選，不是玩家實際覺醒結果；候選chancePercent的語意尚未確認，僅留本機研究層，**沒有當作能力發動率或上傳**。能力自身triggerEffects.chancePercent另有顯示。才能亦不冒充已解鎖／培養階段。stats保留模板基準值，等級基準未獨立確認；不代入玩家裝備、成長或戰鬥最終數值。
- 網站沿用既有架構：`getCharacterReference`只載入基本資料與輕量詳細索引；`getCharacterDetail`只取所選角色詳細列，走`publicCharacterDetails`白名單。列表新增技能／能力／覺醒候選／才能篩選，詳細頁有五個區塊與跳轉；技能及能力ID移至折疊的進階資訊。沒有外站品牌、外站熱連結、登入鎖或研究原始副本。資料狀態頁同步顯示各項覆蓋數。
- 修正角色版本判斷：SQLite的payload是canonical JSON，但current_documents.sha256保留原始檔hash；不可重新hash回傳字串當成原始檔版本。新增`readCharacterTemplateDocument`同一查詢取得payload與已接受hash，再限制詳細來源需同版本。已加回歸測試；資料過期時維持基本資料可用，詳細欄位不錯接。
- 驗證：離線重建與SQLite逐列相符，基本版本未變；新增Python7項、TS6項通過，另相關既有資料關聯測試通過。typecheck／lint／production build通過；build `.next-local-character-details-build`。Edge桌面1440／手機390共7案例通過：怪獸8號／熊大／潔西卡、未知與已知空技能分開、201角色覺醒篩選、數值／名稱／數量／白名單、無溢出與JS例外；覺醒機率最終文案另驗。報告`character-detail-validation.json`、`character-detail-ui-validation.json`。本機3101現用`.next-local-character-details-dev-final`；曾遇到舊模組匯出與文案快取，已只重啟LR服務，未升級依賴或部署。
- **Supabase新私有草稿 `characters-details-463b085e59cd6be948035004`，2,405筆全部回讀一致（2026-11-26 16:51:10臺灣）**；本機基本資料時間與參考核對時間分開，舊版本／published保留，匿名仍封鎖。`reports/character-details-supabase-receipt.json`。新快照normalized_record.templateDetails保存白名單詳細內容，fieldSources明確區分本機基本資料／對照數值；沒有候選原始機率、帳號／憑證或原始記憶體。
- 變更前備份 `data/research/runtime.private/baselines/character-details-before-20261126T083050Z`；最新成功基準見 `reports/character-details-success-baseline.json`（複製輸入可離線重建各筆紀錄）。**未完成：118角色完整詳細資料、角色圖片映射、玩家實際覺醒／培養與裝備後戰鬥數值、本機完整技能數值解析。銀刀等其他99公會防禦、PVP未涵蓋詞條分支、裝備觸發／重複判定及原始.db解密亦未在本輪處理。**

```powershell
# 全離線，沿用已保存資料；不需要遊戲或登入工作階段
python scripts/build_character_details.py --reference data/research/external-reference/character-details-20261126T082045Z --apply
python scripts/validate_character_details.py
python scripts/verify_character_details_ui.py
python scripts/sync_character_details_supabase.py --apply
```

## 最新：108件駐塔特化效果已辨認及還原（11/26，優先於下方舊章節）

- 裝備優先階段已完成：原有 **6,721筆普通／條件／Skill+駐塔詞條不變**，另 **108件駐塔裝備／19種特化效果** 已有本機繁中名稱、一般加成及才能描述的實例數值；原先顯示未知的這108件已補齊。個人設定另9件／6種，部署仍未確認，不混入駐塔數。不是全遊戲所有詞條或戰鬥機制已完成。
- 新限定副本 `data/research/runtime.private/gear-option-definitions-20261126T074130Z-3b58f8`：GearDB+68的36個才能群組共71筆 `GearTalentAttributeData`（AP01e994e0），+70的35筆 `GearSpecialOptionData`（AP01e995f0）；null_tail、前後一致，沒有讀憑證。`read_gear_option_definitions.py`／`parse_gear_option_definitions.py` 可重現；已入SQLite既有gear_special_definition_sources，current_gear_special_definitions scope=`native-option-talents`，source=`gear-options-1308b125e4b88e061c97cde6`。才能群組key為equipTalentCode，陣列順序必須保留，不能按rootAbilityCode合併。
- 實例來源：012193fc讀 `specialOptionCode`、`specialOptionAttrValueGrade`、`specialOptionTalentValueGrade`、`currentSpecialEnchant`；特化定義與GearStat+70關聯由01231bd4保存。0122e270還原一般加成；0122e690依才能陣列建立buff/subBuff索引與特化強化增量；0122c704把 `{$3p}`／`{$4f}` 等依原生索引轉成百分比／秒。一般加成走0122f11c的特化分支（百分比一位小數、非百分比整數），不能套0122f510的其他顯示模式。無普通+5倍率或maxEnchant fallback。報告 `reports/ghidra/gear-special-option-*1242.txt`，舊 `actual-attribute-core-1242.txt` 及 `guild-gear-conditional-json-and-skill-render-1242.txt` 已沿用，未重跑完整分析。
- 現用還原source **`guild-gear-rolls-b517089a7d9f651ad26b43ef`**；保留舊source與原始觀察。新結果在 `gear_instance_rolls.payload.supplementarySpecial`，包含name／normalText／description／specialEnhancement、原始參數與定義證據。原始參數只留本機研究層，前端只收到白名單中文與顯示必要值。未知輸入仍未知；觸發條件、activeProbability的實際戰鬥套用、重複特化優先順序及逐件遊戲目視仍未確認。外部模板參考來源標記未更改。
- 校驗：585次實際分級／特化強化的浮點結果與系統C函式fmaf逐位一致；舊 **6,993筆** 數值（駐塔6,721＋個人設定272）逐筆不變，117筆特化紀錄皆無未替換的顯示參數。`reports/guildwar-special-option-validation.json`。樣本：咒語壓制為降低傷害+20.6%、指定敵人技能閃避減少30.0%；鼓舞可見爆擊傷害+82.2%、增益技能條件下爆擊傷害增加87.8%，均來自各自實例，不互相補值。
- 本機頁面1／6／10塔，1440／390寬全通過：特化中文、全部該塔特化描述與實例值逐項對照、強化分離、觸發未知說明、模板參考、識別白名單、無溢出，JS例外0。`reports/guildwar-special-option-ui-validation.json`，截圖 `runtime.private/browser-ui/guildwar-options-acceptance/`。Python相關12項、TS三檔13項、typecheck／lint／production build通過；build `.next-local-guildwar-options-build`。舊dev曾造成CDP逾時，已只重啟確認屬於LR的3101服務並完成重驗；現用 `.next-local-guildwar-options-dev`，未升級依賴、未部署。
- **Supabase新私有草稿 `guild-top100-e8fd48491af5e370a2225865`**，105筆全部回讀一致（2026-11-26 16:06:21臺灣）；包含中文特化實例結果，舊版本／published保留，匿名封鎖。`reports/guild-top100-supabase-receipt.json`。未上傳Cookie、原始識別、分級原始參數或記憶體。
- 銀刀分支保留在 `reports/silver-guild-defense-investigation.json`：新增確認0133bc78是 `/guildwar/form/fortress/%d` 的GET，與保存POST0133b66c不同；0132a808只在register狀態使用，數字來自FortressModel+18塔code，未建立任意公會ID參數。history只有historyType與字串data[]。修正native_elf.py錯把覆寫過的ADRP／ADD當字串引用，3項回歸已通過。
- 使用者已開自己的十塔；**2026-11-26 16:08:36只讀確認**：正確GuildWarMainController、season454、狀態4=second_standby，己方不是銀刀西郎，opponentModel尚未載入。`reports/guildwar-visible-context-status.json`，0 HTTP請求、未讀Cookie。使用者表示今晚公會戰開始後可正常看對手十塔；目前沒有新增其他公會防禦。先前公開隊伍403批次維持停止，公開guildwar仍是出戰用途。
- 變更前檔案備份 `data/research/runtime.private/baselines/gear-options-20261126T074547Z`；舊成功基準 `guildwar-values-20261126T071141Z` 保留。最新成功凍結路徑見 `reports/guildwar-values-success-baseline.json`。**尚未完成：銀刀及其他99公會真正防禦、戰鬥觸發／重複特化判定與遊戲逐件目視、PVP尚未涵蓋的詞條分支、角色圖片／技能細節、原始.db解密。**

```powershell
# 使用已保存副本；無需重新擷取玩家或讀取登入工作階段
python scripts/parse_gear_option_definitions.py --capture data/research/runtime.private/gear-option-definitions-20261126T074130Z-3b58f8 --apply
python scripts/derive_guildwar_gear_values.py --apply
python scripts/validate_gear_option_values.py
python scripts/validate_current_guildwar.py
python scripts/verify_guildwar_ui.py
python scripts/sync_guild_rankings_supabase.py --apply
```

## 最新：公會6,721筆詞條還原、排行公會來源驗證與403中止（11/26，優先於下方章節）

- 復仇者總動員原有十塔仍為 **25人／500角色／1,499裝備＋1空部位**，不是本輪重新採集的配置。**6,721筆普通／條件／Skill+詞條全部有中文及原生還原數值**：普通4,497、條件1,381、Skill+843。另有 **108件裝備** 的specialOption／talent欄位仍未解析，不能把「6,721已還原」當成所有特殊能力完成。來源 `guild-gear-rolls-b8082cf3e6b7c0f231750e27`；未確認部署的個人設定另272詞條，不混入十塔。條件適用／技能觸發、逐件目視及角色技能最終值尚未確認。
- `scripts/derive_guildwar_gear_values.py --apply`／`native_gear_special_values.py` 操作已保存副本；SQLite沿用gear_roll_sources/current_gear_rolls/gear_instance_rolls，scope=`guildwar`，數值在payload.entries[*].value/unit。綁定source/tower/owner/team/position/slot及實例雜湊、模板、強化、grade；不改原始觀察。額外未知欄位保存在payload.supplementarySpecial.rawFields，前端只取得未知狀態，不取得原始研究副本。
- **Supabase私有草稿 `guild-top100-6b9c8f0af941cd49a90ed7a0`，105筆完整回讀（2026-11-26 15:02:39臺灣）**。包含6,721個已還原值、中文Skill+描述及額外特殊未知標示；舊版本／published保留，匿名仍無法讀取。`reports/guild-top100-supabase-receipt.json`。未上傳Cookie、原始記憶體或原始帳號識別。
- 新限定擷取副本 `gear-special-definitions-20261126T055850Z-24068b`：GearDB+48／AP01e4af18 `20EquipmentUnlimitData` 1,001筆，+58／AP01e993a8 `17GearSkillPlusData` 104筆；`gear-special-definitions-20261126T061703Z-b71900`：+50／AP01e99258 `24GearSkillPlusUpgradeData` 515筆。皆null_tail、前後一致，不讀憑證。`parse_gear_special_definitions.py` 已接受 `gear-special-e51584ca5a0ca5764233f3e1` 及 `gear-special-51d75b8c7c3f6f2f832dcef4`；gear_special_definition_sources/current_gear_special_definitions分ordinary-special與skill-upgrades兩scope。
- 條件計算0122dde4：GearData+e0（virtual1e8/0121c758；currentAdvancedEnchant），累加level=0..該強化的00f451d8回傳，加grade插值，沒有普通+5倍率。查GearDB+48，key由00f4296c `%s%s%u`（uppercase selector＋種類code＋level）建立，EquipmentUnlimitData+4c float增量。特殊selector保留適用狀態未知。指令亦證明缺key回float0，不是解碼器自行補預設值。
- Skill+：012193fc→0122dab4→0122d81c保存實際ID／grade，再0122a97c以獨立字串ID字典取定義。0122ed7c依實際Skill+ ID（**不使用attrNumberGroup**）、grade、currentSkillPlusEnchant逐級累加+50表；0122f11c原生operator表為空／+／-／+／-，type3乘100，targetFactor=SUB為秒。01230e34以 `SKILL_PLUS_%d_nm` 連本機lang_equip繁中。頁面顯示「技能追加參數變化」，保留描述的N，**不將變化量當成角色原技能最終值**。來源／指令報告guild-skillplus-*與guild-gear-conditional-*。
- 公會頁保持1～10塔、中文裝備名、實例強化、模板參考分離；條件與Skill+強化各別標示，108件特殊效果顯示尚未解析。`validate_current_guildwar.py`通過，未知模板ID 0；新增Python解析／拒絕／候選隔離與TS數值相關測試通過，typecheck/lint/build通過。**最終隔離瀏覽器第1/6/10塔（1440／390寬）全通過**，含實例數值逐項比對、中文Skill+、108件特殊未知提示、無私有識別外洩及版面溢出，JS例外0；`reports/guildwar-ui-validation.json`。本機dev3101，build `.next-local-guildwar-values-build`，未部署。依賴hash未變；Next只自動加新build types至tsconfig。
- 使用者要求從排行榜繼續挖：已正常進公會戰排行第1「銀刀西郎」→成員→玩家。正常GET `015eab84` `/player/units/team/equip/uid/<UID>` 確實帶guildwar20角色／60裝備，保存一名副本 `ranked-guild-war-group-20261126T063426Z-1a9498`。**用途已明確排除防禦**：00f96454把guildwar映成 **0x0c出戰群組**，01328cac消費該群組後呼叫battle/enter；真正defencedeck回應0133c6c8載入 **0x0b**，公開回應沒有該防禦群組。未把0x0c、一般隊伍或PVP當防禦，沒有猜guildId／uid查塔端點。證據 `reports/guildwar-ranked-public-defense-boundary.json`、`guildwar-public-group-defense-link-1242.txt`。
- 同時間本人公開群組與savedDefense：20角色實例相同但位置只2處相同，裝備58對60；另兩名既有駐塔玩家也不同。不是可互換的部署來源；比較副本與結果 `reports/guildwar-public-group-purpose-comparison.json`。新增比較器曾把unit/gear map解包錯位，已修正、完全以既存副本離線重算，並加回歸測試，不重抓。
- 使用者同意先抓供其核對後，新增 `collect_guild_public_formations.py`，最多2worker／每秒2次、6小時快取、逐人保存／續接。已將1名成功副本存入 **獨立** guild_public_formation_sources/current_guild_public_formations，purpose=`guildwar_attack_formation`、defenseVerified=false、towerCode=null。第一名公會其餘49人批次最先兩個正常GET均 **HTTP403**，於 **2026-11-26 15:01:08** 停止，未繼續其他人；已加previous_refusal_requires_manual_access_review，重跑亦不讀session／不發請求。拒絕前只保存1人20角色／60裝備，**新增其他公會已驗證防禦仍0／99公會未完成**。不要直接重跑／清除拒絕狀態／換身分，需正常可見來源或明確解除的存取狀態證據。
- 使用者用於核對的白名單中文檔 `reports/guild-public-formation-review.json`，含角色／裝備模板中文、實際強化，不含帳號、角色／裝備實例識別或憑證；明確標出戰用途，不是塔內防禦。未接成正式防禦頁、未拿來算PVP或公會防禦統計。
- 其他來源：目前454／second_standby總覽無對手；排行點入他公會後main仍回自己公會。013411ec replay/list是帶已選對戰deck的POST、battle/enter是狀態POST，未呼叫；contribution GID來自manager+18；新125bf98 `/guild/battle/user/list` GET沒有guildId參數，未發請求。未取得跨公會十塔入口。
- 所有Ghidra程序已結束，均-noanalysis，未附加／注入或改遊戲。0122b35c本輪誤設已移除並恢復真實unwind範圍0122b340..0122b36c，報告已標該區塊無效；後續每個dec參數均先核對function_start。
- 變更前備份 `data/research/runtime.private/baselines/guild-values-20261126T054434Z`；成功基準 **`data/research/runtime.private/baselines/guildwar-values-20261126T071141Z`**。已用選定資料表的frozen SQLite離線重建，sourceId與6,721值逐筆結果一致；`reports/guildwar-values-success-baseline.json`。原始副本保留，不複製整個live DB／整份記憶體。既有953裝備／2,405角色／PVP current與歷史保留；PVP自動擷取維持先前403後暫停，未自行恢復。**未完成：其他99公會真正防禦、108件特殊效果／才能數值、條件／技能觸發及逐件目視、角色圖片／技能細節、原始.db解密。**

```powershell
# 全離線，使用已保存成功副本；不需再擷取裝備或登入
python scripts/derive_guildwar_gear_values.py --apply
python scripts/validate_current_guildwar.py
python scripts/verify_guildwar_ui.py
python scripts/export_guild_formation_review.py
# 使用者已授權的既有私有雲端草稿，保留舊版本
python scripts/sync_guild_rankings_supabase.py --apply
```

## 最新完成：黃金以上十個分階及原生裝備數值（本節最優先，11/26）

- 使用者最新指定：只取傳奇、大師1／2／3、鑽石1／2／3、黃金1／2／3；不再取白銀、青銅。共用政策 `data/config/pvp-scope-policy.json`，舊低階來源完整保留，僅移除 current 指標；舊「大師／鑽石／黃金」正名為各自3階。`scripts/apply_pvp_scope_policy.py`、`lib/pvp-scopes.ts`。範圍／未知階級不可 fallback 成傳奇。
- `0174f3dc` 明確以 SSO 即時常數建立14階陣列；MASTER／GOLD的1、2不在rodata完整字串，先前只讀六組表因此漏掉。`reports/ghidra/pvp-subdivision-ui-and-gear-manager.txt`。已沿原正常GET驗證十個回應各自回傳正確phase：傳奇200、大師1 86，其餘八階各100，共1,086筆排名。防禦全部接續取得，current已十階。DNS曾中斷於鑽石2，已恢復；`--resume-staged` 重用完成五階及50筆快取，不從頭重抓。後續每階獨立驗證後啟用，失敗階不覆蓋舊資料。
- **驗收快照2026-11-26 13:13（臺灣）**：1,086名不同玩家，**1,028完整、53部分、5未提供**；1,081名有隊伍、**2,127隊、31,382件裝備**、142,066個效果識別。**31,382／31,382裝備模板對應；未知裝備及角色ID均0**。這是該次驗收數量，持續更新後可變。`reports/pvp-gold-equipment-validation.json`、`reports/pvp-chinese-label-coverage.json`。
- 新全域定義副本 `data/research/runtime.private/gear-definitions-20261126T042612Z-04ee0f`：2,744筆，null tail、無循環／錯誤、前後一致。真正來源是 **GearDBContainer** `00c30fdc → global01fd58c0 / AP01e4af90 → virtual78 / 00f45ab0 → +38`，不是GearManager的巢狀字典。最初錯誤候選在型別檢查立即停止，未匯入。來源 `gear-definitions-8eaaa993a255a0ccf64545a1`，新SQLite `gear_definition_sources/current_gear_definitions/gear_definition_records`。全遊戲完整性仍未知。
- 中文對照擴為 **2,744 ID**，`gear-labels-7737130ca92897c187870135`；34個既有裝備副本＋1個全域定義容器，6,878個物件證據、衝突0。Supabase `equipment-native-labels-616117f4bced3e6a9f14603b` 2,744筆回讀完成。現有十階122,583個詞條種類已中文；19,483個Skill+等種類仍未知，不混用命名範圍。
- 已交叉核對舊4,134個非零ID物件的種類／steps／min／max：4,134一致，差異0。`scripts/derive_http_gear_values.py` 以原兩件裝備6個畫面值校準、2,953個普通物件分支作證，再加入下述通用載入證據，已還原 **94,101個實際普通值**；**47,965個數值維持未知**，其中45個是超出目前驗證分級。另存 `gear-rolls-fd532e508bf928a2919fa646`，原觀察不改；SQLite `gear_roll_sources/current_gear_rolls/gear_instance_rolls`，數值在 `gear_instance_rolls.payload.entries[*].value / unit`。舊2,952個原生數值完整保留。factor時間與觀察／最近核對時間分別記錄，不把模板範圍當實例值、不重複乘強化。
- 數值版已存入 **Supabase私有草稿 `pvp-ranked-af4949f2ed66b18951569ca4`，3,223筆完整回讀**（10排行＋1,086玩家＋2,127隊），包含94,101個普通還原值；`ranger_research_records.normalized_record.members[*].equipment[部位].actualEffects[*]` 中的 `value / unit / valueSource` 區分還原來源。舊published及所有版本保留，匿名讀取仍被阻擋，沒有上傳Cookie或原始記憶體。`reports/pvp-rankings-supabase-receipt.json`。
- 網站已接嚴格的實例綁定還原層：owner範圍雜湊、snapshot、角色位置、部位、裝備實例、模板、強化、grade與效果ID／分級全部吻合才顯示值；舊已驗證數值優先。Skill+、特殊依賴、selector條件與超出已驗證分級保留未知。`lib/gear-instance-values.ts`、`lib/defense-teams.ts`、`lib/pvp-rankings.ts`。沒有把還原值標為新玩家已目視核對。
- 為減少重工，原生校準依定義來源／34個immutable manifest SHA／演算法版本快取；PVP更新結尾自動重建還原層再同步雲端。保留 `--resume-staged` 手動續抓。PVP每10分鐘排程已恢復啟用，worker有40分鐘上限、Windows工作45分鐘上限，IgnoreNew及原限速／拒絕暫停保留；不保證十階每10分鐘全部完成。
- 一個候選位址0122dd04實際位於ELF unwind函式0122db78～0122dde4內，該反編譯報告已標INVALID，未用作證據；已用 `RestoreVerifiedFunctionRange.java` 僅移除本輪誤建目標並恢復正確函式區間。所有Ghidra均-noanalysis，單程序順序操作，無LIAPP附加／改遊戲檔／依賴升級／部署。
- 通用關聯已確立：`01226b44` 呼叫 `012193fc` 解析裝備JSON、逐項呼叫 **01226f08**；後者以GearStat virtual48取attrNo，經 **00f44fdc → GearDBContainer+38字典objectForKey(long)** 複製種類、steps、min/max及selector至實例，再走 `0122dde4 / 0122f510` 普通計算／格式分支。證據 `gear-manager-attribute-resolution-1242.txt`、`gear-definition-lookup-and-skillplus-1242.txt`。因此已擴至全域容器中全部有證據支持的普通分支；未套用條件／特殊／Skill+分支。不要重追UI函式01218340或GearManager+38外層字典。
- 驗收：Python25項相關解析／範圍／保留／拒絕／還原測試、TS4檔12項通過；typecheck、lint、production build通過。隔離Edge桌面1440與手機390寬度：十階選單、排除白銀而不誤顯傳奇、大師1獨立頁面、實際3個值逐項對資料庫、模板範圍分離、未知保留、無溢出／JS例外均通過。`reports/pvp-gold-values-ui-validation.json`；原中文／舊數值案例 `reports/pvp-chinese-ui-validation.json` 亦通過。導覽驗證器改等實際loaderId，避免同網址換尺寸時誤讀上一份DOM。沒有部署或依賴變更。
- PVP排程已於13:13實際開始新一輪，僅黃金以上；更新中的遊戲／HTTP工作階段仍只留本機記憶體。續接基準 `reports/pvp-gold-equipment-success-baseline.json` 保存本次驗收版本，避免live current持續改變導致無法重現。

```powershell
# 沿用既有副本，不需重新擷取／解密原始.db
python scripts/parse_gear_definitions.py --capture data/research/runtime.private/gear-definitions-20261126T042612Z-04ee0f --apply
python scripts/build_native_gear_labels.py --apply
python scripts/derive_http_gear_values.py --apply
python scripts/validate_pvp_gold_equipment.py
python scripts/verify_pvp_gold_ui.py
# 正常更新黃金以上；若剛中斷，可加 --resume-staged 重用完成分階
python scripts/update_local_game_data.py --module pvp --capture --scope all --use-authorized-runtime-session --sync-supabase
python scripts/pvp_auto_update.py --status
```

本機 `http://127.0.0.1:3101/pvp`。**仍未完成**：47,965個特殊／條件／Skill+等數值（含45個分級未驗證），其中19,483個Skill+等種類仍未知；公會防禦尚未接此PVP還原層，其他99公會防禦仍受正常可見來源限制；角色圖片／技能細節、原始.db解密與全遊戲完整性仍未完成。Skill+來源已定位 `0122a97c → GearDBContainer virtual+b8 / 00f45bf0 → +58` 的字串ID字典（`%d`，17GearSkillPlusData），尚未擷取及驗證其定義／實際計算；不借普通ID對照補值。公會／角色本輪未重抓，不需使用者額外操作。

## 最新完成：PVP 中文詞條、六段位實際更新及自動／手動更新（11/26，本節最優先）

- PVP 防禦改用中文裝備卡，與裝備頁共用名稱、星等、圖示及可展開的模板效果／條件／範圍。一般詞條優先顯示已驗證的中文種類；未知項目顯示「種類尚未解析」，數值未知顯示「數值尚未解析」。原始裝備／效果 ID 與代號收進預設關閉的進階資料。模板範圍未填入實際詞條，歷史已確認數值不重複乘強化。
- 新增原生名稱來源 `gear-labels-0302d083820111b8ca60b1a8`：沿用34份成功副本，驗證4,134個0x78 GearStat物件的SHA／vtable／邊界；ID +0x18、種類 +0x1c，與 `0122f924`／`0085611c` 的種類表、`GEAR_FILTER_%s_nm` 和本機繁中翻譯關聯，得到 **253個普通屬性ID對照、衝突0**。沒有新擷取、Ghidra分析或推算數值。`skillPlusAttr1No` 屬不同命名範圍，不套普通屬性ID。
- SQLite：`gear_attribute_label_sources` 保存來源／證據、`current_gear_attribute_labels` 選用普通詞條來源、`gear_attribute_labels.attribute_id / type_enum / code / label` 保存對照。白名單輸出不含原始記憶體、帳號識別或憑證。
- 中文名稱來源已存入 Supabase 私有草稿 **`equipment-native-labels-04c06766f8e58c86ca3efcfa`，253筆完整回讀**；既有裝備模板／外部參考／published版本保留。`reports/native-gear-labels-supabase-receipt.json`。

### 本次真正更新的排名／防禦

- **2026-11-26 11:03:23～11:16:02（臺灣）**，以已授權、僅存記憶體的現有工作階段完成六個已確認段位的正常排行／防禦請求；未操作登入、朋友、出戰或配置。傳奇200＋大師／鑽石／黃金／白銀／青銅各100，共700名玩家：**613完整、56部分、31未提供**，共 **1,292組隊伍、18,477件裝備、504個已確認空裝備部位**。這些是新時間點的配置，與上一版數量不同不代表舊資料消失。
- 最新80,345筆詞條中 **68,415筆可顯示原生中文種類、11,930筆種類未知**；未知包含9,970筆技能追加、1,960筆普通種類尚無對照。新HTTP來源的實際數值仍為0，沒有以中文種類或模板範圍冒充數值；所有歷史來源的 **2,952筆已確認數值仍保留**。`reports/pvp-chinese-label-coverage.json`。
- 新PVP Supabase私有草稿 **`pvp-ranked-d63d4db08d6d169e95a9133f`，1,998筆完整回讀**（6排行來源＋700玩家＋1,292隊伍），原始UID以範圍別名輸出，舊版本／published保留。`reports/pvp-rankings-supabase-receipt.json`。
- 公會資料沒有重抓或變更，仍是100公會／4,751成員，復仇者總動員10塔／25人／500角色／1,499裝備；其他99公會防禦仍未取得。裝備953／角色2,405基本資料未變。

### 已啟用的更新與驗收

- Windows本機工作 **`LR-Local-PVP-Auto-10min`** 已註冊啟用，每10分鐘嘗試一次；沿用快取、最多兩個worker／每秒兩次、程序鎖與資料驗證。單輪加雲端保存本次約13分鐘，正在執行時略過重複啟動，並非保證每10分鐘完成700人。只有有效遊戲工作階段可讀，不自動登入或保存Cookie。
- `/pvp`、玩家防禦及 `/data-status` 有更新狀態與「立即更新PVP」。固定本機工作由限定localhost／同來源／開發模式的 `/api/local-updates/pvp` 啟動；瀏覽器每10秒僅讀狀態，不直接請求遊戲。重整頁面不會觸發採集。收到拒絕／限流、身分不符或格式改變時暫停自動請求，保留原有效版本；不猜新端點、不繞過保護。
- Python新增8項、TS相關4檔9項及既有排名6項通過；typecheck、lint、production build通過。隔離Edge實測1440／390寬度，中文種類、模板範圍、進階代號收合、未知數值、歷史已確認數值、更新狀態及無私有玩家ID外洩均通過，無橫向溢出／JS例外。`reports/pvp-chinese-ui-validation.json`。實測修正Next內部localhost與瀏覽器127.0.0.1別名差異；更新中正常POST回202／already_running、跨來源回403，沒有額外啟動遊戲擷取。`reports/pvp-local-update-api-validation.json`。沒有部署或依賴變更。
- 成功腳本／新增標籤資料表的增量基準見 `reports/pvp-chinese-success-baseline.json`，沿用父基準，避免再次複製整份大型資料庫。現有原始副本與舊版本保留。

```powershell
# 使用既有副本重建中文種類（不連裝置、不推算數值）
python scripts/build_native_gear_labels.py --apply
python scripts/validate_pvp_chinese_labels.py
python scripts/verify_pvp_chinese_ui.py
# 查目前自動工作；停用不刪資料
python scripts/pvp_auto_update.py --status
python scripts/pvp_auto_update.py --disable
# 僅在自行確認拒絕／登入或格式問題已解除後，明確恢復
python scripts/pvp_auto_update.py --enable --resume
# 正常立即更新也可用網站按鈕；執行時不重複啟動
schtasks.exe /Run /TN LR-Local-PVP-Auto-10min
# 沿用既有雲端私有草稿流程
python scripts/sync_native_gear_labels_supabase.py --apply
```

本機頁面 `http://127.0.0.1:3101/pvp`。**仍未完成**：11,930筆詞條種類與新HTTP來源實際數值／單位／技能追加關聯、其他99公會防禦、角色圖片映射與技能細節、其他子段位覆蓋、原始.db解密與全遊戲完整性。其他公會的正常可見性限制沿用下節證據，不再重試已被排除的路徑。本次不需使用者額外操作。

## 最新完成：公會裝備中文卡、遊戲第1～10塔與其他公會來源查證（11/26，本節最優先）

- 公會防禦現在共用 `equipmentName` 與 `EquipmentReferencePanel`，顯示裝備繁中名稱、星等、本機圖示及可展開的中文模板效果／條件／範圍；圖示仍標示對應待確認。連往裝備頁時帶入相同強化參考等級。原始裝備及效果 ID 收在「原始識別資料（進階）」中，預設畫面不再顯示代號。
- 本批1,499件裝備使用221種模板；**221／221有繁中語系名稱、221／221可接原裝備頁的模板效果**。其中 `[GA]3R`、`[GA]The Ripper` 本來就是遊戲繁中表原文，沒有自行編造中文名。實際詞條數值仍未知，模板範圍未冒充實際值，也沒有再次套用強化至實際詞條。
- 塔號已改成 **第1～10塔**：11～16→1～6，21～23→7～9，31→10。證據：`01340bec` 讀取 `00858314` 的0～9索引，`01362abc` 呼叫字串格式化時明確傳入 index+1；遊戲畫面 MY第6塔亦與原始myFortressCode=16相符。`reports/guildwar-tower-number-evidence.json`。未知代碼維持「塔號尚未確認」，不能套用原生表的預設0當成第1塔。
- 塔按鈕與成員防禦連結使用 `?tower=1`～`10`；舊 `?tower=11`／`31` 連結仍能正確解析。原生代碼繼續保存在來源／SQLite作精確關聯，不改遊戲檔。

### 其他公會：本輪實際查證結果

1. `0133adc0` 確有 `/guildwar/main?status=%s&seasonNo=%d`。僅以已保存、同公會／同454期的第一場來源參數進行正常GET，請求 `first_battle`，伺服器仍回 **454／second_standby**，沒有歷史對手。未將這份回應誤存為第一場、未發出對手塔請求。診斷只存欄位形狀、期別／狀態及雜湊，Cookie不落檔。
2. 正常讀取排名第1的「銀刀西郎」公開公會及50人成員名單，精確核對guild身分，沒有塔位／公會戰防禦裝備欄位；`useTeamNo` 未證明防禦用途，不套成駐防。沒有從公會名單抓PVP。`reports/guild-other-public-structure-check.json`。
3. `01359730 → 0132a950 → 0133b66c` 的成員UID清單路徑是 `/guildwar/form/fortress/%d`；`01058b84 → 01a4be64(mode=1)` 是保存配置，**未呼叫**。
4. `01364d10` 在FortressLayer狀態=3時直接顯示「破壞前一層一半以上的要塞後才可確認防禦隊伍陣容」，不發出正常檢視通知。擷取器不以main計數陣列推定對手塔已解鎖；正常可見性尚未確認的對手塔明確跳過。沒有繞過塔鎖定／存取限制。

**其他99個排名公會防禦仍未取得，沒有新增其他公會防禦資料。**本輪新增的是可重現來源查證及界面，不是宣稱全公會擷取完成。研究結果集中 `reports/guildwar-labels-crossguild-validation.json`；歷史來源若日後可讀，較舊場次也不得覆蓋較新的有效戰局，已加入測試。

### 保存、驗收與續接

- 原公會戰資料與前次成功基準逐表完全一致：sources6、current4、裝備實例觀察1,559、fetch attempts101；原駐防仍是10塔／25人／500角色／1,499裝備。沒有新增遊戲資料，故未重新上傳或覆寫Supabase；原105筆已驗證私有草稿保留。
- Python7項解析／保存＋4項HTTP範圍，TS3檔9項通過；typecheck、lint、production build通過。瀏覽器驗證第1、6、10塔（桌面／手機），中文名稱逐頁核對裝備詳細頁一致；另確認展開效果不溢出、原裝備頁+5等級切換仍可用，JS例外0。`reports/guildwar-ui-validation.json`、`reports/guildwar-chinese-card-ui-validation.json`。
- 沿用原Next/Ghidra與依賴，沒有auto-analysis、LIAPP附加、POST、登入／隊伍變更或部署。所有定向Ghidra程序已保存／關閉。新程式版本及證據索引 `reports/guildwar-labels-success-baseline.json`，父資料基準沿用，不重複複製大型資料庫。專案仍無.git；保留使用者與先前成果。
- 本機可看 `http://127.0.0.1:3101/guild/2e32a9c4273f4fa8871b?tower=6`。驗證指令：`python scripts/verify_guildwar_ui.py`；來源查證輔助：`collect_guildwar_http.py --use-authorized-runtime-session --previous-context data/research/runtime.private/guildwar-bootstrap-20261125T142824Z-e3cf3c --side opponent`，目前只會記錄回傳狀態不符並停止，不能宣告取得舊對手。
- 仍未完成：其他99公會防禦、實際詞條數值／特殊效果、角色圖片與技能細節、PVP常駐更新、其他子段位涵蓋及.db解密。此次不需使用者再操作遊戲。

## 最新成功基準：復仇者總動員十塔防禦（2026-11-26，本節優先）

使用者已切換帳號並確認十塔畫面開啟。上一輪因自動核准用量失敗而未執行的讀取已恢復；沒有繞過核准。遊戲一度回到 15% 載入，之後玩家模型正常建立，直接以已授權工作階段做正常 GET，沒有操作登入／朋友／出戰／儲存配置。LF_AC 僅留在 Python 記憶體，未落檔或上傳。

### 本輪實際成果

- **復仇者總動員（原排名第 16）：第 454 期、第 2 場，10／10 座塔、25 位真人、25 份防禦、500 個角色、1,499 件裝備；另 1 個確認未穿戴部位。**取得於台灣時間 **2026-11-26 07:34:39～07:34:49**，狀態 `second_standby`。是正常塔回應中的配置，未標為逐件目視核對。25／25 成員與已保存名單精確關聯，500／500 角色、1,499／1,499 裝備模板對應；未知模板 ID 均 0。
- 1,499 件裝備的 `unitInvenId` 均與該角色 `invenId` 相符；`currentEnchant` 實例欄位此次均為 **+5**，不是 maxEnchant／fallback。取得 **6,721** 個實例效果 ID／原始階級，**新數值還原 0**。詞條數值、單位、強化計入方式及特殊條件仍未知，網站不拿模板範圍補值。
- 舊的個人已儲存設定另存：20 角色、60 裝備、272 效果識別。沒有與本次部署資料合併計數，也未以模板相似推定這份舊設定的部署。合計新子系統保存 1,559 筆裝備觀察；實際駐防部分為 1,499。
- 原始白名單副本：`data/research/runtime.private/guildwar-main-20261125T233439Z-71ffb8/`，包含 main 與 10 份 `tower-ally-*.private.json`。只保留塔、防禦成員及角色／裝備分支，不存活動紀錄、頭像網址、Cookie、玩家升級等無關內容。先前 `guildwar-bootstrap-20261125T142824Z-e3cf3c` 原樣保留。
- SQLite 新增 `guild_war_sources`、`current_guild_war_sources`、`guild_war_equipment_instances`，並記錄原始採集時間的 `guild_fetch_attempts`；重複匯入不複製裝備實例。來源不可變、部分更新不覆蓋完整舊防禦。角色／裝備實例識別均依玩家範圍處理。
- **Supabase 私有草稿 `guild-top100-48728c6272532d99429a28f8`：105 筆研究紀錄全部讀回一致**，內含 100 公會／4,751 成員與本次 25 份防禦、500 角色、1,499 裝備及獨立舊設定。原生玩家／公會識別去識別化；沒有上傳原始回應、Cookie 或記憶體。舊 published／所有版本保留，未部署。

### 正常程式路徑與可見範圍

`0133c388 / 0133c590` 唯讀 GET `/guildwar/fortress/{ally|opponent}/{seasonNo}/{battleNo}/{towerCode}`。接收者 AP `01eb5c00` 的 +0x48 是 `013451d0 -> this+0x28`，實際為 `GuildWarSeasonModel`（建構子 `01349e6c`、AP `01eb62a0`）。+0x28 getter `0134a9f8` 讀 seasonNo +0x18；+0x38 getter `0134aa08` 讀狀態 +0x1c，`0134a7c0` 解析字串，`0133c470` 換算場次。塔代碼僅取本次 main 的 fortressCount／enemyFortressCount 鍵。

此次 `result.guildWarDefenceDeckResponses[]` 直接給 fortressCode、mergedGuildPlayer.gid／uid、deckInfoJson.playerUnitTeams；20 角色的 slot 實際為 0～19，沒有套用 PVP 的五槽假設。資料來源證據 `reports/guildwar-normal-source-proof.json`、定向反編譯 `reports/ghidra/guildwar-season-*.txt`。沿用 12.4.2 SHA `1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0`，Ghidra 已保存並關閉，始終 -noanalysis。

**目前僅完成前100公會中的 1 個防禦；其他 99 個未取得。**已知讀塔路徑沒有任意 guild ID 參數，只能讀現有帳號當期己方／對手戰局；本次 main 在第二場準備階段沒有對手資料，所以未取對手塔。保留的對手第1場舊總覽只有識別，不算防禦成功。不猜跨公會端點、不換 UID、不把名單／PVP 防禦充作公會戰。前100排名及100份完整名單／4,751成員已完成並保留。

### 網站、更新與重現

`/guild/2e32a9c4273f4fa8871b` 已有十塔切換、25 位成員到塔的連結、每位 20 角色及三部位實際裝備／強化、角色／裝備圖鑑連結。每次只顯示所選塔，避免一次渲染全部 500 角色。個人已儲存設定獨立摺疊；未知塔／空塔／空部位／未讀分開。模板範圍仍只在裝備圖鑑顯示，不冒充實例數值。無登入門檻、外站品牌或原生帳號識別輸出。

```powershell
# 直接重新讀本帳號正常可見戰局；目前為約10秒的十塔批次，非逐頁擷取
python scripts/runtime/collect_guildwar_http.py --use-authorized-runtime-session --capture-towers
# 重現既有成果，不需要遊戲／Cookie／網路
python scripts/guild_war_database.py --capture data/research/runtime.private/guildwar-main-20261125T233439Z-71ffb8
python scripts/validate_current_guildwar.py
# 原統一公會入口已接當期戰局；排名／名單維持每週二12:00快取規則
python scripts/update_local_game_data.py --module guild --capture --if-due --use-authorized-runtime-session --sync-supabase
# 僅同步已解析白名單到私有草稿，不發布
python scripts/sync_guild_rankings_supabase.py --apply
# 本機頁面
$env:LR_NEXT_DIST_DIR='.next-local-guildwar-dev'
npm.cmd run dev -- --hostname 127.0.0.1 --port 3101
```

原週二排程動作不需改動：統一入口現在會附帶嘗試本帳號當期可見戰局；不宣稱可取得全部100公會。無有效遊戲工作階段時保留舊資料，不自動登入。PVP 六段位 700 玩家／1,288隊／18,499裝備與原953裝備／2,405角色成果未重抓或覆寫。

### 驗證與仍未完成

新來源已逐欄離線重建、核對全部裝備／角色與成員關聯；新表 quick_check=ok、外鍵錯誤0。`reports/guildwar-current-validation.json`。公會戰解析／保留完整舊版6項、HTTP範圍3項、TS相關測試、typecheck／lint／build與本機頁面驗證均以本輪結果記錄。`reports/guildwar-ui-validation.json` 桌面／手機2案例全通過；公會列表、舊對手未知防禦、另一公會名單與完成度4案例回歸通過。沒有重跑完整Ghidra或未受影響全套資料檢查，沒有依賴升級。

本輪成功程式版本、新增資料表一致性副本與來源 SHA 索引保存在 `reports/guildwar-success-baseline.json`；既有完整 PVP／公會成功基準沿用，未重複複製整份大型資料庫。開發預覽：`http://127.0.0.1:3101`，本輪程序 session 94558。package.json／package-lock.json SHA 與前次成功基準一致；Next 僅追加兩組輸出型別路徑。

仍未完成：**其他99公會塔內防禦／裝備**（缺正常跨公會讀取來源）、新HTTP效果的實際數值／Skill+／特殊條件、角色圖片／技能細節、成員顯示等級換算、PVP常駐更新與其他子段位涵蓋、.db解密及全遊戲完整性。此次擷取已成功，無需使用者再切換或儲存隊伍；下方「待開十塔」是舊歷史狀態。

## 最新成功基準：查詢介面與公會前 100 名（本節優先）

### 本輪授權與操作限制

使用者要求對照 Rangerbook 的介面，前台不出現外站來源，網站先不加登入／付費限制。已移除外站名稱、網址及來源說明；既有模板範圍與實例數值仍分開，後端來源證據／外部來源類別完全保留，沒有改稱本機解析。

使用者本輪已明確授權：「**同意，僅限本機讀取正常可見的公會資料**」，允許現有 LF_AC 僅在本機記憶體讀公會前 100 名、名單及正常可見十塔；拒絕存取即停止，不保存／上傳 Cookie。此授權已擴充下方舊 PVP-only 範圍，不需重問。最初自動審查拒絕時已停止，取得上述明確授權後才執行。

**待使用者操作：**使用者說進公會戰需等他切換帳號，尚未收到「十塔已開」。已提出一次完整需求：切換至已報名且正常能看公會戰的帳號，開啟「公會戰 → 十塔總覽」保持開啟；不用出戰、儲存／改隊伍。不得自行切帳號或操作戰鬥。名單已取得，等待期間不再碰遊戲畫面。

### 已完成的真實公會資料

- **前 100 名：100／100 公會，完整名單 100 份、4,751 位成員、部分／失敗均 0。**實際正常遊戲回應：gradeId=1 提供第 1～50 名；gradeId=2 提供第 51～200 名，只取其第 51～100 名。沒有合成排名或拿站外公會數字補值。回應 observedTotal=5,111。
- 本機排行 ID `guild-ranking-219f70dcfa60fbf49b2c5101`。新增 `guild_rank_sources / current_guild_rankings / guild_ranking_checks / guild_roster_sources / current_ranked_guild_rosters / guild_fetch_attempts`，保留每個公會來源與獨立時間／失敗。舊裝備、角色、防禦、舊公會正常化文件 SHA 與前次基準完全一致。
- 正常請求：`012a386c -> GET /guildwar/rank/total?gradeId=%d`；`012a4db4` 使用同 selector+1 組 `GUILD_LEVEL_TITLE_%d`，本機翻譯 1=傳奇、2=大師。`0125386c -> GET /guild/${GID}`；`01259a0c -> GET /guild/${GID}/member/list`（GET helper `0105a004`）。GID 精確核對，成員 gid 相同且 uid 不重複；無畫面逐頁擷取。
- 200 個正常 GET（100 公會各 profile＋roster），最多兩 worker／每秒兩次開始，批次 **100.797 秒**。每份只保存公開公會／名單白名單，不保存 guildPlayer、最後上線、幫助／入會紀錄等無關欄位。副本 `runtime.private/ranked-guild-*/guild-response.private.json`。
- 離線 `scripts/validate_current_guilds.py` 已對 100 份來源逐欄重核、驗證來源 SHA、名單邊界與擁有者；新資料表 quick_check=ok、外鍵錯誤 0。`reports/guild-top100-source-validation.json`。
- 角色名單 API 等級原始值 50～532 已保存在後端；尚未證明畫面階級換算，前台不直接當成顯示等級。職位實際值 MASTER／SUBMASTER／NORMAL 對到會長／副會長／成員，其他值維持未知。
- Supabase 私有草稿 **`guild-top100-eb42a2a63b872f6dd19fe4d1`**：101 筆（1 份排名＋100 份公會／名單，內含 4,751 成員），全數讀回一致、保留 published／所有舊版本。原生公會及成員 ID 已依公會範圍去識別化，不含 Cookie／整份記憶體。`reports/guild-top100-supabase-receipt.json`。網站頁面沒有登入門檻，資料庫安全設定未放寬。

### 介面與更新流程

- 新首頁、白色側欄／青綠色系、手機收合選單、篩選器、排名表格；`/gear`、`/characters`、`/pvp`、`/guild` 與 `/guild/[guildAlias]` 已接現有資料。公會排名、段位／名稱／排名搜尋、100 份成員列表可直接查看。未知十塔配置明列尚未取得，不拿 PVP 隊伍代替。
- 裝備效果頁顯示「模板可能範圍」，實際穿戴仍讀實例；未還原詞條保持未知。移除來源說明不等於將來源改稱原生。裝備圖示目前僅依 asset filename 對映，保留「圖示對應待確認」狀態；角色圖片／技能細節仍缺。
- `collect_guild_rankings_http.py` 沿用已接受且本週有效名單；失敗／部分項目可續抓，完整舊名單不會被新部分結果清空。排行內容不變時另存核對時間；週界以台灣週二 12:00 計算。統一入口已接正常請求，`collection_targets.guild='公會前100名'`；PVP 仍為 rankings，不從公會名單擴抓 PVP。
- Windows `LR-Local-Guild-Tuesday-Noon` 已核對為 Ready，下一次 **2026-12-01 12:00 Asia/Taipei**。僅把已知舊擷取動作更新成 `--module guild --capture --if-due --use-authorized-runtime-session --sync-supabase`，保留其他觸發器／設定。現階段排程更新排名及名單；十塔未取得，不能宣稱已排程抓全部防禦。仍需遊戲正常工作階段，失敗保留舊資料；不自動登入。
- dev **session 46903／127.0.0.1:3101**，輸出 `.next-local-ui-guild-dev`；舊 session 33572 已關閉。舊 HMR 導致首頁讀不到新增匯出，乾淨重啟後已通過。Next 開發指示器關閉、agentUpgrade=false 保留，未升級依賴。package.json／lockfile 與本輪前備份 SHA 一致。只追加 Next 自己需要的 tsconfig 輸出型別路徑。
- Vitest 增加 `vitest.config.mjs`，只收 `tests/**/*.test.ts`，避免保存的成功腳本副本被誤當測試重跑；備份未刪。

```powershell
# 每週／按需直接更新前100名；--force 可強制刷新
python scripts/update_local_game_data.py --module guild --capture --if-due --use-authorized-runtime-session --sync-supabase
# 離線重核全部公會
python scripts/validate_current_guilds.py
# 本機整體介面驗收
python scripts/verify_catalog_ui.py
```

### 公會戰防禦目前界線

**目前 0 份十塔防禦，不能宣告已取得前 100 名的裝備。**已準備 `scripts/runtime/probe_guildwar_normal.py --use-authorized-runtime-session`，僅在使用者確認十塔已開後執行。它先核對載入模組／版本，再唯讀取得正常 `/guildwar/main` 及 GET `/guildwar/defencedeck` 的 JSON 邊界；不儲存未審閱完整回應或 Cookie。確認資料形狀後再白名單擷取戰局／塔／駐防及裝備，不能猜參數。

- GET main：`0133adc0 / 0133af3c`；GET saved deck：`0133c678`。沒有證據證明它可任意帶他公會 GID 查防禦。
- **不得呼叫 POST defencedeck：**`00f91408` 的其他 mode 使用 `/player/units/save/%s`，mode 0xb 改為 POST `/guildwar/defencedeck`；`00f916bc` 檢查 `result.success`，這是保存路徑，並非擷取端點。
- `/guildwar/fortress/ally/%d/%d/%d` 與 opponent 對應 `0133c388 / 0133c590`，參數來自實際載入戰局，不能將排名 GID 直接代入。需先取得正常可見戰局，才知道可查看公會範圍。
- 定向 Ghidra 專案已保存／關閉，始終 -noanalysis，沒有修改原始遊戲檔。證據 `reports/ghidra/guildwar-main-normal-read.txt`、`guildwar-defence-deck-callers-and-parser.txt`、`guild-top100-detail-and-tower-requests.txt`。

### 驗收與尚未完成

- Python 公會解析／儲存、權限範圍、唯讀 GET／拒絕保存路徑及既有 HTTP transport 共 9 項通過。TS 4 檔 21 項通過；typecheck、lint、production build 通過。Edge 整體 13 案例通過，另 2 個首頁／手機導覽受影響案例重核；無 JS 例外、橫向溢出、外站品牌／連結、內部公會／成員 ID 或登入門檻。`reports/catalog-guild-ui-validation.json`、`catalog-guild-ui-focused-validation.json`。
- 保存新公會子系統一致性 SQLite 與 37 份程式／文檔版本，沿用前次完整資料庫基準，不重複複製無變更的全部歷史資料。索引 `reports/guild-ui-success-baseline.json`。原始副本、既有 5 筆裝備成功基準、953／2,405／700 玩家成果均保留，未部署。
- **仍未完成：**前100公會十塔駐防／裝備（待使用者切帳號開十塔且需驗證可見範圍）、成員顯示等級換算、新 HTTP 實際詞條數值／特殊效果、角色圖片／技能細節、PVP 常駐更新、其他子段位涵蓋、本機 .db 解密及全遊戲完整性。

## 最新成功基準：六段位正常 HTTPS 更新，停止逐頁擷取（11/25）

本節優先於後面的舊紀錄。使用者已授權「僅限本機使用現有工作階段」取得正常可見排行及玩家 PVP 防禦，並要求加入大師、鑽石、黃金、白銀。Cookie／解密參數只在 Python 記憶體，不存檔、不輸出、不上傳；拒絕存取即停止。不使用朋友入口、注入、附加、登入／TLS 繞過。授權不得自行擴至公會等其他帳號功能。暫不部署，未升級依賴。

### 目前有效資料

2026-11-25 20:35（台灣時間）直接核對六份排行；新增四段位防禦於 20:42 完成。傳奇、青銅沿用一小時內已重新核對的同玩家副本，各份原始取得／核對時間仍分開保存。

| 段位 | 排名玩家 | 完整／部分／未提供 | 隊伍 | 已穿戴裝備／模板關聯 |
|---|---:|---:|---:|---:|
| 傳奇 | 200 | 200／0／0 | 400 | 5,970／5,970 |
| 大師 | 100 | 100／0／0 | 199 | 2,982／2,982 |
| 鑽石 | 100 | 98／2／0 | 196 | 2,922／2,922 |
| 黃金 | 100 | 85／14／1 | 181 | 2,557／2,557 |
| 白銀 | 100 | 67／8／25 | 140 | 1,877／1,877 |
| 青銅 | 100 | 77／18／5 | 172 | 2,191／2,191 |

- 合計 **700 位不重複玩家、627 完整／42 部分／31 未提供、1,288 隊、18,499 筆已穿戴裝備紀錄（按擁有者範圍去重亦為 18,499 個實例）、554 個確認空部位、未知部位 0；模板關聯 18,499／18,499，未知裝備／角色模板 ID 0，請求失敗 0**。未提供隊伍不代表沒有防禦；角色位置與空部位／未知部位分開。並非每人固定兩隊。
- `python scripts/validate_current_pvp.py --integrity` 已逐份驗證 700 份保存回應的 SHA、擁有者、模組、隊伍與位置、角色／裝備實例、部位、currentEnchant、效果 ID／valueGrade 與目前接受資料一致；SQLite quick_check=ok、外鍵錯誤 0。報告 `reports/pvp-current-source-validation.json`、`reports/pvp-current-cohorts.json`。新 HTTP 共 80,707 個效果 ID／階級條目，數值還原 **0**，ID／階級不能當成實際效果數值；也未標為目視核對。
- 強化來自各實例 `currentEnchant`，含大師的 +2 等實際值，不是統一 +5、模板 maxEnchant 或 fallback。相同模板的不同實例保留獨立識別範圍。
- 六份名單僅代表該回應範圍，全服／全段位／子段位完整性未知。新增四段位使用模組實際字串 `MASTER_3 / DIAMOND_3 / GOLD_3 / SILVER_3`，不把它們換成猜測英文參數；本機翻譯表分別對到大師Ⅲ等名稱。未獨立確認是否涵蓋同名其他子段位。
- 953 裝備模板及 Rangerbook 外部參考仍分開；角色 2,405、星等 2,405、中文名稱 2,385、技能 ID 1,903、能力 ID 1,750；圖片及技能細節均 0。此輪未重新擷取或改寫這些成功成果。

### 已驗證來源與快速流程

- 防禦：`0174720c -> MainDataLoader 015eab84 -> /player/units/team/equip/uid/{UID}`；`015eac0c -> FriendModel -> 0113b5a8 -> FriendDataManager+0xc0`。`pvpteam` 為 kind 5，與普通 team1～team5 分開。首份 HTTP 與既有 Narumi 原生副本交叉核對 2 隊／10 角色／30 裝備及 119 組普通效果 ID／階級一致。
- 排行：`0174d004 -> PvpMainDataManager +58 / 01751700 -> this+30 -> 01750af0`，正常路徑 `/pvp/league/rank/%s`；回應 `01750c2c -> result.pvpLeaguePhase / league.rankingList -> 0175113c / 00fc4d78`。整數 JSON predicate／int32 轉換依 `01a15bfc / 01a15244`；接受 199.0，拒絕小數、NaN、bool 等。
- `scripts/runtime/pvp_league_codes.py`：青銅／傳奇以遊戲快取 UID 集與 UI 確認來源逐項匹配；新增四段位取原生表 `01f404b0` 實際字串及本機 zh-Hant 翻譯，要求正常回應回傳同一 phase code。新段位沒有先前 UI 筆數基準，只驗證回應陣列完整讀取、排名連續、識別不重複，不宣稱全段位完整。證據 `reports/pvp-league-code-validation.json`、`reports/ghidra/pvp-ranking-phase-table-consumer.txt`。
- `scripts/runtime/pvp_session.py` 僅擷取必要 HTTP context 與 LF_AC 單一偏好項於記憶體使用。固定正常來源、TLS 驗證、禁止重導、限制回應長度，不儲存 headers／Cookie。模組 12.4.2 SHA `1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0`。
- 統一入口 `update_local_game_data.py`：名單預設 60 秒快取、防禦 300 秒；跨名單按實際 UID 沿用已接受副本，保留原始來源與時間。新的失敗跨名單也不會被舊快取掩蓋，必須有較新的實際成功核對才能恢復；新名單先暫存，防禦批次驗證完成才一起切換 current pointers。跨程序 OS 鎖防止重複擷取。每個防禦批次最多兩個 worker／每秒兩次開始；內容不變只更新核對時間，0 原始副本／0 隊伍重寫。
- 首輪傳奇 200 人：199 新 GET＋1 既有副本，含解析／入庫 123.672 秒；同副本快取 0.328 秒。擴充四段位：400 新 GET＋原本 300 人快取，整個統一更新 426.189 秒。這些是實測範圍，不能當成每輪固定速度。六段位 700 人快取重跑由 52.672 秒縮到 **8.391 秒（含 Python 啟動／完整統一入口，0 GET、0 normalized 重寫）**，測試參數為沿用名單、快取上限 3,600 秒；沒有把快取當作重新取得或改寫原時間。改善為僅檢查本次目標、過期玩家才準備內容比較、不重複解析私有根路徑。報告 `reports/pvp-six-scope-cache-validation.json`，優化前另存。已移除 HTTP 每段位重跑全歷史 quick_check；交易、欄位及來源驗證保留，交付時另做一次完整檢查。

```powershell
# 六段位按需更新，本機＋Supabase；不逐頁操作遊戲
python scripts/update_local_game_data.py --module pvp --capture --scope all --use-authorized-runtime-session --sync-supabase
# 單一段位；--force 可強制重新請求
python scripts/update_local_game_data.py --module pvp --capture --scope 大師 --use-authorized-runtime-session
# 離線重核已接受資料
python scripts/validate_current_pvp.py --integrity
```

### 保存及驗收

- 本機 `data/local/lr.private.sqlite` 已保留舊版本，目前 normalized 有 1,399 隊歷史觀察；其中 1,288 隊屬於六份目前排行，不能把歷史累積當作目前隊伍數。
- Supabase 私有草稿 **`pvp-ranked-8cf30e62ebbd126baba1abbb`** 已保存 **1,994 筆＝700 排名玩家＋1,288 隊＋6 來源**；全數讀回一致、匿名存取阻擋、published／既有版本保留。receipt `reports/pvp-rankings-supabase-receipt.json`。
- 舊原生副本普通數值 2,952（2,523 固定值一致＋429 在外部範圍），2,170 條仍未知，只有歷史 6 個數值目視核對；與這次 HTTP 的未知值分開。其私有 Supabase 草稿 `equipment-audit-cb9fd967d04381a13d8479ea` 已於本輪完整讀回確認，非仍待同步。
- 網站 `/pvp` 已接六段位、個別玩家裝備、來源／核對時間；`/data-status` 增加各段位成功／部分／未提供／失敗／未讀表格。統計只用各份名單同玩家的選用隊，保留角色與裝備分母、備用隊不計入；不計算勝率。
- 已通過 Python HTTP／排行／匯入 27 項＋快速入庫保留成功資料 1 項；最新跨名單失敗快取 2 個受影響案例另重驗。TS 資料層 19 項、typecheck、lint、production build 通過。Edge 六段位／桌面手機／玩家頁／缺漏與隱私共 11 案例通過，另單獨核對大師玩家實際 +2 裝備 1 案例通過（沒有統一改成 +5）。`reports/rankings-browser-validation.json`、`reports/rankings-enhancement-browser-validation.json`。新 HTTP 玩家頁原先只接受舊快照 ID 的 404 問題已修正，保留舊 ID 相容。

- 成功基準已保存一致性 SQLite 副本與成功程式版本：`data/research/runtime.private/baselines/pvp-six-leagues-20261125T125724Z`；索引 `reports/pvp-six-league-success-baseline.json`。不含 .env、Cookie、解密金鑰或整份記憶體。原 5 筆裝備成功副本與舊基準均保留。

仍未完成：指定公會「復仇者總動員」名單／公會戰十塔防禦；HTTP 實際詞條數值及 Skill+／特殊條件；同名其他子段位涵蓋確認；角色圖片／技能細節；PVP 常駐排程；本機 .db 解密及全遊戲完整性。遊戲目前顯示「回到主畫面以更新變更的遊戲資源」提示，沒有代操作更新；已載入的現有工作階段仍完成本次正常請求。舊 UI collector 停止檔保留，不得恢復逐頁批次。Ghidra 定向六段位 session 已關閉／保存，始終 -noanalysis。

## 最新策略修正：已停止逐頁批次，改查程式碼／快取／正常請求來源

使用者最新表示「不是應該抓程式碼嗎？用快照太慢太耗時」。**不得自行恢復逐頁 UI 批次。** 已用停止檔讓 collector 安全結束，DB 已重核：兩次共保存 **23 位傳奇玩家、46 隊、690 個裝備部位＝689 件已穿戴＋1 個已確認空部位**，未讀取 **177／200**，失敗 0；原資料保留。最後 exec session `38290` 已 exit，原 `3407` 亦已結束。停止檔 `runtime.private/ranking-session-20261125/stop` 保留，這是目前策略，不要為了續跑移除它。

- 目前不是圖像辨識：角色／裝備取自已驗證原生物件，副本供離線檢驗；但逐玩家正常 UI 載入仍是瓶頸。曾將同一排行可見列查找從 273 次讀取／5.375 秒縮到 47 次／約 0.6 秒，座標與玩家相同；**沒有宣稱全流程也快相同比例**。比較在 `reports/runtime-ranking-ui-read-benchmark.json`。即使如此，現已按使用者要求改查遊戲已有的快取與正常載入請求，不能只繼續點頁。
- 新的 Ghidra 定向程式碼 session `68589` 目前開啟已保存專案，`-noanalysis`；queue 為 `runtime.private/evidence-pvp-source-20261125`（ready 後可送明確目標；15 分鐘後自動關閉）。沒有完整 auto-analysis、安裝、注入、權限變更。第一個工作 `pvp-avatar-request-and-friend-cache-root.txt` 已排入：`PvpRankingCell` 正常頭像 callback `01742648`（由 `017426f0` 明確註冊）與 exact RTTI `FriendDataManager AP01e7d468`。優先確認已有完整隊伍快取、正常請求／回應來源；尚不能宣告有可直接批次呼叫的 API。不讀取／輸出登入憑證，不繞過保護或存取限制。
- 網站新排行資料層已接入，但第一次瀏覽器 QA 的玩家頁仍讀到舊防禦面板（缺排名 context）。已證實磁碟程式碼有新 prop；舊 dev session `70655` 已停止，改用乾淨輸出目錄 `.next-local-rank-dev` 重開 **session `33572`／port3101**。正在重核，不能先宣告瀏覽器全通過。未升級 Next／依賴；新 dev 只追加自己的 tsconfig 型別輸出路徑。
- PVP Supabase 匯出／上傳仍未完成；新裝備普通詞條數值仍待 collector 停止後離線 enrich（目前已可安全進行，係數為 `gear-factor-20261125T094625Z.private.json`，要確認同 PID）。外部對映／效果範圍不得填成實例值。公會「復仇者總動員」資料、圖片／技能細節、特殊詞條、.db 解密等仍未完成。**後續先繼續目前程式碼調查與網站驗證，不要求使用者再逐頁開玩家。**

## 11/25 進行中：真實排行榜已取得，正在批次抓傳奇防禦

**本節為目前工作狀態，尚未交付完成。** 使用者已開啟 PVP 排行並要求繼續；不得操作朋友入口。**目前只有 `collect_ranked_pvp.py` 可操作裝置 UI，其他工作不得同時切換／點擊遊戲。**

- 真實青銅榜第 1～100 名：`runtime.private/pvp-ranking-20261125T091619Z-f40206`；傳奇榜完整讀出此次載入的第 1～200 名：`runtime.private/pvp-ranking-20261125T092412Z-1f35f3`，排名無重複，與青銅 100 人 UID 無交集。未獨立確認全服完整性。中途傳奇 100／200 的上限中止副本 `pvp-ranking-20261125T091720Z-3c92a1` 保留，未蓋過完整載入副本。
- 目前傳奇來源 ID：**`pvp-ranking-6c983bf0025d54857e39aa07`**。原生排名與前四位名稱／分數已對照正常畫面；`screen-observation.private.json` 保留段位標示、時間及截圖 SHA。排行榜及防禦各自保留採集時間。
- 第一名 Narumi 經排行頭像正常入口進入防禦，**原生 UID 精確吻合**；取得 A／B 兩隊、10 角色、30 裝備，實際 currentEnchant 均 +5，模板關聯 30／30。副本 `ranked-defense-20261125T091925Z-026748`；A 隊「防禦」用途／五個角色位置已目視，未宣稱逐件詞條目視。讀取實測約 9.7 秒。這筆沿用同次工作較早副本，時間未改為本次入庫時間。
- 本機新增 `ranking_snapshots`、`current_rankings`、`ranking_defense_attempts`；`scripts/ranking_database.py` 管理不可變排行來源與獨立防禦嘗試。按段位保存目前有效名單，部分來源不覆蓋完整舊來源；每玩家成功／部分／失敗／未讀取分開，可續抓。隊伍仍透過原 `import_defense_teams.py`、`sync_database` 保存全部實例，保留原非排名資料及強化／詞條。
- **目前批次仍在跑：exec session `3407`**，命令 `python scripts/runtime/collect_ranked_pvp.py --snapshot pvp-ranking-6c983bf0025d54857e39aa07 --top 200 --max-seconds 3600`。此節寫入時成功 14 位（已包含較早第一名，名次不保證連續），200 位目標尚未完成；最終數字須查 DB／`runtime.private/ranking-session-20261125/progress.private.json`，不能沿用此中途數字。停止檔為該 session 目錄的 `stop`；不是舊公會 stop。不要另起第二份 collector。
- 批次由可見 `PvpRankingCell` 的原生 UID／RankingData 比對來源，再以 CCNode getter 證實的位置、父節點、縮放／anchor 換算可點位置；點入後再次檢查可見玩家 UID／mode5。只使用正常排行／返回／段位選單／捲動。退出玩家頁會回青銅，因此正常重選傳奇，不能誤把青銅列貼上傳奇名次。每次有節點、深度、列數、時間、捲動上限，類型或來源不符即停止；沒有注入、改權限或猜端點。
- 新腳本：`scripts/runtime/pvp_visible_cells.py`、`scripts/runtime/collect_ranked_pvp.py`。證據：`reports/ghidra/pvp-ranking-visible-cell-source.txt`、`pvp-ranking-cell-record-and-index.txt`、`pvp-ranking-cell-leaf-storage.txt`；精確驗證模組內已匯出的 CCNode getter 指令，不從其他類別套偏移。
- 已接線但**本輪最後瀏覽器驗證尚待完成**：`lib/pvp-rankings.ts`、`/pvp`、`/pvp/players/[playerAlias]`。名單依段位／Top N 名次範圍；防禦頁只讀本次來源明確關聯的隊伍，不拿同玩家較新或不相干的歷史隊伍代替。統計使用選用隊伍，不算備用 B；角色／裝備完整玩家各自分母，玩家數與出場次數分開，未知部位不當空部位；裝備組合只取同個角色實例。無戰果，不算勝率。非排名歷史頁依已確認排行來源精確排除新隊伍，舊資料保留。
- 當前只擷取並標準化新裝備的屬性 ID／分級，**新樣本數值尚未批次還原**。已讀同 PID 係數 `runtime.private/gear-factor-20261125T094625Z.private.json`（1.0）；collector 結束後再執行離線 enrich，不得與 collector 同時修改正常化檔。原非排名 886 值／373 未知維持；不要將 373 當成包含新增排行資料的總未知數。
- 本輪已通過 TS 17 項及一次 typecheck；Python 新資料庫測試曾只因測試連線未關閉而清理失敗，已改用 closing，3 個實際排名儲存測試及 5 個既有遠端寫入測試重跑通過。排行解析既有 7 項通過。共享上傳器新加 pvp module／可調小批次，**PVP 遠端匯出及上傳尚未執行**；最後相關測試、lint/build、瀏覽器 QA、成功備份及收尾紀錄仍需完成。角色 2,405 星等及先前裝備的遠端草稿保留。
- 開始前一致性備份：`runtime.private/ranking-session-20261125/before/`。**不部署、不升級依賴、不重跑完整 Ghidra auto-analysis。** 尚未取得「復仇者總動員」名單／公會戰十塔，不能用這些排行玩家冒充公會成員。

## 11/25 最新續作：2,405 筆角色星等已驗證並保存兩端；排行擷取準備完成

**本節優先於下方舊狀態。** 使用者已要求繼續並表示遊戲已開，解除先前裝置暫停；但最新明確指示是「下次不要開朋友，我重開一次開 PVP」。**不得再從朋友入口操作。** 目標仍為「復仇者總動員」公會成員／公會防禦，PVP 仍只能從真實排行榜取得玩家。未部署、未升級依賴、未重跑完整 auto-analysis。

- ADB 正常；雷電 ABI 為 x86_64，實際載入的 arm64 `libgame.so` SHA256 仍是已驗證 12.4.2 的 `1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0`。沿用唯讀、有限位址範圍的 Reader；未使用附加／注入或調整權限。朋友入口本次再次觸發載入及 `input tap` 逾時後即停止該入口；使用者自行重開遊戲。
- **角色星等已建立原生 UI 證據，覆蓋由 0 提升為 2,405／2,405。** `StarLayerBuilder 019c461c` 的第一個 dynamic_cast RTTI 指向 `UnitData`（`01fb98f0 -> 01e36218`，與 UnitData AP `01e35410` 的 RTTI 相同）；virtual `+b0 -> 00c147cc -> UnitData+f8`，經 `01a5c570` 解 wrapper 後存入 Builder+18，橋接到 `019c4a84` 的星等繪製。範圍 1..9；只對已驗證模組與 RANGERS 模板採用，GUARDIAN、未知模組／範圍保留未知。不是以角色名稱、ID 或外部數字推定。
- 使用原保存副本 `character-capture-20261123T030909Z-da0eaa` 離線重解析，**沒有重新擷取角色**。2,405 筆原生其他欄位逐筆比較一致；`parse_runtime_characters.py` 版本為 `runtime-character-v4-native-star-ui`，`fieldStatus.starCount=verified-native-ui-relation`。原始副本與舊正常化版本保留。
- 星等分布：1 星 33、2 星 56、3 星 69、4 星 100、5 星 97、6 星 111、7 星 143、8 星 1,586、9 星 210。例：`u1618e-ka`「怪獸８號」日比野卡夫卡為 **9 星**。名稱 2,385／2,405、類型／屬性 2,405／2,405、主技能 ID 1,903、能力 ID 1,750；圖片／技能詳細數值覆蓋仍為 **0／0**。載入容器先前已遍歷結束，全遊戲完整性仍未獨立證實。
- 本機 SQLite 的 `documents.payload.records[*].starCount`（由 `current_documents.filename='verified-characters.json'` 選取）已更新。**兩個角色文件版本均保留**；quick_check=ok、外鍵錯誤 0。新增角色星等入庫驗證：缺原生 UI 證據、非整數、越界不能推進有效版本。
- Supabase 沿用已存在的私密研究表，新草稿 **`characters-native-82bb54a1f8ab3bf328a3f36e`**，module=`characters`；`ranger_research_records.normalized_record.starCount` 共 **2,405 筆**，全部逐筆讀回一致，匿名讀取阻擋及 published 版本未變已驗證。未建立新表／執行 migration。角色取得時間仍是原副本時間，沒有把本輪靜態確認時間冒充新採集時間。
- 新增 `scripts/sync_character_templates_supabase.py`：先驗證目前本機已接受文件、原生來源 SHA、模組與逐筆白名單，再凍結私密匯出；預設只準備、`--apply` 才新增。沿用原裝備 uploader 的保留／續傳／讀回機制，僅擴充 module 篩選，角色匯入不碰裝備表。回執：`reports/character-templates-supabase-receipt.json`；凍結版本在 `runtime.private/character-exports/characters-native-82bb54a1f8ab3bf328a3f36e/`。金鑰未寫入匯出或聊天。
- 網站 `/characters` 星等顯示與篩選已啟用，`/characters/u1618e-ka` 顯示 9 星；`/data-status` 反映星等完成，圖片／技能仍待補齊。沒有把模板星等混成玩家等級或玩家進化狀態。953 裝備模板、886 個實際普通屬性值及 373 個未知數值均未改動。
- 新增 `scripts/runtime/read_pvp_rankings.py` 與 `scripts/parse_runtime_rankings.py`。定向證據確認 `PvpMainController AP01f150f8 -> PvpRankingLayer AP01f14af8 -> virtual+448/017456ec -> +178 CCArray -> RankingData AP01e53d58`；原生 JSON parser `00fc4d78` 與 setter 證實 uid+18、score+30、rank+34、displayName+58、leaguePhase+78。只讀正常載入清單，限制 320 UI 節點、深度 7、256 排行列／預設 100，驗證型別、短讀取、字串、重複指標／玩家、來源前後一致；原始識別只寫 runtime.private。不從公會名單產生排行，不推測 API。
- **排行腳本目前僅完成準備與隔離測試，尚未取得實機排行紀錄。** 17:07:27～17:08:19（台灣時間）的有限唯讀檢查持續看到 `ResourceUpdateController`，畫面為「載入遊戲數據」0%，不是 PVP 主頁或排行榜。`reports/pvp-ranking-source-readiness.json` 的 `rankingCaptured=false`；**排名樣本仍 0**，沒有寫入 fixture、建立空統計或改排行頁宣稱成功。下一次必須等遊戲正常到排行榜才能執行實機驗證；不操作登入或繞過載入／保護機制。
- 檢查：角色解析／合併 Python **15 項**、新角色入庫保留測試 **1 項**、排行解析隔離測試 **7 項**、共享遠端保留／讀回測試 **5 項**通過；TS 受影響資料層 **13 項**通過；typecheck、lint、production build 通過。Edge **6 個角色／篩選／詳細／覆蓋頁案例**通過、無 JS 錯誤。裝備介面及無關全套檢查未重跑。package.json／package-lock.json 與前次成功基準 SHA 相同；build 僅自動追加自己的 `.next-local-continuation-20261125` 型別輸出路徑。
- 證據：`reports/character-star-field-validation.json`、`reports/ghidra/character-star-count-confirmed-native1242.txt`、`reports/ghidra/character-star-builder-render-bridge1242.txt`、`reports/character-stars-browser-validation.json`。本輪開始前的檔案／一致性 DB 備份：`runtime.private/resumed-20261125/before-character-stars/`；完成基準與腳本另存 `runtime.private/resumed-20261125/successful-character-stars/`。

```powershell
# 使用已保存副本重現角色，無需連裝置；先輸出到新檔確認，不覆蓋原始副本
python scripts/parse_runtime_characters.py --capture data/research/runtime.private/character-capture-20261123T030909Z-da0eaa --localization data/research/runtime.private/guild-session-20261123/lang_unit.ndb --output data/research/runtime.private/resumed-20261125/characters-reproduced.private.json
python scripts/update_local_game_data.py --module characters
python scripts/sync_character_templates_supabase.py --apply
python scripts/verify_character_defense_browser.py --scope characters
# 僅在正常 PVP 排行榜已開啟後擷取；scope-label 只能填畫面實際標示，不推定全服
python scripts/runtime/read_pvp_rankings.py --max-rows 100
python scripts/parse_runtime_rankings.py --capture data/research/runtime.private/<本次排行副本> --output data/research/runtime.private/<本次排行副本>/rankings.private.json
```

仍未完成：指定公會「復仇者總動員」名單／公會戰十塔及防禦；真實排行榜玩家、防禦關聯、快取續抓與統計；373 項裝備實例最終數值及條件、123 項模板候選的實例關聯；角色本機圖片、技能詳細內容、進化分類；原始 .db 解密及全遊戲完整性。**目前最少需要使用者讓遊戲正常進入可操作的 PVP 排行榜並保持開啟**，不要要求使用者替代擷取或轉貼函式。

## 11/25 最新追加：373 個未知數值項目補上外部效果對映

**本節更新下方前次校對結果；數值未知與效果無對映必須分開。** 沿用保存的原生物件副本，未操作裝置、未變更依賴、未部署；既有資料及正式版本均保留。

- 新公開來源副本：`data/research/external-reference/audit-20261125T075450Z-051be1`，包括 Rangerbook `gear/`、`equipment.json`、`equipment-effects.json`、`gear-detail.js`。效果索引只有 149 個 `attributeId`／`optionKey` 對照；參考範圍來自同裝備模板，不能當成玩家實際抽值。
- 原 373 個數值未知項目中，**216 個精確 attributeId 對映**；**34 個由同裝備 Spec+ 的 optionKey 與原生基礎範圍相符對映**（不能稱為相同 ID）；**123 個 ID=0 只能列同裝備模板候選**。後者 89 個有 GearStat+0x68 依賴、34 個有 +0x70 依賴，不視為空詞條，也不因候選只有一個就認定實例效果。
- 原生副本核對實例／位置／屬性欄位及 SHA256；屬性代碼、條件 selector 或基礎範圍衝突會拒絕對映。原始指標、記憶體及內部識別不傳前端。對映均為 `actualValueVerified=false`、`activationVerified=false`。
- 例：`eq_wpn_evt_138` 的 `attributeId=120018` 對應 `PRD_SPE_MUL`、敏捷型 Ranger 條件；外部模板 +0 為 −6.2%～−8.0%，每級參考變化 −2 個百分點。這是效果種類／模板參考，不是已解析的實例最終數值。`eq_2509_amr_18` 的 140007 則對應 HP_MUL／火屬性 Ranger，亦保留數值未知。
- **886 個原生普通數值不變，373 個 nativeValue 仍為 null**；已目視核對仍僅兩件裝備共 6 個值。總量仍為 953 模板、326 穿戴實例＋19 空部位、1,259 原始屬性條目，不宣稱全部為有效詞條。
- 新校對 ID：**`equipment-audit-7e5aa14830bba8e8a6b3f014`**。本機表 `equipment_attribute_checks` 的 `payload.externalMapping` 保存新對映，外層 `status=unparsed_native` 保留。Supabase 對應 `ranger_research_records.normalized_record.referenceChecks[*].externalMapping`，限定同一 snapshot_id；原始未知數值未覆寫。
- 本機保存並標記 remote verified；Supabase 新增私密 draft，**953 模板、2,251 研究紀錄全部逐筆讀回一致**，匿名讀取阻擋及正式版本保留已驗證。前次 `equipment-audit-d5653e93b83290e19783c270` 及原有資料保留。匯出／回執在 `data/research/runtime.private/equipment-audits/equipment-audit-7e5aa14830bba8e8a6b3f014/`。
- 網站由本機 SQLite 讀最新通過校對，白名單輸出顯示必要欄位。250 個效果對映顯示「效果種類已對上，實際數值尚未確認」；123 個候選顯示「同裝備模板候選，尚未確認實例對應」。範圍清楚標示模板 +0，觸發條件是否生效未知；不重複套強化或把參考範圍寫回實例數值。
- 修改：新增 `scripts/equipment_unknown_mapping.py`、`lib/equipment-mapping.ts`；更新校對抓取／比較／遠端同步、`lib/local-game-data.ts`、`lib/defense-teams.ts` 及防禦面板。新增 Python／TS 對映測試；瀏覽器檢查補入來源／候選與實際數值分離。
- 本次受影響 **Python 10 項、TS 15 項通過**；型別與 production build 通過。Edge 桌機／手機 **10 個案例全通過、runtimeErrors=[]**，含未知數值不補值、候選不當成確認、無原始識別／指標洩漏及模板範圍分離。證據：`reports/equipment-instance-reference-audit.json`、`reports/equipment-audit-supabase-receipt.json`、`reports/source-routing-browser-validation.json`。
- 成功基準：`data/research/runtime.private/baselines/equipment-audit-7e5aa14830bba8e8a6b3f014/`，含一致性 SQLite 備份及本次腳本／顯示／測試／報告副本與雜湊清單，不含連線金鑰。

```powershell
python scripts/audit_equipment_reference.py --reference data/research/external-reference/audit-20261125T075450Z-051be1 --apply
python scripts/sync_equipment_audit_supabase.py --export data/research/runtime.private/equipment-audits/equipment-audit-7e5aa14830bba8e8a6b3f014/export.private.json --apply
python -m unittest tests.test_unknown_equipment_mapping tests.test_equipment_reference_audit
npx.cmd vitest run tests/equipment-mapping.test.ts tests/native-data-layers.test.ts tests/local-game-data.test.ts
python scripts/verify_character_defense_browser.py --scope source-routing
```

仍未完成：373 項實例最終數值與啟用條件、123 項候選的實例效果關聯；指定公會「復仇者總動員」名單／公會防禦；真實排行玩家及防禦樣本（目前 0）；角色星等／圖片／技能細節；原始 .db 解密與全遊戲完整性。裝置操作仍依使用者指示暫停，不因外部對映成功自行恢復。

## 11/25 最新追加：裝備外部校對已保存本機與 Supabase

使用者明確要求校對後存入「本機與 Supabase 都要，保留現有資料」。本節更新下方舊的「未修改遠端」狀態；網站仍未部署、裝置操作仍暫停。**本次只新增私密裝備草稿，沒有切換正式版本。**

- 重新取得 Rangerbook 裝備 JSON、裝備顯示 JS 與頁面：`data/research/external-reference/audit-20261125T071751Z-240f51`。JSON、JS 雜湊與原保存版本一致，頁面實際引用相同顯示 JS。比對採裝備 ID、原生屬性代碼、單位、實際強化等級，沒有名稱模糊比對，也沒有重複套用強化。
- **953／953 模板的 ID、星等、類型一致**；1,259 個原始屬性項目中，**498 個固定值完全一致、388 個落在外部範圍內、373 個本機尚未解析**，無已解析數值衝突。範圍相符不等於外部資料能確認該件裝備的精確抽值；只有原 6 個值已目視核對。未知項目沒有用外部範圍補值。
- 本機 `data/local/lr.private.sqlite` 新增 `equipment_reference_audits`、`equipment_template_checks`、`equipment_attribute_checks`、`equipment_audit_exports`，原模板與實例內容未覆寫。校對 ID **`equipment-audit-d5653e93b83290e19783c270`**，本機已讀回 953 個模板校對、1,259 個屬性校對；quick_check=ok、外鍵錯誤 0。
- Supabase 原專案一度 DNS NXDOMAIN；使用者恢復後已連通。遠端缺少裝備研究表，已以 `scripts/sql/ensure_equipment_audit_storage.sql` **僅建立三個原本不存在的表**：`ranger_research_snapshots`、`ranger_research_records`、`ranger_equipment`；新表 RLS 私有、撤銷 anon/authenticated 權限。沒有執行完整多模組 migration、修改既有資料表／函式或改 migration history。
- Supabase 以上述校對 ID 新增 **draft**：`ranger_equipment` **953 筆原生模板**，`ranger_research_records` **2,251 筆**（953 原生模板、953 外部參考、345 部位觀察＝326 穿戴實例＋19 已確認空部位）。所有 payload 已逐筆讀回完全相符；匿名讀取阻擋已驗證。內部玩家／角色／裝備實例 ID 轉為具玩家範圍的別名，沒有上傳憑證、金鑰或原始記憶體。
- 原有翻譯 **1,346 筆**及 published 版本完全未變。前後內容摘要皆 `d8ac2cf85d7b9108867581151816f997`；原版本 content SHA256 仍 `4b06537f4146078ad1859f8793a438418ebc237a2e1e4d04f38370efe1a5d301`。原公開翻譯功能及正式版本保留。
- 重現腳本：`fetch_equipment_reference_audit.py`（只抓三個公開來源）、`audit_equipment_reference.py`（比較及本機保存）、`sync_equipment_audit_supabase.py`（預設只準備，`--apply` 才新增；只補缺列，不覆寫，並驗證全部讀回）。Supabase 連線沿用 `.env.local`，金鑰不寫入聊天或匯入檔。
- 受影響 Python **14 項**通過，含真實副本比對／入庫、固定值與範圍區分、負值／單位／強化、未知值不補值、重跑不重複、遠端衝突保留與匿名權限防線。編譯檢查通過。本次未改網站程式及依賴，未重跑無關的 Next build／瀏覽器檢查。
- 證據：`reports/equipment-instance-reference-audit.json`、`reports/equipment-audit-supabase-receipt.json`；私密可續傳匯出在 `runtime.private/equipment-audits/equipment-audit-d5653e93b83290e19783c270/`。本機匯出狀態已標為 remote verified。

```powershell
python scripts/audit_equipment_reference.py --reference data/research/external-reference/audit-20261125T071751Z-240f51 --apply
# 對同一份已保存匯出檔準備／續傳，不另建新 ID，也不切換正式版本：
python scripts/sync_equipment_audit_supabase.py --export data/research/runtime.private/equipment-audits/equipment-audit-d5653e93b83290e19783c270/export.private.json
python scripts/sync_equipment_audit_supabase.py --export data/research/runtime.private/equipment-audits/equipment-audit-d5653e93b83290e19783c270/export.private.json --apply
```

尚未完成維持：373 個未知項目的計算／依賴、指定公會名單與公會防禦、真實排行樣本及其防禦、角色星等／圖片／技能細節、原始 .db 解密與全遊戲完整性。裝置操作暫停未解除；不要因 Supabase 恢復就自動恢復遊戲操作。

## 最新有效指示：指定公會與排行分流；裝置操作依使用者要求暫停

**本節優先於下方全部歷史狀態。** 使用者已更正：不要再抓 YXGC；公會目標改為 **復仇者總動員**，取得公會成員及公會防禦。**PVP 必須從排行榜取得排名玩家後再抓防禦，不從公會成員擴抓。** 使用者最後表示「稍等一下，先做其他的」，因此已停止裝置操作；尚未收到恢復操作指示。不得自行繼續點擊／重啟雷電。

- 已停止舊批次，`runtime.private/guild-bulk-session/stop` 存在；`collect_guild_pvp.py` 已被資料庫的 ranking-first 政策封鎖，不能再作主要擷取流程。泛用 `update_local_game_data.py --module pvp --capture` 也已封鎖，必須先建立真正的排名來源／玩家關聯。不要為了續跑而移除這些防線。
- 本機 SQLite 新增 `collection_targets`：guild=`復仇者總動員`、pvp=`rankings`，來源為使用者選擇。公會擷取及週二排程在匯入前檢查公會名稱，不得拿目前帳號的 YXGC 覆蓋目標。排程時間仍為每週二 12:00（台灣時間）；只表示嘗試取得，尚未完成目標公會的來源驗證。
- `/guild` 已顯示指定公會「復仇者總動員」及名單／公會防禦尚未取得，沒有拿 YXGC 成員充數。舊 YXGC 名單、隊伍及物件副本保留於本機歷史資料。使用者確認「未報名所以打不開公會戰」**只適用舊公會 YXGC**；不得套用到新目標。
- `/pvp` 已改為排行來源主頁，目前明示排名樣本未取得，沒有 Top N／使用率／勝率。舊隊伍移至 `/pvp/observations`，為非排名歷史觀察。原頁的分頁／玩家選擇連結已改用新路徑。沒有把歷史成員觀察轉成排名樣本。
- 新增 `/data-status`，顯示已取得與尚未完成項目、未知裝備 ID、實際數值覆蓋、來源邊界。新公會的成員總數維持「尚未取得」，沒有把歷史 44 人當作新公會人數。
- 歷史原始副本本輪保存並正常化後，合計 **12 位非排名玩家、23 隊、345 個裝備部位紀錄：326 件已穿戴、19 個已確認未穿戴部位**。先前將 345 稱為裝備件數不精確，不能把空部位算作實例。326 件中，296 件保存屬性陣列，30 件舊副本未擷取屬性。普通屬性公式已擴用於每位玩家自己的副本：共 1,259 原始屬性條目，**886 個已還原數值、373 個數值仍未知**；未知條目包括語意未明的 ID=0 項目，不能全稱為真實詞條。目視核對仍只有原 NiroDen 兩件裝備的 6 個數值，沒有替其他玩家標記已目視。這些歷史資料不代表新目標公會或排行取得成功。
- `parse_runtime_gear_values.enrich` 支援校準來源：先重新驗證原兩件裝備及 UI 證據，再以同模組／同 PID 的係數計算新副本各自的普通欄位；不抄另一玩家數值，不複製目視旗標，+68/+70 或 selector 非 none 的分支仍跳過。批次離線腳本 `scripts/enrich_saved_defense_values.py`，已使用 `gear-factor-20261125T042702Z.private.json`。不要讓它與其他正常化匯入器同時寫同一份資料。
- 遊戲曾連續 Android ANR，正常關閉／重新開啟後已載入主畫面；點朋友頁後持續轉圈，`input tap` 亦逾時，尚未執行新公會名稱搜尋。搜尋文字方式已查證雷電官方 `call.input`，無需安裝輸入法；但暫停期間不能使用。停前截圖 `runtime.private/guild-search-session/current.private.png`（主畫面轉圈），不表示目前畫面仍相同。
- 核對：SQLite quick_check=ok、外鍵錯誤 0；package.json／lockfile SHA 未改；typecheck、lint、production build 通過。受影響 TS 23 項通過；Python 21 項通過（新目標防線、校準、資料庫、正常化）；Edge **10 個桌機／手機案例**通過，含公會目標不混用、排行／非排行分頁及資料進度，無 JS 錯誤。證據：`reports/source-routing-browser-validation.json`、`reports/collection-source-separation-validation.json`、`reports/build-local-validation-status.json`。

每次交付必須明列尚未完成，不能只報已完成：

1. **復仇者總動員**：尚未搜尋／驗證其成員名單；成員總數未知，公會防禦／十塔能否正常查看也未知。
2. **PVP 排行**：尚無已解析排名玩家、名次範圍、來源時間與排名玩家防禦關聯；排名樣本仍 0。舊青銅排行畫面截圖不算已解析樣本。
3. 特殊／進階／Skill+ 屬性缺少已保存依賴與完整計算證據，373 個已讀條目數值未知；未讀依賴另計。
4. 角色基本模板仍 2,405 筆，中文名 2,385；星等／本機圖片映射／技能描述數值覆蓋仍 0／0／0。主技能 ID 1,903、能力 ID 1,750 不等於技能細節。
5. `.db` 解密、全遊戲完整性、脫離遊戲載入狀態的更新來源及部署均未完成；暫不部署。

目前可重現的離線工作（不觸碰裝置）：

```powershell
python scripts/select_collection_targets.py --guild '復仇者總動員'
python scripts/update_local_game_data.py
python scripts/enrich_saved_defense_values.py --factor data/research/runtime.private/gear-factor-20261125T042702Z.private.json
python scripts/verify_character_defense_browser.py --scope source-routing
```

## 11/25 最新：本機資料庫、週二公會更新與批次唯讀傳輸

本節優先於下方歷史基準。沒有部署、改動遠端 Supabase 或升級依賴；原始資料及舊快照保留。

- **本機 SQLite 已實際入庫並接入網站**：`data/local/lr.private.sqlite`；953 裝備模板、953 外部參考、6 組防禦快照／3 位玩家／90 件裝備觀察、44 筆公會成員關係。角色 2,405 筆也已保存於來源文件表。模板、外部參考與玩家實例分表；外部效果仍標外部，未知值保留 null。玩家／實例／快照識別均依玩家範圍保存，不用模板 ID 合併實例。
- `scripts/local_game_database.py` 管理來源文件版本、目前版本指標、模板、實例、成員、更新規則及嘗試紀錄；交易式匯入，驗證失敗不推進目前版本，不刪舊成功資料。`PRAGMA quick_check=ok`、外鍵錯誤 0。資料庫不在 public，已加入忽略規則；不含 token／金鑰／原始記憶體檔。
- `lib/local-game-data.ts` 僅於 development、設定 `LR_LOCAL_DATABASE_PATH=data/local/lr.private.sqlite` 時從本機資料庫讀取；既有伺服器欄位白名單保留。已追加此單一設定至 `.env.local`，其他設定未改。未設定時保留既有 JSON 讀取流程；production 不開放研究用角色／防禦／外部參考。
- 公會目前 **YXGC 44／50，實際 44 人**，11/25 副本 `guild-members-20261125T023342Z-f7f203`；舊 41 人副本保留。**NiroDen 已取得 PVP A/B 兩隊、10 角色、30 裝備，所屬與模板 30/30、實際強化皆 +5**。其餘 43 人防禦尚未讀取，不等於不可取得。公會戰 10 塔駐防資料仍未取得。
- NiroDen 副本 `member-defense-capture-20261125T023755Z-ee891f` 含 120 原始屬性條目；其中 **90 筆普通屬性數值**已由實例及原生公式還原，2 件不同裝備的 **6 個顯示值**已目視核對；其餘 30 項仍未知。井上尚彌的 183 項仍為 ID／raw 分級，不套用其他玩家數值。新係數來源 `gear-factor-20261125T031832Z.private.json`：GameDBContainer `01fd4df8` → virtual38／`00f3b85c` → GameFactorData +3cc（float32=1.0），與實例 currentEnchant 一次計算；非猜測常數、非模板 maxEnchant。
- 普通分支 `0122dde4`，百分比格式 `0122f510`、類型鍵 `0122f924`；只有雙 selector=none 且 +68/+70 無特殊依賴才處理。`scripts/parse_runtime_gear_values.py` 使用原始副本、同 PID／模組係數與兩件 UI 核對檔，輸出 `observations-values.private.json`；未實作進階／Skill+／特殊分支。例：聖誕神聖槍物攻 +444.0%、重生 -30.0%、技能必中 +24.0%；11.5 週年草帽技能發動 +50.4%、礦石 -30.0%、技能閃避 +50.4%。強化已計入，網站不再乘一次。
- **公會每週二 12:00，Asia/Taipei**：已登記 Windows 工作 `LR-Local-Guild-Tuesday-Noon`，下次 2026-12-01 12:00。執行 `scripts/update_local_game_data.py --module guild --capture --if-due`；需 Windows 使用者已登入、雷電遊戲已正常開啟公會成員名單。睡眠／關機不會保證準時；StartWhenAvailable 支援恢復後補跑。無可見來源則記錄失敗並保留舊庫，不會自動操作登入、切畫面或更改隊伍。本週已取得成功名單會跳過重擷取。
- **PVP 隨時更新**：`--module pvp --capture` 只擷取目前正常可見的他人 PVP 防禦；自己帳號加 `--own`，沿用原有雙管理器所有權驗證。每次只同步該模組，不重抓 953 模板。網站顯示各隊實際取得時間；刷新網站不會自動抓遊戲。不存在可用來源時，不能憑排程變出新配置。
- 使用者要求改善速度後，已改善 `equipment_memory.py` 的精確 dd 區塊大小與 `Reader.read_many`：同批目標僅一次 Base64、一次 shell 往返；角色、裝備、強化 wrapper／string 與屬性採批次讀取。無頁面快取、無跨程序指標重用、無整份記憶體傾印、無注入、無權限調整；原有讀取／位址／型別／一致性上限保留。微量測 `reports/runtime-read-benchmark.json`：20 段／45,600 bytes，0.5382 → 0.1579 秒、內容一致，約 3.41 倍；**不是整次擷取的速度保證**。快照是可驗證來源副本；不能聲稱原生程式碼本身就含所有玩家防禦。
- 已另做一次目前可見玩家的完整實機批次擷取驗證：**26.453 秒、2 隊、30 件裝備、30/30 所屬關聯、30/30 實際 +5**；共 587 個目標讀取範圍、77,841 bytes，未覆蓋資料庫中已目視核對的數值快照。摘要 `reports/runtime-fast-defense-validation.json`，原始測試副本 `runtime.private/fast-read-validation-*`。這是目前流程的實測耗時，沒有舊完整流程同條件數據，不能宣稱全流程快 3.41 倍。
- 受影響檢查：資料庫／正常化／舊防禦 Python 19 項，TS 23 項、typecheck、lint、production build 通過；7 個 Edge 桌機／手機案例通過，涵蓋新資料庫讀取、公會規則、PVP 分頁及 NiroDen 90 個數值。批次讀取另外 17 項 Python 回歸通過（含原有邊界、短讀取、位址、槽位與所有權）。角色星等／圖片／技能描述數值覆蓋仍 0／0／0，主技能 ID 1,903、能力 ID 1,750；排名可統計樣本仍 0。沒有重跑未受影響的角色／模板全套檢查或完整 Ghidra auto-analysis。

```powershell
# 只將既有有效資料入庫，完全不連裝置
python scripts/update_local_game_data.py
# 隨時更新目前正常可見的他人 PVP 防禦；自己的帳號另加 --own
python scripts/update_local_game_data.py --module pvp --capture
# 公會補跑；需已開啟成員名單
python scripts/update_local_game_data.py --module guild --capture --if-due
# 檢查已安裝的排程
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/register_guild_update.ps1 -Inspect
```

## 11/25 追加：真實可見玩家 PVP 與實例屬性（目前仍在整合）

- 已由使用者正常開啟的「井上尚彌／復仇者總動員」PVP 防禦取得 **兩隊、10 角色實例、30 件不同裝備實例**。原始副本 `data/research/runtime.private/member-defense-capture-20261125T021309Z-1fba2f`，已離線解析並匯入現有私密快照，與舊兩隊合計 **兩位玩家、四隊、20 角色、60 件裝備**。
- 新增角色模板關聯 10/10、裝備模板 30/30，未知 ID 0；30/30 unitInvenId 所屬關聯吻合，currentEnchant 實際皆 +5。選用 A 隊畫面「防禦」及 5 位角色順序已核對；B 隊與每件裝備名稱／強化仍未逐一目視核對。
- 新 30 件裝備皆保存實例 +b0 屬性陣列，共 **183 筆原始屬性條目、38 個不同原始 attrNo**。不能稱為 183 個抽取詞條；數值、單位、觸發條件及固有效果／抽取詞條分類尚未確認。+1c 是格式／屬性類型 raw 值，已更名 attributeTypeRaw，不能當強化類型。實際效果 value/unit 仍為 null，沒有引用外部範圍補值。
- 原始條目同時含 +28/+2c float 與 +24/+20 欄位；離線原始欄位審查在該 capture 的 attribute-raw-field-audit.private.json。29 條有 +68 依賴、34 條有 +70 依賴，這些物件尚未保存；舊 0122d7f0/0122eb28 有分支與強化計算，不能把原始 float 或簡單內插直接當最終值。
- 成功物件鏈：CCDirector → FriendHomeController(AP01eee558)+138 → FriendModel(AP01e7d650)；mode+168=5、顯示隊號+148與 profile PvP隊號+160一致；UID字串+90，公開名稱+48，隊伍群組字典+198，kind5 為 PVP。constructor 0113c7f4 建立 0..5/19 字典後 virtual+1f8→0113e9b0 保存+198；getter0113e9a8。相關報告 member-pvp-visible-object-fields.txt、member-unit-container-getters.txt、friend-team-group-decoder.txt。
- 新擷取器 `scripts/runtime/read_visible_member_defense.py` 預設嚴格匹配保存名單。`--allow-visible-player` 明確保留非該名單的正常可見玩家，不虛構成員關係。上述井上 UID 與 guildId 都不匹配 YXGC，**不歸到 YXGC 成員**；目前 YXGC 成員防禦成功數仍 0，正在正常介面尋找其成員。
- 使用者已確認：PVP 防禦可在玩家首頁底部選單選「防禦」；公會戰配置位於 **10 座塔**，不是每位成員都有駐防。目前沒有已解析塔／駐防名單，未讀取不能當作未駐防。
- `/guild` 已按精確玩家 ID 串接 PVP 快照摘要；`/guild/members/[去識別化代號]` 可顯示該成員自己的角色與三部位裝備，沒有資料就標示未知，沒有借用其他玩家的隊伍。`/pvp` 顯示實際公開名稱（可取得時）及正確玩家數，不產生排名統計。
- 本輪受影響 Python 23 項、TS 16 項通過；公會／PVP 的 7 個 Edge 桌機／手機案例通過（reports/member-defense-browser-validation.json），原角色檢查未重跑。最終新增來源欄位後仍需完成本輪最後 lint/build。解析版本 runtime-defense-v3-visible-player；正常化 defense-import-v3-attribute-type。
- 雷電中斷後已正常啟動，目前遊戲已登入，沒有繞過登入／LIAPP、修改裝置權限或原始遊戲檔。11/25 使用的 Ghidra 指定函式工作階段已正常保存結束，沒有完整 auto-analysis。切勿重用 11/23 PID／指標。
- 青銅 PVP 排名畫面副本 `guild-session-20261123/pvp-ranking-bronze-20261125.private.png` 已保存，但未解析排名玩家 UID 與範圍；**可統計的標準化排名樣本仍 0**，井上快照沒有排名關聯。

離線重現（不重擷取）：

```powershell
python scripts/parse_runtime_defense.py --capture data/research/runtime.private/member-defense-capture-20261125T021309Z-1fba2f --all-teams --output data/research/runtime.private/member-defense-capture-20261125T021309Z-1fba2f/observations.private.json
python scripts/import_defense_teams.py --input data/research/runtime.private/member-defense-capture-20261125T021309Z-1fba2f/observations.private.json
python scripts/verify_character_defense_browser.py --scope guild-defense
```

## 11/23 已驗證基準（以下沒有新增來源的數字以本節頂端更新為準）

本節為目前狀態；下方 11/19 區段保留歷史資訊，不代表目前筆數、裝置狀態或公會來源。暫不部署，沒有改動依賴。工作區沒有 `.git` 目錄，未執行提交。

## 本次已取得並接上網站

- **角色模板 2,405 筆**，由 12.4.2 全域模板容器取得；遍歷 3,158 節點，排除 753 個非 RANGERS 定義，0 讀取錯誤／重複。null tail、容器前後一致，已載入容器遍歷完成，**全遊戲完整性未知**。原生 invenId=0，與玩家持有實例分開。
- 欄位覆蓋：ID／STR-AGI-INT 類型／屬性各 2,405；中文名稱 **2,385**；主技能 ID **1,903**；主要能力 ID **1,750**。星等、已確認圖片、技能描述及數值皆 **0**，維持未知。20 筆缺中文名稱仍保留，主技能 ID 不等於技能細節已解析。
- 原始角色副本：`data/research/runtime.private/character-capture-20261123T030909Z-da0eaa`；目前離線結果 `data/research/rangers-native-2405.json`；網站白名單 `data/normalized/verified-characters.json`。與舊 15 筆角色的名稱／類型／行為／屬性／技能 ID 比較無衝突。
- **公會 YXGC，等級 8：觀察總數 41／上限 50，實際擷取及解析 41 人，錯誤 0**。每個成員 gid 都匹配公會，UID 無重複，擷取前後容器一致。名單在本次觀察範圍已對齊總數；不是「50 人已取得」，也不是未來名單完整性保證。
- 公會副本 `data/research/runtime.private/guild-members-20261123T033922Z-6a83ec`；正常化 `data/normalized/guild-roster.private.json`。`/guild` 已顯示真實名單、名稱搜尋、時間／版本、部分缺漏與過期未知狀態；每名成員配置未讀取，不能當成沒有隊伍或裝備。識別碼僅留伺服器，前端白名單排除原始 UID、內部錯誤與記憶體欄位。
- 畫面核對：公會名稱／等級／41/50 與前 3 位成員吻合；未逐一目視核對全部 41 人。證據在 `guild-session-20261123/roster-screen-verification.private.json`。成員原生 level 與畫面階級不同，尚未確認換算，不直接顯示 raw level。
- 首位成員正常可見首頁是 **FriendHomeController / FriendModel、mode=0、一般 1 隊伍**，不是已確認的防禦資料；保存畫面與觀察，防禦狀態仍為 not_read。已請使用者開啟明確標示公會戰／PVP 防禦的可見配置頁；不用儲存、更改隊伍或出戰。**新增其他成員防禦成功數 0**，不能把畫面 15 件裝備或自己的舊隊伍套給他。
- 既有裝備 **953 模板**及外部 Rangerbook 效果來源標示保留。既有 12.4.0 PVP A/B 兩隊、10 角色／30 件不同裝備實例不變；30/30 裝備關聯、所屬角色關聯與實際 +5 回歸通過。它是 11/19 保存快照，不是目前 12.4.2 配置。實際詞條數值未解析。
- 真實 PVP 排名樣本 **0**；沒有使用率或勝率。公會排名 3285 不是 PVP 玩家排名。

## 已修正的重要原生證據

- 模組 12.4.2 (201242)，SHA256 `1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0`。只依 SHA 選版型；不套靜態絕對位址到 ASLR。
- **unitType 行為仍是 +0x430**：00c15428 / virtual+0x688。+0x448 是新 unitMoveType，不能把 FLIGHT 當行為。原始副本與 manifest 未改動，v3 離線解析器從完整 record 的已證明 inline 欄位還原；記錄 dependencyFieldsRecoveredFromRecord，hash 驗證仍保留。證據 `reports/ghidra/unit-type-move-type-correction.txt`。
- **01fe9a50 / AP01e4f790 是 ProhibitedWordManager，先前當作公會管理器的判斷錯誤，已排除**；未遍歷其中禁用詞。native_layouts 已移除 guildGlobal/guildManager 舊命名。
- 真實公會名單路徑：CCDirector global0204e2f0 → runningScene+f0(GuildController) → CCNode children+b8 → GuildMemberListLayer(AP01ea22f8) → +180 GuildInfoModel(AP01eadb48)。Layer+178 = model virtual+c0 → model+70 的 CCArray。
- GuildInfoModel：gid+30、name+38、level+84、max/currentMemberCount+9c/+a0。GuildMemberModel(AP01eade20)：uid+30、gid+38、name+40，來源解析器012ebd64與 getter 已確認。詳見 `guild-member-list-model-link.txt`、`guild-member-model-getters.txt`、`guild-member-fields.txt`、`guild-count-getters.txt`。
- GuildWarDataManager 正確 global0200a320 / AP01eb5c00；+78 的 10 個 CCArray 內容為 CCInteger，未證明是成員隊伍，不當作防禦資料。相關私密觀察 `guild-session-20261123/guildwar-container-counts.private.json`。
- 12.4.2 Ghidra 專案 `data/research/ghidra-12.4.2-targeted/LRNative1242Targets.gpr` 已保存；本輪只用 -process/-noanalysis 指定函式，沒有完整 auto-analysis，舊專案保留。最近伺服器已正常結束儲存。

## 本次重現與驗證

```powershell
python scripts/parse_runtime_characters.py --capture data/research/runtime.private/character-capture-20261123T030909Z-da0eaa --localization data/research/runtime.private/guild-session-20261123/lang_unit.ndb --output data/research/rangers-native-2405.json
python scripts/export_characters_website.py --source data/research/rangers-native-2405.json
python scripts/parse_runtime_guild.py --capture data/research/runtime.private/guild-members-20261123T033922Z-6a83ec --observation data/research/runtime.private/guild-session-20261123/member-general-team-observation.private.json
# 只有需要更新且遊戲已開啟成員名單時：
python scripts/runtime/read_guild_members.py
```

- 新擷取器限定版本／型別、最多 320 個 UI 節點／7 層／128 成員，檢查循環、重複指標、陣列界線與一致性；讀取失敗留紀錄。離線逐檔驗證 hash，拒絕重複 UID、索引、錯誤公會關聯及型別。部分名單不覆蓋舊有效快照。
- 角色／公會成功腳本與正常化結果、原始 manifest hash 保存在 `runtime.private/baselines/characters-guild-20261123`；舊 5／256／953 裝備及 15 角色／A-B 基準保留。原始副本仍保留原位置，不公開給前端。
- 本機 `http://127.0.0.1:3101/characters`、`/guild`、`/pvp`；dev 產物 `.next-local-dev`。目前角色總數、搜尋／101 頁分頁、詳情、公會名單／搜尋、A/B 防禦已通過 Edge 9 個桌機／手機案例，0 JS exception、無水平溢出／原始帳號及記憶體欄位洩漏。報告 `reports/character-defense-browser-validation.json`。
- 受影響 Python 解析／關聯／版本測試、TS 白名單與未知值測試、typecheck、lint、獨立 production build 已執行；最終結果見本輪交付及 `reports/build-local-validation-status.json`。953 裝備無關檢查未重跑；package.json / lockfile SHA 未變，沒有 Next 升級。

---

# 歷史狀態（2026-11-19，以下筆數與公會假設已由上方更新）

本文件是唯一目前狀態紀錄；舊 progress 與 Ghidra 報告是歷史證據。工作區目前沒有 `.git` 目錄，未執行提交、部署或 Supabase 正式資料更新。

## 目前交付：A/B 防禦驗證、技能關聯與版本相容準備

- 保存的12.4.0副本已解析 **A/B兩隊、10角色實例、30裝備實例**。角色模板10/10、裝備模板30/30皆匹配，未知ID0。4個重複模板都保留不同實例；30個裝備實例ID全不同。
- **30/30裝備unitInvenId匹配所屬角色invenId**：01218e08→virtual+0x150→0121bfe8→instance+0x98。強化全為+5，來源是currentEnchant→+0x58的checksum/XOR wrapper；不是maxEnchant+0x74、預設值或fallback。回歸測試修改maxEnchant為123仍取得+5，修改owner關聯則拒絕。
- A只目視核對防禦用途／採集時選用／5位置；B未目視核對，30件裝備名稱與強化尚未逐件目視核對。採集時間2026-11-19 02:27:23+08:00，來源12.4.0，不能當成裝置目前12.4.2的即時配置。
- 網站 **/pvp** 顯示A/B兩隊、各位置與三部位、實際強化、玩家範圍實例識別、模板連結、版本／時間／未讀取及目視狀態；過期狀態依來源仍未知。前端玩家代號去識別化，無原始帳號ID。import_defense_teams.py保留舊成功及其他玩家／隊伍，快取鍵包含玩家與用途，部分失敗不清空舊資料；每筆保留來源SHA。
- **角色15筆，來源為全域模板容器，非持有角色或隊伍實例**。原生invenId非0的副本會被模板解析器拒絕。欄位覆蓋：ID15、中文名稱15、類型15、屬性15、主技能ID11、主要能力ID10；星等0、已確認圖片0、已解析技能描述／數值0。新增關聯來自保存物件內的短字串，不依賴裝置或外站數值。/characters與詳細頁保留未知欄位。
- 主技能欄位：舊00e4e908→virtual+0x6b8→00c15328→+0x468；新版00e4ecf8→virtual+0x6c8→00c154e0→+0x480。主要能力舊+0x500、新+0x518，有葉函式證據。長字串未保存heap依賴時維持未知；不因技能缺失而捨棄有效基本資料。
- 詞條靜態路徑已建立：instance+0xb0 CCArray→0122d2fc(size78,AP01e990c0；新版0122d8f0/AP01e99700)，attrNo+18、valueGrade+20；0122d7f0計算內插／強化、0122ef1c定義百分比格式。**30件實際詞條ID與數值仍為0件可驗證**，缺少該陣列與元素的heap副本；額外效果／條件與倍率仍未完成。已準備read_defense_team.py --attributes，支援單件詞條失敗、原始ID及未知單位，不把空容器當沒有效果、不重複套倍率。模板效果仍為外部Rangerbook參考。
- 裝置目前 **12.4.2（201242）**，SHA1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0。與舊版不同，舊擷取器首先按SHA拒絕，沒有套用舊偏移。ADB pull模組副本已核對SHA；exec-out su cat會變換行的首份副本已標為.stream-invalid，未使用。
- 新版僅在獨立data/research/ghidra-12.4.2-targeted/LRNative1242Targets以-noanalysis匯入／續接、手動定義明確函式，無完整分析。原12.4.0專案未變更。新專案已保存；server34197及舊唯讀44909已結束，無背景原生擷取器。續接用-process libgame-12.4.2-pull.so -noanalysis，不重複import。
- 新角色布局：global01fd41e8、managerAP01e4db98、dict+28；DataUnitAP01e35410、size8e8；category+710、identity+714、behavior+448、element+750。舊8d0/6f8/430不可套入。names／grade／invenId／equipMap等已逐項核對；引擎容器Vtable來自dynsym。native_layouts.py依精確SHA分派，未知SHA拒絕。版本證據見reports/native-version-compatibility.json、reports/ghidra/version1242-*.txt。
- 新版只觀察到角色管理器型別，**尚無非空角色紀錄的執行驗證**；ownUnit／guild管理器在資源確認9%時未建立。沒有將這種未載入狀態解讀成沒有隊伍或公會，也未用新版本覆蓋目前可用資料。
- **公會總數未知、成員取得0、防禦隊伍0**。正常own guild manager新版01fe9a50/AP01e4f790→+18已定位；inspect_guild_context.py只檢查實際模型型別，不將舊GLSGuildData偏移套入未知物件。GuildData的guildMemberList/總數/分頁與此root的關聯仍未建立，沒有公會頁假資料。排名玩家0，無使用率、裝備統計或勝率。
- 雷電實例0曾正常重開、LDconsole adb恢復連線並runapp，但遊戲載入期間 **ADB多次離線**，root shell中斷；原因未確認，不歸因於LIAPP、不嘗試繞過。最新操作問題已詢問使用者：讓12.4.2正常進主畫面，再開「公會→成員名單」並保持開啟；若無公會或無法載入則回報該狀態。未操作登入、未改權限、未部署、未變更依賴。
- 本輪驗證：Python23項（實際防禦副本6、匯入／快取8、角色7、合併2）、TS資料邊界8、typecheck、lint、build通過；Edge桌面／390手機5案例通過，A/B共10角色／30部位、技能ID、未知值、原始帳號／記憶體欄位隔離皆通過。未重跑無變更的裝備全套。報告defense-instance-audit.json、defense-data-validation.json、character-defense-browser-validation.json。

## 成功基準（上一階段，12.4.0）

- Next 升級不是資料整合必要條件；已設 experimental.agentUpgrade=false，沒有啟用 Claude Code、安裝或升級依賴。package.json／lockfile 雜湊保持原值，證據 reports/next-upgrade-audit.json。專案仍 Next16.4.3。
- 本機角色模板 **15 筆**（原生普通角色5＋防禦涉及角色10），有 ID、中文名稱／敘述、STR/AGI/INT、行為類型及元素。原生 gradeRaw 已解析，但尚無角色星等 UI 關聯，所以 starCount=null；技能、進化與圖片映射仍未知。外部2321筆只留研究副本，網站不使用外部數字補欄位。
- 原生角色容器：DAT_01fd3b98 → manager(AP01e4d558)+0x28；DataUnit AP01e34de0、size0x8d0。完整欄位證據與離線驗證見 character-native-fields.txt、own-roster-layout.txt、parse_runtime_characters.py。GUARDIAN不計入角色數。
- 使用者已開啟自己的 PVP 防禦畫面，**不再要求重開**。已保存同時段私人截圖，明示防禦、隊伍(A)、小隊1及5個角色；主玩家與PVP玩家UID一致、usePvPTeamNo=1。實際擷取 A/B共10個角色實例、30個裝備；本輪標準化並顯示選用的 **A隊5角色／15裝備**。
- 防禦來源：DAT_01fe99c0(AP01e4f680) → virtual+a0／00f9e380 → manager+0x50；00f95eb0 明確將 playerUnitTeamGroupMap.pvpteam 對應kind5。00f96594 將JSON鍵1的五位置存為0..4、鍵2存為5..9。00f954b4 →00e54204解析角色實例；invenId+0x358(字串)/+0x370(uint64)一致，equipMap+0x378。不是一般編隊或戰鬥紀錄推定。
- 裝備實例為 AP01e986a8、size0x160；01218e08 的currentGrade→+0x50、currentEnchant→+0x58、invenId→+0x68有setter證據。選用隊15件均實際+5；實例詞條仍未解析。模板效果仍是具來源標記的外部Rangerbook參考，未當成實際詞條。
- 選用隊：u1618e-ka／u1535e-brown／u1571e-qs／u1631e-sally／u1646e-jessica。角色對應 **5/5**，裝備模板對應 **15/15 (100%)**，未知ID0。已核對防禦用途、A隊與5位置；裝備值尚未逐件以遊戲詳細畫面核對。取得時間2026-11-19 02:27:23+08:00，配置可能隨時間改變。
- 原始副本：runtime.private/defense-capture-20261118T182700Z-3ea7a5、character-capture-20261118T182737Z-4d8e2c；原普通角色5筆在character-capture-20261118T175648Z-641e5a。所有者UID、畫面與原始物件僅留私人區，不送前端。頁面使用雜湊玩家代號；實例ID保留玩家命名範圍。
- 可重現解析：parse_runtime_defense.py → observations.private.json → import_defense_teams.py → data/normalized/defense-teams.private.json。角色經 merge_native_characters.py 合併並拒絕重複ID衝突，整合為 data/research/rangers-native-fifteen.json → export_characters_website.py → data/normalized/verified-characters.json。read_character_objects.py新增--include-id可僅擷取實際缺少模板；不套裝備偏移。
- 本機頁面 /characters（名稱／ID搜尋、類型／元素篩選與詳細頁）、/pvp（真實防禦5位置、每位3部位、實際強化／實例識別、模板參考連結）。私人資料僅development讀取，production不發布。公會與排名仍無真實樣本，不計使用率或勝率。
- 新增／受影響驗證：Python17項（防禦原始副本4、匯入5、角色6、合併2）、TS資料邊界8項、typecheck、lint通過；production build通過。Edge/CDP桌面／390手機5案例通過，無JS例外、橫向溢出、原始UID或記憶體欄位外洩；見 reports/character-defense-browser-validation.json、defense-data-validation.json。未重跑無變更的裝備全套檢查。
- 本輪快照與成功腳本保存在 runtime.private/baselines/characters-defense-20261119；既有裝備5/256/953基準不動。只讀su、已核對12.4.0模組SHA，不附加Frida、不改權限、不修改遊戲檔或部署。

### 本階段離線重現（不連裝置、不重新擷取）

```powershell
python scripts/merge_native_characters.py --source data/research/rangers-runtime-five.json --source data/research/rangers-defense-ten.json --output data/research/rangers-native-fifteen.json
python scripts/export_characters_website.py --source data/research/rangers-native-fifteen.json
python scripts/parse_runtime_defense.py --all-teams --capture data/research/runtime.private/defense-capture-20261118T182700Z-3ea7a5 --output data/research/runtime.private/defense-capture-20261118T182700Z-3ea7a5/observations-ab.private.json
python scripts/import_defense_teams.py --input data/research/runtime.private/defense-capture-20261118T182700Z-3ea7a5/observations-ab.private.json
```

畫面人工核對綁定 capture 內 screen-verification.private.json 的SHA；解析器不會僅因存在截圖就宣稱完成目視核對。原始帳號與物件不供前端；本機網址 http://127.0.0.1:3101/characters 與 /pvp。目前即時資料受裝置離線阻擋，使用者操作需求見上方目前狀態。公會名單與排名來源尚未取得，未建立虛構資料或擴充統計。

## 已完成與資料邊界

- 真實本機裝備：觀察／擷取 **953**，成功解析 **953**，錯誤、重複、衝突均 **0**。
- 捕獲來源為遊戲 12.4.0（versionCode 201240）載入後的模板容器。已到 null tail，容器鏈與頭指標一致；**已載入容器遍歷完成，全遊戲覆蓋仍未知**。參考站同樣 953 筆也不能單獨證明全遊戲完整。
- 模組 SHA256：`8795d855d2f0aff223c93d6ee7ea3cadd01859dbbbaa15846a07dbfcf07b5d97`。資源版本未取得。
- 原始 `game_item_equip.db` 外層解密**尚未完成**；本次成功是執行時物件副本的離線解析，兩者分開。
- 原始 5 筆、256 筆快照，以及成功腳本仍保留。953 筆來源：`data/research/runtime.private/capture-20261117T162047Z-e6bc01`。離線結果：`data/research/equipment-runtime-loaded953.json`。
- 封存：`runtime.private/baselines/equipment-five-20261117` 的 36 檔、`loaded953-20261118` 的 5 檔與來源 capture manifest 雜湊均通過核對，見 `reports/equipment-baseline-validation.json`。
- 擷取器每個觀察節點計數，失敗也消耗上限；上限 2048 節點、32 MB、20000 次讀取，另有期限。檢查循環、指標、型別、容器變化及相同 ID 衝突。重啟程序時不得沿用舊指標；僅同一 PID／模組／容器可續接。

| 裝備 ID | 本機星等／類型 | 本機其他欄位 |
| --- | --- | --- |
| eq_2202_amr_06 | 6／ARMOR | maxEnchant=5、詞條數3～3、goodGearAttr=0 |
| eq_2202_wpn_07 | 7／WEAPON | goodGearAttr=150006 |
| eq_2202_wpn_17 | 7／WEAPON | goodGearAttr=160015 |

制服名稱為 `[YSH]` 加換行及 `日暮永遠的制服`。星等來自已驗證 grade wrapper 解碼／校驗與星星 UI 呼叫鏈，未從檔名推測。欄位來源見離線結果的 `fieldEvidence` 與 `reports/ghidra/equip-static-record-json.txt`、`equip-static-grade-unpack.txt`、`equip-static-star-count.txt`。

## 效果：本機與使用者確認的參考來源

- **本機裝備的效果關聯仍尚未解析**，保留 `effects:null`／`effectsStatus:unparsed`。空 CCArray 與 goodGearAttr=0 均不能解讀成沒有效果。
- 已從保存的本機 `unit_eqip_attr` 物件解析 10 筆屬性定義（1011～1014、1021～1024、1031～1032）：attrNo、reinforceType enum、valueDivideGrades、min/max float32。單位、顯示倍率、裝備關聯仍未知，沒有把它們套到制服。腳本 `parse_equipment_attribute_definitions.py`；結果 `data/research/equipment-attribute-definitions-sample.json`。證據：`equip-unit-attribute-json.txt`、`equip-attribute-definition-fields.txt`。
- 依使用者確認，網站本機預覽可直接使用 **Rangerbook / WarmyCat 外部對照**。953 個 ID／星等／類型皆與本機吻合，0 衝突；有基本效果953件、高級377件、Skill+167件、Spec+35件。
- 真實頁面引用的公開來源：`https://rangerbook.warmycat.com/gear/` → `assets/js/v2-data.js?v=20261013-thai1` → `res/v2/equipment.json`、`res/v2/equipment-effects.json`、`res/v2/fast/locales/zh_TW.json`、`res/v2/locales/custom.json?v=20261013-thai1`。顯示規則來自 `assets/js/gear-detail.js?v=20261102-number-format1`。原始公開副本保留在忽略目錄，未整站鏡像或熱連結圖片。
- URL、取得時間、各來源 SHA256、規則及版本缺口見 `reports/equipment-reference-identities.json`。外部未提供明確遊戲／資源版本；發布授權未確認，故僅 development 啟用外部對照，production 保持本機已驗證模板及未知效果狀態。
- 外部精確 ID：150006→`EQUIP:GEAR_FILTER_ATK_SPE_MUL_nm`（攻擊速度）；160015→`EQUIP:GEAR_FILTER_ATK_RNGE_MUL_nm`（攻擊範圍），分別與兩件武器的預設高級效果一致。這是可重現外部對照，**本機 goodGearAttr 使用端的查表證據仍未建立**。見 `reports/equipment-reference-comparison.json`。
- 制服外部模板範圍：+0 閃避5～8%、技能閃避5～8%、物理反彈1.5～3%；+5 分別30～48%、30～48%、9～18%。基本效果依來源乘以等級+1；其他效果只使用實際提供的 upgradeStep。Spec+ 的效果機率、係數、時間依各自明列增量；敘述及外層啟動機率保留 +0 並標示。未以去 padding、可讀字串或外站數值宣稱本機解析成功。

## 網站與隔離

- `/`、`/gear`：名稱／ID、星等／類型、基本／高級／Skill+／Spec+ 支持的效果與條件複選、AND／OR、清除、筆數、穩定排序、每頁24筆。
- `/gear/eq_2202_amr_06_nm`：6星 ARMOR、強化上限、詞條數、取得時間、本機未知狀態；外部對照具來源標示與 +0～+Max 切換。7星高級效果及 Spec+ 也已實際驗證。
- 保留本機 APK 圖示候選與缺圖替代，不對外站圖片發請求。名稱的換行只在各自正確資料邊界處理；外部原始雙斜線遵循其公開 catalog renderer。
- `verified-equipment.ts` 是 server-only 白名單；原始副本、記憶體參數、金鑰及帳號資訊不進前端。外部 preview、原始遊戲檔、runtime.private 皆已忽略。
- 舊虛構 JSON 已移至 `tests/fixtures/legacy-ui-prototype`；`/data/gear.json`、`/data/rangers.json`、`/data/guilds.json` 及私有研究路徑皆 404。
- `/translations` 保留既有 Supabase 已發布翻譯；已驗證裝備查詢不依賴翻譯服務可用性。

## 角色／PVP／公會

- 角色：15筆原生模板已本機顯示；已驗證獨立容器／欄位與本機翻譯。已新增主技能ID11筆與主要能力ID10筆；星等UI關聯、技能描述／數值及圖片仍未知。
- PVP：已取得自己帳號A/B兩隊（10角色／30裝備）並顯示；無排行榜／排名玩家範圍或跨玩家防禦樣本。`data_contracts.py`、`pvp_statistics.py` 已備妥：驗證快照、同玩家取最新嘗試、失敗不回填舊成功、有效玩家作分母、出場次數與玩家數分開、配裝只組合同一角色實例的三部位。沒有戰鬥結果，所以 winRate 為未知。
- 公會：缺真實會員名單及成員防守隊伍來源。資料介面區分 PVP／公會戰用途、會員快照／玩家／角色實例／部位、未知與未穿戴、取得失敗；fixture 僅用於測試，只有上述本機私人PVP隊伍，沒有公會隊伍或使用率資料。
- 此輪不再附加 Frida、不繞過 LIAPP／登入、不更改裝置權限、不重跑完整 Ghidra 分析。

## 重現與驗證

優先離線，不需裝置在線：

```powershell
python scripts/parse_runtime_equipment.py --capture data/research/runtime.private/capture-20261117T162047Z-e6bc01 --localization data/extracted/lr_20261116T212608096_7b99bdd0/assets/res/tutorial_res/db/lang_equip/lang_equip.ndb --output data/research/equipment-runtime-recheck.json
python scripts/export_equipment_website.py --source data/research/equipment-runtime-recheck.json
python scripts/parse_equipment_attribute_definitions.py
python scripts/build_equipment_reference_preview.py
$env:LR_NEXT_DIST_DIR = '.next-local-dev'
npm.cmd run dev -- --hostname 127.0.0.1 --port 3101
```

僅缺必要副本時才重新擷取：`python scripts/runtime/read_equipment_objects.py --max-nodes 2048 --max-seconds 900`。原始 5／256／953 筆成功來源不覆寫。

```powershell
python -m unittest discover -s tests -p 'test_*.py'  # 63通過
npm.cmd test                                      # 23通過
npm.cmd run typecheck
npm.cmd run lint
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_website_build.ps1
python scripts/verify_equipment_http.py
python scripts/verify_equipment_browser.py
```

`verify_website_build.ps1` 僅清除指定 `.next-local-*` 產物的唯讀屬性，以處理 OneDrive EPERM，不刪除來源。Next 16.4.3 production build 成功，見 `reports/build-local-validation-status.json`／`.log`。

本機實際驗證：Edge/CDP 10案例（390手機／1440桌面、圖片解碼完成、搜尋表單、清除、AND／OR、分頁、直接網址、+5與重新整理），0 JS例外與橫向溢出；開發／production 各13 HTTP案例通過。Production 使用3102本機短暫驗證，不部署。前端12個JS檔、599458 bytes稽核無私有欄位。報告：`website-browser-validation.json`、`website-http-validation.json`、`website-http-production-validation.json`、`website-client-bundle-audit.json`。截圖留在 `runtime.private/browser-qa/`。

本機預覽：`http://127.0.0.1:3101/gear`；目標：`http://127.0.0.1:3101/gear/eq_2202_amr_06_nm?level=5`。
