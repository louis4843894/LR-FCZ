# Ranger Atlas

LINE Rangers 非官方資料研究站，沿用 Next.js App Router、TypeScript strict 與 Supabase 架構。

目前包含 **953 筆已驗證裝備模板、2,405 筆角色基本資料**，以及角色詳細資訊、PVP 防禦與公會戰十塔的本機顯示流程。裝備模板參考範圍與玩家裝備實際數值分開；沒有、未知、尚未取得也分開表示。已載入裝備容器遍歷完成，但全遊戲完整性未知，原始 `.db` 解密仍是獨立研究工作。

此倉庫保存網站、解析工具、資料庫結構、測試與基本模板。玩家配置、研究副本、SQLite、環境金鑰及執行時資料保留在本機，不會隨 Git 提交。另存 Supabase 的研究成果仍為私有草稿；推送程式碼不等於部署網站。

最新可續接狀態、資料來源與具體阻礙只維護於 [current-state](docs/current-state.md)。其他 progress 報告是歷史記錄，勿當作目前資料能力。

## 開發方式

建議使用已驗證的 Node.js 24（本機 SQLite 讀取使用 `node:sqlite`）。先於 `.env.local` 設定網站用的公開連線資訊：

```text
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
```

網站不使用 Supabase secret key。安裝依賴及啟動：

```powershell
npm.cmd ci
npm.cmd run dev
```

開啟 `http://localhost:3000`。驗證與正式建置：

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run build
```

## Vercel 環境變數

在專案 Settings → Environment Variables 新增以下兩項，環境選 Production、Preview：

```text
NEXT_PUBLIC_SUPABASE_URL=https://<project-id>.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<publishable-key>
```

值使用自己的 Supabase 專案 URL 與 Publishable key。`SUPABASE_URL` 僅是同專案網址的可選 server override；`SUPABASE_SECRET_KEY`、`LR_LOCAL_DATABASE_PATH`、`LR_NEXT_DIST_DIR` 不需填入 Vercel，`NODE_ENV` 由平台管理。環境變數變更只影響後續部署，見 [Vercel 官方說明](https://vercel.com/docs/environment-variables/managing-environment-variables)。

**目前正式環境尚未接齊資料**：角色、PVP、公會、裝備效果研究對照及私有圖片讀取仍有 development／loopback 限制；Supabase 研究快照目前為私有草稿。填入上述兩項只設定既有公開查詢連線，不會自動讓本機資料在 Vercel 顯示。正式發布需要另外完成可公開資料的白名單讀取與素材串接，不能靠把 `NODE_ENV` 設成 development 取代。

## 目前功能

- `/gear`：953 筆裝備搜尋、篩選、詳細資料與效果參考；制服已確認為 6 星 ARMOR。
- `/characters`：2,405 筆角色基本資料、搜尋與篩選；已對照的技能、技能前搖、角色能力、覺醒候選與才能依證據顯示。
- `/guild`：前 100 名公會與已取得名單；十塔防禦區分完整、部分與未取得，塔號顯示 1～10。
- PVP／公會共用可收合的隊伍檢視器：角色位置、實際等級、雷納德點數、覺醒／才能與各部位裝備；中文實際詞條與模板範圍分開。
- `/translations`、`/data-status`：已發布翻譯及真實資料覆蓋狀態。缺少私有副本時顯示缺口，不提供示範排名、假隊伍或假使用率。
- 本機角色圖片已有已驗證的模板映射；圖片留在私有素材目錄，缺圖使用替代顯示，不熱連結別站。

本機私有資料目前含一個完整公會防禦與一個部分對手防禦；**前 100 公會的批次防禦取得尚未完成**。公開玩家回應中的 `guildwar` 已確認是進攻編隊，不能匯入為十塔防禦。細節以 current-state 為準，這些玩家資料不包含在倉庫內。

## 資料範圍與限制

本機裝備副本已解析 953 筆，原始 5 筆與後續 256 筆成功基準均保留。`goodGearAttr` 原始值已保存，但其遊戲內使用關聯尚未全部證實，不能單憑 0 推論沒有任何效果。

外部效果對照來自指定的公開 Rangerbook 資料與顯示 JS，與本機數值來源分開。953 個裝備 ID／星等／類型吻合；外站未提供明確遊戲資源版本，發布授權未確認，因此效果對照僅在 development 本機研究預覽啟用，不會自動納入 production。效果、條件、Skill+、Spec+ 只顯示來源實際存在的資料。

研究物件、執行時依賴及工具都位於被忽略的 `data/research/runtime.private/`，網站只讀白名單標準化資料。舊的虛構 UI JSON 已移至 `tests/fixtures/legacy-ui-prototype/`，不再放在可公開請求的 `public/`。

翻譯來源中若包含字面 `\\n`，資料庫與 normalized 原文會保留；伺服器讀取層只把未被另一個反斜線跳脫的 `\\n` 轉成顯示換行，不作遞迴或通用反斜線解碼。

網站只查詢 Supabase 已發布版本。目前已發布 snapshot `lr_20261116T212608096_7b99bdd0`，含 1,346 筆 `lang_equip:zh-Hant` 真實翻譯記錄；匿名讀取、私有來源欄位保護及禁止公開寫入均已實際驗證。這些是翻譯文字，不是角色／裝備物品圖鑑。多模組研究 migration 尚未套用；不要直接執行會同時推送所有待處理 migration 的 `supabase db push`，直到該 migration 完成驗證。若資料庫沒有已發布版本，網站會顯示明確狀態，不會用示範資料補位。

手動資料更新命令與 research bundle 格式見 [docs/data-pipeline.md](docs/data-pipeline.md)；目前未設定排程。

## 本機裝備流程

```powershell
# 新快照，不覆寫成功基準；max-nodes 計算觀察節點，最大 2048。
python scripts/runtime/read_equipment_objects.py --max-nodes 2048 --max-seconds 900
$capture = (Get-Content -Raw data/research/runtime.private/latest-capture.json | ConvertFrom-Json).directory
python scripts/parse_runtime_equipment.py --capture $capture --localization data/extracted/lr_20261116T212608096_7b99bdd0/assets/res/tutorial_res/db/lang_equip/lang_equip.ndb --output data/research/equipment-runtime-latest.json
python scripts/export_equipment_website.py --source data/research/equipment-runtime-latest.json
# 需已保存的指定外站公開研究副本；只產生本機對照白名單。
python scripts/build_equipment_reference_preview.py
$env:LR_NEXT_DIST_DIR = '.next-local-dev'
npm.cmd run dev -- --hostname 127.0.0.1 --port 3101
```

OneDrive 的既有 `.next` 是 reparse placeholder；`next.config.ts` 支援 `LR_NEXT_DIST_DIR` 選用專用本機輸出目錄。Production 驗證使用 `.next-local-validation`，不部署。
