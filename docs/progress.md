> 最新可續接狀態請見 [current-state.md](current-state.md)；本檔保留歷史進度。

# 資料研究進度

## 已完成

- 已閱讀工作區 `README.md` 與 `.gitignore`；在工作區及其上層位置未找到適用的 `AGENTS.md`。
- 環境檢查：Node.js `v24.14.0`、npm `11.9.0`、Python `3.12.6`、Git `2.49.0.windows.1`。
- `adb.exe` 不在 PATH；已於常見雷電安裝位置找到 `C:\LDPlayer\LDPlayer9\adb.exe`。
- 建立 `data/raw/`、`data/inventory/`、`data/extracted/`、`data/normalized/`、`data/overrides/`、`reports/`、`scripts/`、`docs/`。
- 更新 `.gitignore`，排除原始／解包資料、遊戲封裝檔、私人資料及本機環境檔，保留 `.env.example`。
- 執行 `adb devices -l`：目前有一台已連線裝置 `emulator-5554`（`device`，型號 `SOV44`）。
- 本階段未建立網站功能、未擷取遊戲檔案，亦未新增或產生遊戲資料。

## 第二階段：本機資料取得

- 使用者確認第三方套件 `com.linecorp.LGRGS` 為 LINE Rangers。
- 記錄版本 `12.4.0`（versionCode `201240`）、Android `9`（API `28`）、裝置 ABI `x86_64` 與 snapshot 時間。
- 建立 snapshot `lr_20261116T212608096_7b99bdd0`；由 `pm path` 查得並匯出 base APK 及 3 個 split APK。
- 兩個指定的外部資料／OBB 路徑均回報 `No such file or directory`；未匯出其內容。
- 檢視 APK 後，抽取 9 個具標準 SQLite 標頭的靜態資產；未解密其他資料檔或讀取玩家資料。
- 產生 `data/raw/lr_20261116T212608096_7b99bdd0/manifest.json` 與 `reports/acquisition.md`。
- 未清除遊戲資料、重裝、啟用 Root 或變更系統權限。

## 第三階段：遊戲檔案辨識

- 建立可重跑的 `scripts/inventory_game_files.py`；依檔頭與內容辨識格式，將 APK ZIP 安全解壓至 `data/extracted/<snapshot-id>/apk_contents/`。
- 設定 APK 合計 20,000 檔、1 GiB 未壓縮大小、單檔 512 MiB 的限制；拒絕路徑穿越、絕對路徑、保留名稱、符號連結、重複路徑及帶 ZIP 加密旗標的成員。已用路徑穿越案例驗證拒絕結果。
- 完成 4 個 APK、5,979 個 ZIP 成員的盤點；輸出 `data/inventory/lr_20261116T212608096_7b99bdd0/inventory.json`。
- 找到並核對 JSON 資源索引；`unit.db` 與 `game_item_equip.db` 的大小及計算 MD5 均與索引項目吻合。
- 驗證 `lang_equip`、`lang_guild` SQLite 表的欄位與繁中樣本，並檢視角色圖集 ZIP 中的 plist frame 索引。
- 產生 `reports/data-sources.md`，記錄可信度、未知二進位檔頭、引擎判斷及待取得內容。

## 第四階段：首個真實資料解析器

- 裝備主檔 `game_item_equip.db` 已被證實是索引所指的資源，但不是標準 SQLite，實際記錄欄位仍未確認；角色主檔 `unit.db` 同樣無法直接讀取，因此不把它們當作可解析資料。
- 選用已驗證可讀的 SQLite `lang_equip` 表作為第一個真實資料來源。此表是裝備相關本地化文字，不是裝備物品清單；其欄位為 `dataCode`、`language`、`msgType`、`msg`，主鍵為 `(dataCode, language)`。
- 新增 `scripts/parse_equip_localization.py`，讀取 manifest 記錄的檔案，核對大小與 SHA-256、SQLite 完整性及表結構後，以唯讀方式匯出資料；缺少／重複來源識別會明確報錯。
- 匯出的裝備 ID、物品名稱、分類、星數、原始數值、效果參數、顯示值及圖片對應均保留 `null`；資料行用原始 `(dataCode, language)` 識別，不將翻譯代碼誤當裝備 ID。沒有已確認單位換算，因此不轉換數值。
- 產生 10 筆繁體中文真實翻譯記錄及遊戲畫面核對 CSV；該核對表明確將物品名稱、星數與數值標示為 `unknown`，僅供核對來源文字，不宣稱已有裝備物品資料。
- 測試檔 `tests/test_parse_equip_localization.py` 使用的假資料僅存在測試程式中。
- 實際驗證：來源 SQLite `integrity_check=ok`，manifest 檔案大小／SHA-256 相符；`zh-Hant` 有 1,346 筆來源行，輸出 JSON 與 CSV 各 10 筆。首筆實際資料為 `ENHANCE_TITLE`／「強化」。5 項單元測試、Python 編譯檢查及輸出 JSON／CSV 欄位核對均通過。
- 當時 JADX 不在 PATH；本階段未宣稱已追查主檔解碼方式，未推測或補造任何裝備屬性。後續工具追查結果見第十階段補充。

