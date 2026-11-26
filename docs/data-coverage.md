# 資料覆蓋與來源狀態

更新時間：2026-11-17（Asia/Taipei）

本文件只描述已在工作區檔案、來源 manifest 或本機執行結果中觀察到的內容。索引路徑不等於已取得資料；翻譯代碼不等於遊戲 ID；未觀察到的資料不等於遊戲已刪除。

## 四個模組

| 模組 | 已取得並驗證 | 缺少 | 尚未確認 |
|---|---|---|---|
| 角色 | APK 資源索引確認 `unit.db` 對應角色／單位資源；`advent_area` SQLite 有 19 列，其中 `advnt_unit_cd` 出現 `u2001e-lia`、`u2002e-alice`。 | 可讀角色主檔、角色名稱／翻譯、技能、進化或等級數值、可連回角色 ID 的圖片索引。索引所列 `lang_unit`（11,673,600 bytes）不在 APK 內，也未取得。 | `unit.db` 的記錄格式、欄位與解碼方式；`advent_area` 的單位代碼是否可連到角色主檔；圖集檔名和角色 ID 的關係。 |
| 裝備 | `game_item_equip.db` 已由資源索引、大小與 MD5 對上；但它不是 SQLite，尚未解出欄位。SQLite `lang_equip` 可唯讀解析，`zh-Hant` 1,346 列、完整性檢查 `ok`。目標 `eq_2202_amr_06_nm` 只在此翻譯表找到；同主幹 PNG 存在但仍是候選。 | 可讀裝備主檔列、正式 game ID／名稱關聯、星等／部位／效果／Spec+／強化數值；圖片語意映射及公開使用權。 | `game_item_equip.db` 的二進位格式與讀取／欄位映射；索引記載的版本化檔名不在本次 inventory。檔名中的 `06` 不能當星等證據。 |
| PvP | 尚無排行榜、段位、玩家防守隊伍或玩家配裝的真實記錄。 | 排行榜快照、玩家 ID、排名、已確認用途的防守隊伍、角色與三件裝備關聯、覺醒／才能資料。 | 合法且可重現的動態資料取得方式、樣本範圍、有效樣本與失敗筆數。未確認可透過官方或已授權來源取得。 |
| 公會 | `lang_guild` SQLite 有 1,895 列，繁中 379 列；它是介面文字翻譯，不是公會或成員資料。 | 公會列表／搜尋資料、成員名單、成員各自的防守隊伍與角色配裝、每位成員的取得狀態。 | 是否存在可合法讀取的公會成員名單；隊伍用途是 PvP 防守或公會戰防守；玩家與角色／裝備 ID 的來源映射。 |

### 跨模組素材

- APK `res_base_hd.txt` 為 JSON 資源索引，列有 `unit`、`game_item_equip`、`lang_equip`、`lang_guild` 等資源 ID、路徑、大小及簽章；索引本身不證明未隨 APK 封裝的內容已下載。
- 角色圖集 ZIP 與 plist、PNG 已在 APK 中觀察到，但尚未證實 frame 名稱與角色主檔 ID 的映射。
- 在 1,171 筆以 `_nm` 結尾的裝備名稱代碼中，有 884 筆在 `assets/res/tutorial_res/hd/gear_icon/` 找到同主幹的 `_icon.png`。這是可重跑的精確檔名比對，不等於裝備主檔已驗證映射。網站僅在開發模式、loopback localhost 讀取這些候選 PNG；未複製到 `public/`、資料庫或 production build。
- 遊戲引擎尚未確認；不得以一般原生函式庫名稱判定引擎。
- 來源細節、檔頭、信心等級及舊樣本見 [資料來源辨識報告](../reports/data-sources.md)。

## 優先資料鏈的實際結果

要求的鏈為「一個公會 → 成員名單 → 一位成員 → 已確認用途的防守隊伍 → 每位角色的武器／防具／飾品 → 角色與裝備名稱」。目前卡在第一段之前：沒有已確認的公會資料來源，也沒有公會記錄可選。

因此目前**沒有取得任何公會成員防守裝備**；也**沒有取得 PvP 防守或公會戰防守隊伍**。不得將 `lang_guild` 文字或 `advent_area` 單位代碼稱為公會成員／隊伍資料。

最新唯讀取得重試使用已確認的 ADB 路徑及序號，實際錯誤為：

```text
error: device 'emulator-5554' not found
```

