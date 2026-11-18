# Cloudflare 部署步驟

最後更新：2026-11-18

部署後會得到一個網址，同時提供：

- 試用版網站：輸入問句即時從知識圖譜作答，附出處與處理過程；含知識地圖
- 使用紀錄：訪客同意後才記錄問句、點選的出處與時間，存在 D1 資料庫 `seeing-coordinates-log`
- 知識圖譜資料表：v2 schema 的 2,048 個節點、4,088 條關係與出處、審核紀錄，存在 D1 資料庫 `seeing-coordinates-data`，可在 Cloudflare 後台用 SQL 查詢
- `/api/answer?q=問句`：給外部嵌入與外掛測試用的查詢 API；`/api/health`：檢查部署狀態

登入、建立資源都由帳號擁有者本人操作；資料夾裡沒有任何帳號資訊或密碼。指令以撰寫時的 Cloudflare 官方文件為準。

## 部署包內容

| 路徑 | 內容 |
|---|---|
| `public/` | 網站檔案（已建好）：index.html、engine.js（查詢程式）、graph.json（圖譜快照）、data.js、map.html、log.js、config.js |
| `src/` | Worker 與查詢程式原始碼（TypeScript） |
| `migrations/0001_usage_log.sql` | 使用紀錄的資料表 |
| `d1/v2_data.sql` | 知識圖譜資料表與資料（約 2.6 萬列、6 MB） |
| `wrangler.toml` | Worker 設定；兩個 `database_id` 由你貼上 |
| `test/` | 自動測試（`npm.cmd test`，15 項） |

## 開始前

- 解壓縮到 `08_NTU Challengers\試用版網站\cloudflare\`。這個資料夾已排除在 GitHub 之外，貼上的資料庫代碼不會公開
- 電腦已安裝 Node.js（v24）。PowerShell 會擋 `npm`、`npx` 的腳本，所以下面的指令一律寫 `npm.cmd`、`npx.cmd`；改用「命令提示字元」則可直接打 `npm`、`npx`
- 到 dash.cloudflare.com 註冊帳號，並開啟兩步驟驗證

## 步驟

在 `cloudflare` 資料夾按右鍵「在終端機中開啟」，依序執行。

**1. 安裝工具**（約 1 至 2 分鐘）

```
npm.cmd install
```

**2. 登入 Cloudflare**：會開瀏覽器，按 Allow。

```
npx.cmd wrangler login
npx.cmd wrangler whoami
```

`whoami` 顯示你的帳號即完成。

**3. 建立兩個資料庫**

```
npx.cmd wrangler d1 create seeing-coordinates-log
npx.cmd wrangler d1 create seeing-coordinates-data
```

- 若詢問是否自動寫入設定檔，選 No
- 每個指令會印出一段含 `database_id = "..."` 的文字，把兩個代碼分別貼進 `wrangler.toml` 的 `REPLACE_WITH_LOG_DATABASE_ID` 與 `REPLACE_WITH_DATA_DATABASE_ID`，存檔

**4. 建立使用紀錄的資料表**

```
npx.cmd wrangler d1 migrations apply seeing-coordinates-log --remote
```

詢問是否繼續時選 Yes。

**5. 匯入知識圖譜資料**（只需執行一次）

```
npx.cmd wrangler d1 execute seeing-coordinates-data --remote --file=d1\v2_data.sql
```

- 約 2.6 萬列，免費方案每日寫入上限 10 萬列，一次可以完成
- 若中途失敗，把錯誤訊息存下來；重跑前要先清空資料表，否則會出現「table already exists」

**6. 部署**

```
npx.cmd wrangler deploy
```

- 第一次部署會請你設定 workers.dev 子網域，自己取一個名字即可
- 完成後會印出網址：`https://seeing-coordinates.<子網域>.workers.dev`

**7. 設定限流用的密鑰**

```
npx.cmd wrangler secret put RATE_SALT
```

提示輸入時，自己打一串 20 字以上的隨機英數字。這串字不要存進任何檔案；忘記也沒關係，重設即可。

## 驗收