可重複執行的命令：

```powershell
python scripts\parse_equip_localization.py --snapshot lr_20261116T212608096_7b99bdd0 --language zh-Hant --limit 10
python -m unittest discover -s tests -p "test_parse_equip_localization.py"
```

輸出位置：

- `data/normalized/lr_20261116T212608096_7b99bdd0/equip_localization.json`
- `data/normalized/lr_20261116T212608096_7b99bdd0/equip_localization_review.csv`

## 第五階段：Supabase migration 與匯入流程

- 依正規化 JSON 的真實結構建立 `ranger_dataset_versions` 與 `ranger_equip_localizations`；目前沒有可用的裝備／角色 game ID，因此不建立或填充虛構的裝備／角色主檔，也不把 `dataCode` 改稱 game ID。
- 資料列的版本內唯一鍵是 `(snapshot_id, data_code, language)`，沿用 `lang_equip` 原始 `(dataCode, language)` 識別；同 snapshot 的重跑以 upsert 避免重複，snapshot 不同則保留為不同版本。
- migration 將新版本先寫為 draft；匯入程式核對遠端版本、筆數與每筆原始記錄後，才呼叫交易式發布函式。發布新版本時舊版本改為 archived；中途失敗不切換現行版本。
- 兩表皆啟用 RLS；匿名／已登入公開角色只能讀取 published 版本的必要文字欄。來源路徑、雜湊、原始 JSON 與研究警告不授予公開讀取，且沒有公開寫入權限或寫入 policy。
- 新增 `scripts/import_supabase.py`，預設 dry-run；只有 `--apply` 才連線寫入。使用 `SUPABASE_SECRET_KEY` 作為伺服器端 API key，程式只傳送 `apikey` 標頭、不輸出 key；匿名驗證使用 publishable key。圖片欄位目前皆未知，未建立 Storage 物件或上傳圖片。
- 新增 `.env.example`，所有四個變數都只有空白占位符；既有 `.env.local` 不納入 migration 或程式碼。
- 本機驗證：匯入器重新核對本機 SQLite 完整性及每筆翻譯原文，並驗證來源檔案 SHA-256；完整 unittest **15 項通過**，Python 編譯檢查通過，dry-run 輸出 10 筆／0 個本機驗證錯誤且未發出網路請求，migration 權限結構靜態檢查通過。
- 尚未連線或寫入實際 Supabase；本環境找不到 Supabase CLI 與 `psql`。因此 migration 尚未執行、正式匯入與匿名 API 驗證尚未完成。

檔案：

- `supabase/migrations/20261116223000_ranger_localization_import.sql`
- `scripts/import_supabase.py`
- `tests/test_supabase_import.py`
- `.env.example`

確切執行步驟：

1. 在 PowerShell 複製 migration，再到 Supabase Dashboard → SQL Editor 貼上並執行：

   ```powershell
   Get-Content 'supabase\migrations\20261116223000_ranger_localization_import.sql' -Raw | Set-Clipboard
   ```

2. 本機 dry-run：

   ```powershell
   python scripts\import_supabase.py --dry-run
   ```

3. 確認 `.env.local` 中的 server secret 已輪替，且不要將 secret 貼到聊天或 commit。於同一個 PowerShell 視窗載入變數並正式匯入：

   ```powershell
   Get-Content '.env.local' | ForEach-Object {
       if ($_ -match '^\s*([^#=]+)=(.*)$') {
           [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2], 'Process')
       }
   }
   python scripts\import_supabase.py --apply
   ```

