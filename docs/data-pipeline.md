# 手動資料更新流程

所有命令由專案根目錄執行；每一步都是獨立的手動命令，沒有排程。資料來源必須先確認可合法讀取，不得猜測遊戲 API、資源 URL、欄位或解密方式。

## 命令

| 子命令 | 行為 | 可重跑／安全性 |
|---|---|---|
| `acquire` | 使用明確的 `--adb`、`--serial`、`--package` 檢查裝置與 package，建立新 snapshot，原樣匯出 base/split APK；只檢查兩個候選 App 目錄是否存在及可讀，不匯出私人 App 設定。 | Snapshot ID 唯一；不覆蓋既有目錄。裝置失敗時保留 `partial` manifest 與原始 ADB 錯誤。 |
| `inventory` | 對指定 raw snapshot 依檔頭／內容盤點格式；APK 當 ZIP 安全抽取，保留大小與檔案數限制。 | 每次輸出至獨立 `data/inventory/<snapshot>/runs/<run-id>/`；不覆寫舊盤點。 |
| `parse` | 呼叫目前已確認的 `lang_equip` SQLite 翻譯解析器；省略 `--limit` 會讀取該語言完整資料。 | 輸出至唯一 `data/normalized/<snapshot>/runs/<run-id>/`，附輸出雜湊及覆蓋 manifest。 |
| `validate` | `lang_equip` 逐筆比對唯讀 SQLite 原文及 manifest；`--research` 驗證多模組研究 bundle envelope／來源檔雜湊。 | 預設不連線、不寫入；不完整來源預設失敗或阻止發布。 |
| `diff` | 比較兩份 raw manifest 檔案 SHA-256，並可比較兩份 normalized records 的原始識別及欄位。 | 產生唯一 `reports/diffs/<run-id>/`；缺少列標成「新快照未見」，不冒稱官方刪除。 |
| `import` | 預設只 dry-run。`--apply` 對已部署、匹配的 migration 寫入 draft 並核對遠端資料。`--research` 使用私有研究 bundle adapter。 | 重用同 snapshot／原始識別，不新增重複列。匯入不發布。 |
| `publish` | 預設為本機 dry-run；僅 `--apply` 才驗證遠端版本並呼叫交易式發布函式。 | 完整性／讀取模型／列數檢查任一失敗時，保留舊發布版本。 |

執行 `python scripts\data_pipeline.py --help` 可列出命令；各子命令的旗標以 `--help` 為準。

## 目前可重現的真實資料命令

目前可讀取的完整資料只有 `lang_equip:zh-Hant` 翻譯表，不是裝備物品資料。

```powershell
$snapshot = 'lr_20261116T212608096_7b99bdd0'

python scripts\data_pipeline.py inventory --snapshot $snapshot
python scripts\data_pipeline.py parse --snapshot $snapshot --language zh-Hant
python scripts\data_pipeline.py validate `
  --input data\normalized\lr_20261116T212608096_7b99bdd0\runs\equip_pipeline_20261116\equip_localization.json
```

本次驗證結果：來源 1,346 列、解析 1,346 列、SQLite 完整性 `ok`；完整輸出及 run manifest 保留在新 run 目錄。舊 10 筆輸出未覆蓋。

同一舊快照的全量比較（只是確認檔案無變更，不代表已取得新版本）：

```powershell
python scripts\data_pipeline.py diff `
  --old-snapshot lr_20261116T212608096_7b99bdd0 `
  --new-snapshot lr_20261116T212608096_7b99bdd0 `
  --old-records data\normalized\lr_20261116T212608096_7b99bdd0\equip_localization.json `
  --new-records data\normalized\lr_20261116T212608096_7b99bdd0\runs\equip_pipeline_20261116\equip_localization.json `
  --run-id verified-sha-diff
```

產生 `reports/diffs/verified-sha-diff/diff.md`、`diff.json`：13 個 raw manifest 檔案重新計算 hash 並皆與 manifest 相符；相較舊 10 列樣本，新全量輸出多觀察到 1,336 列翻譯，10 個共同識別無欄位變更。不得把 1,336 解讀成新裝備。