- 打開網址：先出現「使用紀錄說明」；同意或不同意都能使用。輸入「刺點這個概念後來怎麼發展？」應得到附出處的回答與「Agent 處理過程」；「知識地圖」分頁可開
- 打開 `網址/api/health`：應看到 `"ok":true` 與 `"data":{"entity":2048,"assertion":4088,...}`
- 打開 `網址/api/answer?q=多木浩二和Provoke有什麼關係`：應看到 JSON 回答
- 看最近的紀錄：

```
npx.cmd wrangler d1 execute seeing-coordinates-log --remote --command "SELECT ts, grp, type, question FROM events ORDER BY id DESC LIMIT 10"
```

- 在 Cloudflare 後台 Storage & Databases → D1 → seeing-coordinates-data → Console，可直接下 SQL，例如 `SELECT type, COUNT(*) FROM entity GROUP BY type`

## 試用時

- **分群連結**：網址後面加 `?g=代碼`，例如 `?g=ntu-photo`、`?g=lightbox`。紀錄的 `grp` 欄會帶這個代碼，方便分開統計
- **回饋表單**：Google 表單網址貼進 `public\config.js` 的 `formUrl`，再執行一次 `npx.cmd wrangler deploy`，頁首會出現「填寫回饋」按鈕
- **保存期限**：`public\config.js` 的 `retention` 是同意說明上寫的期限（目前 2027-01-31），到期前請匯出並刪除

匯出與刪除：

```
npx.cmd wrangler d1 execute seeing-coordinates-log --remote --json --command "SELECT * FROM events ORDER BY id" > events.json
npx.cmd wrangler d1 execute seeing-coordinates-log --remote --command "DELETE FROM events"
```

## 記錄什麼

| 欄位 | 內容 |
|---|---|
| ts | 伺服器時間 |
| session | 瀏覽器產生的隨機代碼，不對應到個人 |
| grp | 分群代碼（`?g=`） |
| type | consent、ask、open、click、map |
| question | 輸入的問句（最多 500 字） |
| qid、intent、sha、exact | 若問句與評估題庫相同則記題號；問題類型、回答指紋、是否與題庫相同 |
| target | 點選的出處網址 |

不記錄姓名、信箱、IP 位址。限流用的計數鍵是 IP、日期與密鑰的雜湊，隔日清除。每個來源每天最多 300 筆、每個瀏覽器代碼 200 筆。

## 費用與限制（免費方案）

| 項目 | 上限 | 本專案的用量 |
|---|---|---|
| Worker 請求 | 每日 10 萬次 | 只有 `/log`、`/api/*` 會計入；網站檔案由 static assets 提供 |
| Worker CPU | 每次請求 10 ms | 網站在瀏覽器裡作答，不受影響；`/api/answer` 冷啟動要載入 4 MB 快照，第一次呼叫可能逾時，需要穩定的 API 時再評估付費方案（每月 5 美元） |
| D1 讀取 | 每日 500 萬列 | `/api/health` 每次約 2.2 萬列（計算各表總數），約可重新整理 200 次；其他用途很少 |
| D1 寫入 | 每日 10 萬列 | 資料匯入約 2.6 萬列加索引（一次）；每則使用紀錄約 5 列（含計數與索引） |
| D1 容量 | 每個資料庫 500 MB | 約 6 MB |

## 之後更新資料

圖譜有新一輪資料時，在 repo 根目錄依序執行，再把 `api\public\` 與 `build\d1\v2_data.sql` 複製到這個資料夾，重新部署：

```
python graph_build.py
python build_viewer.py
python tools/build_cloudflare.py
python tools/export_d1.py
cd api
npm.cmd install
npx.cmd esbuild src/browser.ts --bundle --format=iife --target=es2020 --minify --legal-comments=none --outfile=public/engine.js
```

資料表要整份重建時，先在 D1 後台刪除再建立 `seeing-coordinates-data`，重做第 3 步（只建這一個）、第 5 步，並更新 `wrangler.toml` 的代碼。

## 本機測試

```
npm.cmd test
```

15 項：查詢程式 8 項（與 Python 版的 difflib、networkx 結果比對），Worker 7 項（路由、紀錄驗證與限流、`/api/answer`、`/api/health`）。