4. 匿名讀取／私有欄位及公開寫入權限驗證：

   ```powershell
   python scripts\import_supabase.py --verify-anon
   ```

## 第六階段：Next.js 真實資料網站

- 沿用工作區既有 Next.js App Router；以 TypeScript strict Server Components 查詢 Supabase，網站資料層只使用 URL 與 publishable key，不使用 secret key。
- 列表、繁中翻譯文字／原始代碼搜尋、固定排序與分頁由 Supabase 執行；詳細頁只查詢目前 published snapshot。新增短期 60 秒快取。
- 更新 migration，新增 `SECURITY INVOKER` 的 `ranger_search_equip_localizations` RPC；公開角色僅可執行該讀取函式，函式依 RLS 查詢已發布資料，且限制關鍵字長度、頁碼與每頁筆數。
- 網站明確標示現有來源是「裝備相關文字記錄」，不是裝備圖鑑；星數、類型、效果數值及圖片均顯示未知，不載入 `public/data/` 的虛構示範 JSON。
- 新增載入、無已發布資料、搜尋無結果、Supabase 連線失敗及詳細頁不存在狀態；目前未設定資料 fallback。
- 新增 Vitest data-layer 測試、ESLint 設定與 runtime validation eval plan。獨立 runtime validation 的型別檢查、lint、production build、4 項測試及列表／詳細頁 HTTP 路由探測均通過。
- 舊有 Python parser／Supabase 匯入回歸測試另行執行，15 項通過。
- 本機 production route 探測：首頁與 `/gear/ENHANCE_TITLE` 均回 HTTP 200，但兩頁顯示 Supabase 查詢失敗；HTTP 探測只確認路由可回應，尚無法用真實已發布資料驗證列表點入詳細頁的資料流程。
- Supabase migration 尚未套用、資料尚未正式匯入；匿名 RLS 實際驗證仍待部署資料庫後執行。
- 瀏覽器錄製依使用者選擇改採 HTTP 探測；未安裝 Playwright 或 Chromium。

網站啟動及檢查：

```powershell
npm ci
npm run dev
npm run typecheck
npm run lint
npm test
npm run build
```

正式資料可讀取前，請先完成第五階段的 migration、dry-run、`--apply` 與 `--verify-anon` 步驟；網站網址為 `http://localhost:3000`。

## 待確認與限制

- 外部資源目錄目前不存在；若要再次檢查，需在正常使用遊戲後另行確認，不預設改動裝置狀態。
- 角色／裝備主資料 `.db` 有資源索引與校驗值證據，但不是標準 SQLite；內容欄位仍未確認。
- APK 資源索引列出 `lang_unit` 與多個 ZIP 資源包，本次沒有找到對應的完整版本化檔案。
- 遊戲引擎尚未確認；不能只依通用原生函式庫名稱判定。

## 下一步

1. 在使用者正常啟動模擬器後，以確認的 `adb.exe`、`emulator-5554` 與 `com.linecorp.LGRGS` 重試 `acquire`；不得清除、重裝或改權限。
2. 如需角色／裝備清單，先在文件要求的 64-bit JDK 21 環境用 Ghidra 追查 `libgame.so` 中 `res_base_hd.txt`、`game_item_equip` 及 `eqip_*` 資源的讀取路徑，再據實作建立解析器；不要把翻譯代碼當成裝備 ID。
3. 先確認公會名單與 PvP 排行的合法、可驗證來源，再逐段測試公會→成員→隊伍用途→三件裝備→圖鑑名稱；不得用參考站私有介面或推測 API。
4. 檢視並在測試資料庫套用多模組 migration；來源 adapter 與 read model 核對成功後，才驗證匿名 published-only 讀取。migration 尚未執行。
5. 完成一次手動端到端更新前，不設定定時工作。

## 工作區現況備註

- README 描述此工作區已有 Next.js 原型及示範資料；該既有內容不屬於本階段，未修改也未將其當作真實遊戲資料。

## 第七階段：四模組需求、來源覆蓋與手動更新流程

### 本次實際完成