## 新 snapshot 取得方式

每次取得都必須指定已確認 ADB 路徑、裝置序號及 package；成功會輸出新的 Snapshot ID。接著將 `$snapshot` 設為輸出的 ID，再執行後續命令：

```powershell
$acquireOutput = python scripts\data_pipeline.py acquire `
  --adb 'C:\LDPlayer\LDPlayer9\adb.exe' `
  --serial emulator-5554 `
  --package com.linecorp.LGRGS
$acquireOutput
if ($LASTEXITCODE -ne 0) { throw 'Acquire failed; inspect the partial manifest and error.' }
$snapshot = [regex]::Match(($acquireOutput -join "`n"), 'Snapshot:\s+([A-Za-z0-9_-]+)').Groups[1].Value
if (-not $snapshot) { throw 'Acquire output did not contain a Snapshot ID.' }

python scripts\data_pipeline.py inventory --snapshot $snapshot
python scripts\data_pipeline.py parse --snapshot $snapshot --language zh-Hant
```

`inventory` 與 `parse` 會印出唯一的 run ID 和完整輸出路徑；請將該 JSON 路徑傳給 `validate`、`diff`、`import` 及 `publish`。這次取得重試實際回報 `error: device 'emulator-5554' not found`，因此該 partial snapshot 不含 APK，不能拿來盤點或解析。

## 多模組 research bundle 格式

`scripts/import_research_bundle.py` 不推測角色／裝備／動態來源欄位。bundle 頂層須提供：

- `schemaVersion: 1`、`bundleKind: "ranger-research-bundle"`、`snapshotId`、`module`（`characters`／`equipment`／`abilities`／`pvp`／`guild`）、`sourceKind`（`static`／`dynamic`）、時區明確的 `capturedAt`。
- 原始 snapshot `sourceManifestSha256`、`coverage.scope`、`coverage.complete`、`sourceRecordCount`、`parsedRecordCount` 及 `recordCount`。
- 每列 `sourceRecordIdentity`、`sourceFile`、`sourceFileSha256`、`rawRecord`、可選 `normalizedRecord`、`validationStatus`、`parseWarnings`。

匯入器會要求來源檔位於對應的 `data/raw/<snapshot-id>/` 或 `data/extracted/<snapshot-id>/`，重新計算來源檔／manifest SHA-256，檢查 snapshot 內識別重複及敏感欄位名稱。敏感欄位名稱被拒絕但其值不會輸出。測試 fixture 僅放在 `tests/`。

目前研究 bundle `--apply` 只 stage 到私有 `ranger_research_records`，尚未將 raw records 映射為模組公開 read model；因此新 migration 的 publish gate 會拒絕沒有角色／裝備／PvP／公會 read-model 列的 snapshot。要發布，必須先有真實來源及經核對的模組 adapter。舊 `lang_equip` importer 與研究 bundle importer 是兩條不同流程。

## Supabase 執行前提

- 舊翻譯匯入使用 `supabase/migrations/20261116223000_ranger_localization_import.sql`；此 migration 已套用至目前連結的 Supabase 專案，並已由 CLI 記錄為 applied。研究模型使用 `supabase/migrations/20261117000000_ranger_multimodule_research.sql`，仍待測試資料庫驗證與套用。
- 目前已發布 snapshot `lr_20261116T212608096_7b99bdd0`，版本 `12.4.0`，`lang_equip:zh-Hant` 共 1,346 列；公開匿名讀取及不可讀取未發布／來源私有欄位已通過實際驗證。
- 新多模組 migration 尚未驗證前，不要直接執行會套用全部待處理 migration 的 `supabase db push`。
- `import` 與 `publish` 的 `--apply` 是不同操作；先完成 stage、遠端列核對及權限驗證，再單獨發布。PowerShell 只從受控環境讀取 `SUPABASE_SECRET_KEY`，不可列印或貼入聊天。
