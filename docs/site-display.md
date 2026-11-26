# 正式網站顯示資料

正式環境不讀取本機研究 SQLite。網站使用 `data/site-display/` 的壓縮顯示模型，以及 `public/site-assets/` 的已驗證 PNG；兩者可隨 Git 一起建置到 Vercel，不需要遊戲登入工作階段或 Supabase secret key。

## 從既有有效資料重建

先維持已設定 `LR_LOCAL_DATABASE_PATH` 的本機 development 預覽在 `127.0.0.1:3101`，再執行：

```powershell
python scripts/export_site_display.py
python scripts/validate_site_display.py
```

匯出不擷取遊戲、不讀 Cookie、不寫原始資料庫。它使用已驗證的角色／裝備模板、角色詳情、當前公會名單與駐防，以及各段位目前接受的排名／防禦關聯。失敗時不先清空既有網站資料；所有資料、關聯與圖片通過後才更新輸出，manifest 最後更新。

中途中斷可指定該次 `data/research/runtime.private/site-display-<時間>` 目錄作 `--resume`，重用已驗證的顯示片段。若原始有效資料已更新，應開啟新一輪匯出，不混用舊片段。

## 顯示與隱私邊界

- 角色基本資料、星等與已確認才能保留本機來源；參考技能與模板效果仍標記為使用者確認的參考資料，不改稱本機原生解析。
- 玩家防禦只保留顯示名稱、排名、時間、角色位置、培養數值、三部位裝備與已驗證數值。原始玩家／公會識別、角色／裝備實例 ID、原始階級與研究路徑不進入顯示模型；連結使用既有不透明別名。
- 玩家實際覺醒、詞條與強化不以模板補值。`null`、確認空位、未讀取、失敗及沒有配置各自保留。
- 公開公會資料不含個人未確認部署的儲存設定；未取得的公會／塔不改成空隊伍。
- 非排名個人歷史觀察仍僅限本機；正式版提供的是當前接受的排名防禦。沒有公開完整研究副本或本機資料庫。
- `manifest.json` 保留資料時間、來源類別、各檔 SHA-256、圖片 SHA-256 與涵蓋數。網站資料時間仍是原始採集／核對時間，匯出時間不是重新抓取時間。

## 建置與驗證

`next.config.ts` 明確納入 `data/site-display/*.json.gz` 的伺服器檔案追蹤，同時排除研究／原始／本機資料庫及私人標準化檔案。圖片走靜態路徑，不開放原本的本機圖片 API。

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
npm.cmd run start -- --hostname 127.0.0.1 --port 3101
# 僅在上述 production 預覽啟動後執行
python scripts/verify_site_display_ui.py
# 核對使用者指定的公開部署，不需要登入憑證
python scripts/verify_site_display_ui.py --origin https://lr-fcz.vercel.app
```

不要同時讓 development 與 production 使用同一個 port 或 distDir。可沿用 `LR_NEXT_DIST_DIR` 在本機分離建置產物；此變數不需要設定到 Vercel。

Vercel 使用 Next.js 預設 build/start；不需要將 `NODE_ENV` 改為 development，也不需要上傳 SQLite。Supabase 原有公開翻譯查詢仍使用原本兩個 public 環境變數；私有研究草稿不會因匯出而發布或覆蓋。

更新遊戲資料後，需重新匯出、驗證並推送版本，正式網站才會更新。雲端網站不會代替本機執行遊戲擷取；PVP 拒絕存取後的暫停與公會資料缺漏仍保留。