- 建立 [docs/data-coverage.md](data-coverage.md)：分別記錄角色、裝備、PvP、公會的已取得／缺少／未確認欄位，以及公會成員防守裝備資料鏈卡點。
- 建立 [docs/requirements.md](requirements.md) 與 [docs/architecture.md](architecture.md)：保留完整四模組範圍，記錄現有 Next.js／Supabase 原型及不遷移決策，並調整以來源可驗證性為 gate 的開發順序。
- 建立 [docs/data-pipeline.md](data-pipeline.md) 與 `scripts/data_pipeline.py`，實際提供 `acquire`、`inventory`、`parse`、`validate`、`diff`、`import`、`publish` 命令。inventory 與 parse 改採唯一 run 目錄，避免重跑覆蓋舊結果。
- 新增 `scripts/diff_data.py`：重新計算 manifest 內檔案 SHA-256，再比較檔案與 normalized fields；缺少列一律標示未觀察到，不判為官方刪除。
- 建立 `scripts/data_contracts.py`，區分 PvP／公會戰用途、成功／失敗／不可取得、已裝備／未裝備／未知；公會名單 snapshot 與隊伍 snapshot 可分開保存。
- 新增 `scripts/import_research_bundle.py`，提供多模組研究 bundle 的來源 SHA、snapshot manifest、唯一識別與敏感欄位名稱驗證；dry-run 預設不連線，`--apply` 僅 stage 私有 raw research rows，`publish` 分開執行且資料庫 gate 仍要求 typed read model。
- 新增 `supabase/migrations/20261117000000_ranger_multimodule_research.sql`，涵蓋四模組及共用 snapshot、guild roster、player team、PvP ranking、usage stats 等資料模型。此 migration **尚未在實際資料庫執行或 SQL 解析器驗證**；所有新表預設 RLS 私有且沒有匿名讀取 policy。
- 保留舊 10 筆輸出，新增全量 `lang_equip:zh-Hant` 解析 run `equip_20261116T153030490722Z_e602f5e9`，並透過 pipeline 產生 `equip_pipeline_20261116`：來源與輸出各 1,346 列，SQLite 完整性 `ok`，來源 manifest／原始檔大小及 SHA-256 通過檢查。資料仍為翻譯標籤，不是裝備主檔。
- 建立 `reports/diffs/verified-sha-diff/`：同一 raw snapshot 的 13 個檔案逐一重新雜湊並與 manifest 相符；相較舊 10 列樣本新觀察 1,336 筆翻譯列，10 個共同識別無欄位變更；沒有推定刪除。
- 以新 run-id 實際重跑 inventory：`data/inventory/lr_20261116T212608096_7b99bdd0/runs/inventory_20261116T160258763422Z_7cac513b/inventory.json`，5,984 個檔案記錄、4 個 APK，未覆蓋舊盤點。
- 用已確認 ADB 路徑與 `-s emulator-5554` 實際重試取得，錯誤為 `error: device 'emulator-5554' not found`。保存 partial snapshot `lr_20261116T235245917571_b848fd4e`，`complete=false`、APK 檔案數 0；未重裝、清除資料或更動模擬器。
- 因工作區沒有已確認動態來源，目前未取得 PvP 排行、任何公會名單／成員隊伍／裝備；不能宣稱取得 PvP 防守或公會戰防守資料。角色與裝備主檔仍是未解碼二進位。
- 更新 [reports/acquisition.md](../reports/acquisition.md) 與 [reports/data-sources.md](../reports/data-sources.md) 記錄全量解析及實際取得錯誤。

### 驗證結果與未完成

- `python -m unittest discover -s tests -p "test_*.py"`：**38 項測試通過**，涵蓋翻譯解析、研究 bundle 完整性、快照差異、匯入 idempotency、隊伍用途、成員映射、未知／未裝備狀態及 migration RLS gate。
- parser 全量輸出以 `scripts/data_pipeline.py validate` 重新比對 SQLite 原文：1,346 列、完整來源覆蓋，通過。
- `scripts/data_pipeline.py --help` 已列出七個命令。
- Pylance 對本次新增／修改 Python 程式執行診斷：無診斷；全量測試與兩個真實 parse run 均通過。
- Supabase 舊翻譯 migration 與新多模組 migration 均未套用；沒有連線、匯入、發布或匿名權限驗證結果。
- 多模組 research bundle 格式已由明確標示的 `tests/` 測試 fixture 測試；沒有真實 PvP／公會 bundle，也尚無 source-specific parser 將 raw research row 映射成公開 read model。
- Next.js 網站未改動，仍只有翻譯文字原型；沒有執行本次 TypeScript/build 流程。