失敗狀態保存在 `data/raw/lr_20261116T235245917571_b848fd4e/manifest.json`；該目錄沒有匯出 APK。前一個成功快照的兩個資源目錄也已實際回報 `No such file or directory`，原始訊息見 [取得報告](../reports/acquisition.md)。沒有重裝、清除資料、啟用 Root、讀取 shared preferences、cookies、登入憑證或帳號設定。

## 解析、差異與發布狀態

- 先前 10 筆輸出保留在 `data/normalized/lr_20261116T212608096_7b99bdd0/equip_localization.json`，沒有覆蓋。
- 全量輸出位於 `data/normalized/lr_20261116T212608096_7b99bdd0/runs/equip_pipeline_20261116/`；manifest 顯示來源語言列數與解析列數皆為 1,346，SQLite `integrityCheck=ok`。較早的全量 run `equip_20261116T153030490722Z_e602f5e9/` 亦保留。
- 與舊 10 筆輸出的欄位比較：1,336 筆是本次**新觀察到**的翻譯列、共同 10 筆沒有欄位變更、沒有把缺少項目判定成刪除。這不是 1,336 件新裝備。
- 原始檔案 SHA-256 比較使用同一個舊快照，13 個 manifest 檔案重新計算 hash 並皆未變動；尚未取得第二份完整遊戲快照，無法報告新版本的檔案差異。報告為 `reports/diffs/verified-sha-diff/`。
- Supabase 舊翻譯 migration 已套用，snapshot `lr_20261116T212608096_7b99bdd0` 已發布，1,346 列資料及匿名唯讀權限已實際驗證。新多模組 migration 尚未套用；網站目前仍只有裝備翻譯文字查詢，不是角色／裝備／PvP／公會完整資料站。
- 新增的多模組研究表預設私有且無匿名／一般登入角色讀取政策。泛用研究 bundle 匯入器可將已驗證來源先 stage 為 draft；若沒有對應的已驗證模組讀取模型，發布函式會拒絕發布。

## 欄位缺口

目前只有 `lang_equip` 翻譯列可作為實際樣本。對角色與裝備主檔、PvP 與公會動態資料，ID、名稱、星數、屬性、效果、裝備槽、段位、隊伍用途、玩家名單、覺醒／才能等欄位均未經資料來源核對，不能補成 `0`、空隊伍或模型推測值。三個裝備欄位應分別表示「已裝備」、「未裝備」及「未知」；整體讀取失敗則記錄為失敗狀態，而不是空陣容。

## 下一個可驗證步驟

1. 在雷電模擬器啟動並確認既有遊戲安裝後，使用本文「手動更新命令」中的 `acquire` 重試。不可用 `--wipe-data`、重裝或更改權限。
2. 如果成功取得新 APK，先執行 `inventory`，對新 manifest 內**實際存在且可讀**的資源建立來源清單；不要依索引路徑猜下載位置。
3. 要解開角色／裝備主檔，可用 JADX 追查已找到的 `unit.db`、`game_item_equip.db` 讀取位置及欄位映射；未有這個證據前不新增角色／裝備解析器。
4. 公會資料鏈需先有合法可取得的名單來源，再逐段驗證成員、隊伍用途、隊伍資料與三件裝備的 ID 對應。若只得到 PvP 防守資料，必須保留 `pvp_defense` 用途，不能標為公會戰。

## 手動更新命令

模擬器目前未連線，最新 ADB 錯誤已記錄在取得報告。裝置正常啟動後的完整命令、run ID 擷取方式、research bundle 格式及 Supabase 匯入／發布前提見 [docs/data-pipeline.md](data-pipeline.md)。該文件中的命令會將產生的 Snapshot ID 與輸出路徑存入 PowerShell 變數，不需輸入 PowerShell 無法解析的尖括號佔位符。

目前可直接重跑的真實解析與來源驗證：

```powershell
python scripts\data_pipeline.py parse --snapshot lr_20261116T212608096_7b99bdd0 --language zh-Hant
python scripts\data_pipeline.py validate `
  --input data\normalized\lr_20261116T212608096_7b99bdd0\runs\equip_pipeline_20261116\equip_localization.json
```

多模組研究 bundle 必須使用 `ranger-research-bundle` 格式，逐筆提供來源識別、raw record、來源檔案與 SHA-256；多模組 read model 尚未有來源解析器，因此研究資料會留在私有研究表，發布 gate 會拒絕尚無模組 read model 的版本。所有命令目前為手動執行，未設定排程。
