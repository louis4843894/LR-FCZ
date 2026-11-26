# 架構與開發順序

更新時間：2026-11-16（Asia/Taipei）

## 目前基線

- 工作區已有 Next.js App Router、TypeScript strict、Supabase 查詢層及 Python 解析／匯入腳本；本次沿用，不重建網站。
- 既有網站只呈現已發布的 `lang_equip` 翻譯文字列表與詳細頁。它不是角色或裝備圖鑑；尚未連到已發布 Supabase 資料時會顯示連線狀態，不使用假資料補空白。
- 舊 migration `20261116223000_ranger_localization_import.sql` 只涵蓋翻譯版本與翻譯列。資料庫尚未套用；該資料集不是裝備主檔。
- 新增 `20261117000000_ranger_multimodule_research.sql`，定義角色、裝備、能力、玩家、公會、成員、隊伍、PvP 排名與統計表，以及一個具 row-count／來源驗證 gate 的發布函式。**這份 migration 尚未執行，也未由 Supabase／PostgreSQL 實際驗證。**
- 新增多模組研究資料表預設啟用 RLS，撤銷 `public`、`anon`、`authenticated` 存取，只授權受控的 `service_role`。尚未加入任何匿名讀取 policy；待來源、欄位與公開範圍核准後，再以獨立 migration 建立 published-only 讀取介面。

沒有改動現有 Next.js 技術方向，也沒有把四模組範圍縮小。新 schema 採用來源識別、raw JSON 與 nullable `game_id` 承接尚未確認的來源差異；未證實欄位不被當成固定遊戲欄位。

## 資料流

```text
已確認的本機／授權來源
        │
        ├─ immutable raw snapshot + manifest + SHA-256
        │
        ├─ inventory（依檔頭辨識；安全解包）
        │
        ├─ 來源格式專屬 parser（character / equipment / dynamic 分開）
        │
        ├─ validate（覆蓋、原始識別、重複、來源檔雜湊、關聯）
        │
        ├─ diff（新觀察／欄位變更／未觀察到；不推定刪除）
        │
        ├─ import（private draft，idempotent，逐筆遠端核對）
        │
        ├─ publish（完整性成功後的單一資料庫交易）
        │
        └─ Next.js Server Components → published-only read API
```

取得、盤點、解析、驗證、差異、匯入與發布由手動命令執行；目前沒有排程。動態 PvP／公會來源和靜態圖鑑來源各自有不同 adapter，不因都使用 JSON 而共用錯誤欄位假設。

## 核心資料關係

- **研究快照**：`ranger_research_snapshots` 以 `(snapshot_id, module)` 唯一標示模組版本，記錄 `source_kind`、版本、觀察時間、manifest SHA-256、完整性、列數及狀態。相同原始快照可有不同模組資料，但每個模組分開驗證／發布。
- **原始研究列**：`ranger_research_records` 以 `(snapshot_id, module, source_record_identity)` 去重；逐列保留來源檔案、SHA-256、原始識別、raw record、可選 normalized record、驗證狀態及解析警告。這是私有研究／匯入 staging，不是公開圖鑑。
- **靜態圖鑑**：`ranger_characters`、`ranger_equipment`、`ranger_abilities` 以 snapshot + 原始識別保存原始列；只有來源確認後才填 `game_id`。資料表含來源檔案及雜湊。跨語言使用 `language`；game ID 未確認時不由 `dataCode` 代替。
- **玩家**：`ranger_players` 只存必要遊戲內公開識別及首次／最近觀察時間；不存登入憑證、cookies 或帳號秘密。
- **公會名單**：`ranger_guilds` 與 `ranger_guild_roster_snapshots`、`ranger_guild_memberships` 分開保存；名單的觀察時間／成功、失敗、不可取得不與成員防守隊伍共用狀態。
- **玩家隊伍**：`ranger_team_snapshots` 以玩家、用途、觀察時間及取用狀態識別；`membership_snapshot_id` 可指向不同時間取得的公會名單，明確保留跨時間關係。`ranger_team_members` 每列是某玩家某次隊伍中的角色與裝備，不把玩家裝備寫進角色圖鑑。
- **角色裝備槽**：角色欄位狀態與武器／防具／飾品槽狀態分開存；狀態值區分 `present`／`not_present`／`unknown` 與 `equipped`／`not_equipped`／`unknown`。ID 只能在對應的已知狀態下填入。
- **PvP 統計**：`ranger_pvp_rankings` 保留每筆來源排行；`ranger_usage_stats` 保存樣本範圍、分子、分母、計算時間及來源 snapshot ID。統計可重算，不把排名失敗視為未使用。
- **發布**：`ranger_publish_research_snapshot` 先核對完整性、source row 數、已驗證狀態、各 read-model 列數與隊伍／公會名單成功狀態，再在同一交易中 archive 舊版並發布新版本。函式錯誤時交易回滾，舊發布版不會被提前替換。多模組研究表目前全數私有，不因 snapshot status=published 自動對匿名公開。