重複命令與格式見 [docs/data-pipeline.md](data-pipeline.md)；模組資料來源狀態見 [docs/data-coverage.md](data-coverage.md)。

## 第八階段：Supabase 發布及網站真實資料驗證

### 本次實際完成

- 專案安裝的 Supabase CLI `3.1.0` 可由 `npm.cmd exec -- supabase` 執行；已初始化 `supabase/config.toml` 並連結使用者指定的專案。
- 以 CLI dry-run 確認待處理 migration 後，只套用網站目前需要的 `20261116223000_ranger_localization_import.sql`，並將其版本記錄為 applied。多模組研究 migration `20261117000000_ranger_multimodule_research.sql` 仍未套用；目前 CLI 遠端狀態顯示舊 migration 已 applied、新 migration pending。
- 以 `scripts/data_pipeline.py validate` 驗證全量來源；匯入器 dry-run 顯示 1,346 筆、0 個本機驗證錯誤。之後以 `--apply` stage，逐列核對後另行發布 snapshot `lr_20261116T212608096_7b99bdd0`。
- 從資料庫確認發布版本狀態為 `published`，宣告筆數及實際列數皆為 1,346。發布前資料庫沒有其他已發布版本。
- 匿名公開讀取驗證通過：可讀取已發布列；未發布版本與來源私有欄位不可讀；公開角色沒有寫入權限。
- 修正匿名驗證器一次抓取超過 Supabase REST 預設列數上限的問題，改以 500 筆分頁完整核對；新增 1,346 筆／三頁的分頁測試。
- 啟動 Next.js 開發網站；首頁、搜尋 `強化` 及 `/gear/ENHANCE_TITLE` 都回 HTTP 200，頁面實際顯示資料庫中的繁中原文。未知星數、效果及圖片仍清楚標示未知。
- 在 `.gitignore` 排除 Supabase CLI 產生的 `supabase/.temp/`；更新 README 與資料流程文件記載目前發布狀態及多模組 migration 尚未套用。

### 限制與驗證結果

- 網站網址：`http://localhost:3000`。網站目前顯示 1,346 筆裝備相關翻譯文字，不代表已取得裝備清單；角色主檔、裝備主檔、PvP 與公會資料仍缺少可核實來源。
- Python 匯入器測試：15 項通過；匿名權限驗證通過；本機首頁、搜尋與詳細頁 HTTP 探測通過。
- Supabase REST 單次回傳筆數有限制；已在驗證工具中處理分頁，未更改網站伺服器端分頁行為。
- 四模組研究 migration 仍未經 PostgreSQL 實際驗證或套用。由於它目前是 CLI 的待處理 migration，正式執行 `supabase db push` 前需先完成該 migration 的驗證。

## 第九階段：精簡裝備頁與本機圖示候選

### 本次實際完成

- 隱藏訪客不需要的語言、發布時間、snapshot ID、訊息類型及未知欄位；保留翻譯文字、原始代碼及遊戲版本。
- 以 1,171 筆 `_nm` 名稱代碼逐一比對 APK `gear_icon` 目錄，884 筆找到完全相同檔名主幹的 PNG。網站列表及明細可顯示這些**候選圖示**；這不是裝備主檔驗證。
- 圖示只由開發模式的 loopback localhost 路由讀取原始解包檔；路徑經 `realpath` 限制在指定資產目錄，並核對 PNG 檔頭。沒有複製到 `public/`、資料庫或正式網站。尚未確認公開使用權前，production 不提供圖示。
- 角色、PvP、公會仍是資料來源狀態頁，不是可搜尋的真實資料功能；角色／裝備主檔、排行榜、玩家防守隊伍與公會名單仍未取得。保留四模組導覽，不以假資料填補。

### 驗證結果與未完成

- `npm.cmd run typecheck`、`npm.cmd run lint`、`npm.cmd test` 均通過；Vitest 6 項通過。
- `npm.cmd run build` 首次受 OneDrive `.next/server/app/gear` 雲端 reparse placeholder 的 `EPERM` 阻擋。改用暫時的隔離輸出目錄完成 production build，路由編譯成功；已移除臨時設定／輸出並還原 `tsconfig.json`。
- 本機頁面與明細 HTTP 200；搜尋列表含候選圖示 URL；圖示端點回傳 `image/png`、10,475 bytes，PNG 簽章核對成功；不合法資產 ID 回 HTTP 404。
- 本機網站已重新啟動：`http://127.0.0.1:3000`。此環境的 production build 必須避開目前的 `.next` OneDrive reparse placeholder；若再次驗證，先確認該路徑狀態，不要直接刪除 reparse point。
- 下一步若要實作真正的角色／裝備圖鑑，需先解析已取得的 `unit.db`／`game_item_equip.db` 欄位及 ID 映射；若要公開展示圖片，需先確認授權。PvP／公會功能則需先取得合法且可重現的動態資料來源。

## 第十階段：目標裝備欄位追查與換行顯示修正

### 逐層結果

- 目標 `eq_2202_amr_06_nm` 在 `lang_equip.ndb` 只有名稱翻譯列；normalized 的 `gameId`、星等、數值、效果參數、顯示值及圖片映射均為 `null`，並帶有「不是裝備主檔」警告。
- APK 內確有 `game_item_equip.db`（241,664 bytes），MD5 與資源索引簽章相符；但檔頭不是 SQLite，唯讀 SQLite 開啟回報 `file is not a database`，目前無可讀欄位。索引的 `/game_item_equip/game_item_equip_1793330182433.db` 未出現在本次 inventory；APK 包裝內的同尺寸／同簽章資料仍存在。
- 全部 9 個已取得 SQLite 資產中，目標名稱鍵只在 `lang_equip.dataCode` 出現；沒有可驗證的星等、效果 ID、數值或 Spec+。目標 PNG（8,449 bytes）存在，但映射仍未由主檔驗證。
- migration、匯入器、公開查詢與前端型別都只有翻譯欄位；匯入器會拒絕把此資料集冒充裝備物品。沒有新增裝備資料表或匯入不存在的效果。
- 原始 SQLite 訊息分隔是兩個字元 `0x5C 0x6E`，不是 LF；讀取層現在保留 `message` 原文，另提供單次換行處理後的 `displayMessage`。雙反斜線序列不再解碼，實際 LF 原樣保留。
- 詳細頁逐項標示星等／部位、基本／高級效果、技能／Spec+、強化數值為「尚未取得」；不把未知標成無效果或不適用，候選圖片仍保留候選狀態。
- 原先的有限 DEX／`.so` 搜尋尚未涵蓋原生庫字串；後續確認 `split_config.arm64_v8a.apk` 中有 19 個 `.so`，其中 `libgame.so` 是 32,292,472 bytes 的 ELF64 AArch64 檔案，含 `res_base_hd.txt`、`resourcePath`、`resourceId`、`game_item_equip` 及多個 `eqip_*` 字串。
- JADX 1.5.6 官方 release 已驗證並用於 `base.apk`；`assets/.tzyxaxtyd.dex` checksum mismatch，解碼仍有 187 個錯誤，LINE Rangers Java 包中沒有裝備資源名稱。
- Ghidra 12.1.2 官方 release 已核對 SHA-256，安裝於使用者本機程式目錄；早期 Java 24、300 秒執行逾時。後續改用文件要求的 64-bit JDK 21，1,200 秒分析成功並保存專案；仍有部分 AArch64 分析錯誤，不能歸因於 Java 版本。
- 對 136 個取得的 `.db`／`.ndb` 搜尋目標 `eq_2202_amr_06_nm` 與候選字串 `eq_2202_amr_06`，只有 `lang_equip.ndb` 命中；其他原始二進位沒有可直接搜尋的明文鍵，不能因此推定沒有編碼／索引映射。
- `game_item_equip.db`、`game_item.db`、`eqip_*`、`unit_eqip_*`、`skill.db`、`ability.db` 與天賦候選檔均已存在於 APK，檔案大小及 MD5 與資源索引吻合；inventory 將其辨識為非 SQLite 二進位。現況是資料位元組已取得、專有格式的解析器／欄位映射未建立，不能確認目標裝備星等或詞條。
- ADB 以已確認路徑與序號重查仍回報 `error: device 'emulator-5554' not found`，沒有新取得或修改原始檔。

### 本次修改與驗證