## 匯入邊界

- `scripts/import_supabase.py` 是現有 `lang_equip` 翻譯 adapter；`--apply` 只 stage 與核對，不發布；需再執行 `publish`。
- `scripts/import_research_bundle.py` 定義多模組原始研究 bundle envelope，可驗證 snapshot manifest／來源檔案 SHA-256、source identity 唯一性、覆蓋筆數、敏感欄位名稱及逐列 digest；`--apply` 僅將研究列 stage 為 private draft。它不自行推斷 character/equipment/PvP/guild 欄位，也不會把 raw JSON 當公開 read model。
- 泛用 bundle 格式及 command 可以先 dry-run／匯入私有研究列；模組 read-model adapter 還必須根據實際來源將已核對欄位映射到上述模組表。發布函式會在沒有 read-model 列時拒絕發布，避免只因 raw JSON 已匯入就聲稱完整網站資料可用。
- 任何 importer 使用 `SUPABASE_SECRET_KEY` 只限受控 Python 行程；網站只用公開 publishable key；本次未輸出或儲存任何 Supabase 金鑰。
- 對玩家／公會資料套用公開 policy 前，必須另行審核公開識別、資料來源授權與欄位白名單。

## 開發順序與品質閘門

1. **取得來源證據**：先確認 ADB 裝置、取得新 immutable snapshot；保存每個檔案 hash 與取得錯誤。未成功即停在「來源不可取得」，不重裝、不清除、不猜 API。
2. **靜態圖鑑可讀性**：追查已找到的 `unit.db`／`game_item_equip.db` 讀取路徑與欄位映射；每一種真實格式建立獨立 parser。先通過 ID、名稱、技能／效果、圖片交叉表核對，再加入正式 read model。
3. **動態來源可行性**：逐段確認公會搜尋、名單、成員防守隊伍、PvP 排行及每筆裝備資料的合法來源與錯誤語意；不得把 PvP 防守命名成公會戰資料。
4. **本機模型與契約**：透過 `scripts/data_contracts.py` 測試名單與隊伍採集時間可不同、用途分離、失敗不等於空隊伍、三件裝備狀態、未知欄位及快照內 source identity 去重。
5. **模組 importer 與 DB**：來源 adapter 輸出明確 bundle；本機 validate／diff 通過後先匯入 draft，遠端逐筆核對與 read-model count gate 通過才能發布。新 migration 先在測試資料庫套用，再檢查匿名讀取與不可寫權限。
6. **網站**：先完成真實圖鑑列表／詳情與名稱／ID 搜尋，再加入來源確認的篩選；動態 PvP／公會分別以成功、失敗、不可取得狀態呈現。查詢與統計留在 server/database。
7. **手動端到端驗收**：取得一次真實來源、執行 acquire → inventory → parse → validate → diff → import → publish；確認失敗時仍可讀舊版。驗收完成前不啟用排程。

目前可實作／測試的內容是快照、翻譯全量解析、資料差異、研究 bundle envelope、模組 schema 與 domain contracts；角色主檔、裝備主檔、PvP 和公會動態 adapter 仍被實際來源缺口阻擋。