- 修改 Supabase read model、裝備列表／詳細頁及 CSS；新增 raw message 與 display message 的分離測試，更新來源報告、覆蓋狀態與 README。
- `npm.cmd run typecheck`、`npm.cmd run lint`、`npm.cmd test` 通過；Vitest 7 項、Python unittest 39 項通過。
- Production build 以暫時的 `.next-validation` 輸出目錄成功；一般 `.next` 仍受 OneDrive reparse placeholder 的 `EPERM` 阻擋。臨時 build 設定與輸出已清除，`tsconfig.json` 已還原。
- 現有全量翻譯 importer dry-run：1,346 列、0 個本機驗證錯誤，明確顯示只匯入翻譯文字。沒有 reimport／發布或 Supabase schema 變更。
- 本機 `/gear/eq_2202_amr_06_nm` 回 HTTP 200；HTML 顯示換行後名稱及未知欄位狀態；候選 PNG 回 HTTP 200、8,449 bytes。

## 第十一階段：裝備二進位格式與 Ghidra 讀取鏈

- 環境：Temurin JDK `21.0.13+9`、Ghidra `12.1.2`。透過 `scripts/run_ghidra.ps1` 僅對 Ghidra 子程序設定 `JAVA_HOME`／PATH，沒有改系統全域 Java。既有分析儲存於 `data/research/ghidra/LRNative.gpr`；早期 300 秒逾時後，此次以 1,200 秒完成 `libgame.so` 分析並保存。
- 分析日誌 `reports/ghidra/ghidra_20261117T113614Z.log` 顯示 `Analysis succeeded`、`Save succeeded`；仍記錄少量 `GccExceptionAnalyzer` 反組譯錯誤與 `VarnodeContext` 位址空間錯誤，故不宣稱分析無錯。首版 Python xref 腳本因未啟動 PyGhidra 失敗，已換為 Ghidra Java 腳本 `scripts/ghidra/ExportResourceStringXrefs.java`。
- 可重跑的定向報告命令：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\run_ghidra.ps1 -Action xrefs`。此模式使用 `-noanalysis`，沿用已保存結果；最近成功報告 `reports/ghidra/libgame_resource_xrefs_20261117T122825Z.txt`，含 `REPORT_COMPLETE`。`run_ghidra.ps1` 已加入輸出檔及完成標記檢查；PowerShell 語法檢查通過。
- `game_item_equip.db`（241,664 bytes，SHA-256 `587a98d344f9e0d5e6fd0c677b17e193ec8c9b47862ba9e0e4f660c1cc308ab9`）、`game_item.db`（167,936 bytes）及 `eqip_spcl_opt.db`（8,192 bytes）均唯讀檢查；觸發 SQLite 查詢皆回 `file is not a database`。觀察到的 gzip／zlib magic 均未能通過完整串流驗證，未確認容器、長度／筆數／偏移、文字區或固定長度紀錄。這些結果不足以認定加密。
- 已確認資源索引片段：`FUN_0138d8e0` 建構 `res_base_hd.txt` 路徑；`FUN_01a43dec`／`FUN_01a41774` 解析 `resourceId`、`signature`、`resourcePath`、`resourceType` 等欄位；資源物件 setter 將前三者及類型寫入已觀察到的物件偏移。`game_item_equip` 引用目前只落在 descriptor 函式 `FUN_00f44fb8`，指標 `01e4aaa0` 指向該函式；`eqip_spcl_opt` 對應 `FUN_00f45288`、指標 `01e4afa0`。`0x1e`／`0x1a` 僅記錄為 descriptor 常數，未賦予星等等語意。
- `FUN_01a408fc` 處理資源路徑並呼叫 `CCFileUtils::sharedFileUtils()` 的 vtable `+0x80` 間接方法；尚未確認實際檔案讀取、轉換、資料紀錄解碼與欄位映射。目標鍵及候選鍵在三個二進位無明文命中；解析筆數為 **0**，沒有真實樣本或已確認的星等／效果欄位。
- **尚未建立解析器**：依格式證據門檻，現在將幾個數字當欄位或猜解碼方式都不可靠。下一步是追蹤 `FUN_01a408fc` 的 vtable `+0x80` 目標及 `game_item_equip` descriptor 的消費者，取得實際讀取／解碼規則；再驗證原始 ID 關聯，才實作及測試解析器。細節已記於 `reports/data-sources.md`。
