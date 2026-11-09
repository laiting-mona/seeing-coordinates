# 可重現性驗證(2026-11-09)

由一個沒看過此專案的獨立 agent,在乾淨目錄 `git clone` 公開 repo,只讀 README,依「怎麼跑」順序逐條執行,不修改 clone 內任何檔案;全程結束後 `git status` 為空。本檔是它的報告,末節記錄當天依報告所做的修正。

| 項目 | 值 |
|---|---|
| Commit | `7c15e47` (2026-11-08) |
| 環境 | Ubuntu 24.04.5, Python 3.13.18(fresh venv), Node 22.23.4, Playwright 1.63.0 Chromium headless |
| 檢出大小 | 34 個追蹤檔案, 3.4 MB 工作樹 + 1.6 MB .git |
| 從 clone 到 viewer 可看 | 牆鐘 5 分 39 秒(含讀 README 與檢查輸出);純指令約 15 秒,瀏覽器排版約 17 秒 |

## 逐步執行

| 步驟 | 指令 | 秒數 | 結果 | 輸出重點 | 備註 |
|---|---|---|---|---|---|
| 1 | `git clone` | 2.3 | 成功 | 34 檔, HEAD `7c15e47` | 無 LFS, 無 submodule |
| 2 | `python3 -m venv` + `pip install -r requirements.txt` | 9.7 | 成功 | pydantic 2.14.3, networkx 3.7 | README 原未提 venv(已補) |
| 3 | `python graph_build.py` | 0.9 | 成功 | 1882 / 3672 / 3457 (15 + 3442) / 184 / 31 | 與「目前狀態」表一致 |
| 4 | `python graph_build.py --with-review` | 0.4 | 警告 | 入圖 3641 | 當時覆寫 graph.json,摘要行把 3641 稱為「正式」(已改) |
| 5 | `python build_viewer.py` | 0.2 | 警告 | 節點 1882 關係 3641 | 照 README 順序會做出含 184 條未查證邊的 viewer 而無提示(已改) |
| 6 | `python test_core.py` | 0.8 | 成功 | 35 項通過 | README 寫 25(已改) |
| 7 | `python agent.py` | 0.3 | 成功 | replay 4 輪,入圖 51 條,佇列 2 條 | 不需 API key |
| 8 | `pip install openpyxl && python tools/make_checklist.py` | 3.4 | 成功 | 184 條;.md 與 repo byte 相同 | 未裝 openpyxl 時依 README 預期失敗 |
| 9 | `python tools/audit_data.py` | 0.2 | 成功 | 硬性錯誤 0, 警告 164 | 與 docs/data-audit.md 相同 |
| 10 | `python review_queue.py` | 0.1 | 成功 | 184 條 | 與 repo 相同 |
| 11 | `python metrics.py` | 0.0 | 警告 | 無輸出 | 函式庫、無 main()(目錄樹說明已改) |
| 12 | `python experiments/weight_sensitivity.py` | 0.1 | 成功 | 7 組;CSV 與 repo byte 相同 | |
| 13 | `python query.py --test` | 7.3 | 警告 | 8 題皆「一致性 ✗」 | 新手無法判斷是否正常(已加總結行) |
| 14 | `python query.py "讀完《明室》下一本讀什麼"` | 0.3 | 成功 | recommend → 刺點 / 知面 / 此曾在 | 用法原只在 docstring(已補 README) |
| 15 | `python recommend.py barthes` | 0.3 | 成功 | 5 條推薦 | `recommend.py Barthes` 無輸出且 exit 0(已改) |
| 16 | Playwright 以 `file://` 開 viewer(沙盒不能連 CDN) | 2.8 | 失敗(環境) | 全黑, `vis is not defined` | 離線不能用且無提示(已加說明文字) |
| 17 | 同上,以本機 vis-network 9.1.9 代替 CDN | 17.9 | 成功 | 1882 節點 · 3457 關係, 未連結 2, console error 0 | 與稽核孤立節點數一致 |
| 18 | 資料檔列數與參照完整性(`python -I`) | 0.2 | 成功 | 見下表 | 關係兩端 id 全在 seed_entities;source_ref 全在 sources.csv |
| 19 | 敏感內容掃描(`git grep`) | 0.3 | 警告 | 無憑證、email、本機路徑、證號 | 見卡點 10、11 |

資料檔實際列數:`seed_entities.csv` 1882(person 792, work 704, institution 150, event 157, concept 79;label_pref en 1400 / zh 404 / zh_en 78);`raw_relations.jsonl` 3672(approved 3442, auto 15, review 184, rejected 31;kind 實用 10 種,`review` 類型目前無資料);`sources.csv` 1336(institution 1020, critic 240, primary 52, other 20, popular 4);`test_prompts.json` 8 題。

## 卡點與落差(12 項)

1. 「怎麼跑」的數字過期:2606 / 283 實為 3457 / 184。
2. 照 README 順序跑,viewer 會悄悄含進 184 條未查證邊:`--with-review` 寫到同一個 graph.json,之後 test_core 又把它重建回 3457,viewer 卻不變。
3. `--with-review` 摘要行自相矛盾:「正式入圖 3641(自動 15 + 查證確認 3442)」。
4. 測試數量寫 25,實為 35。
5. viewer 需要網路,README 說「瀏覽器開即可」;離線全黑且無提示。
6. `recommend.py` 對不存在的 id 無任何訊息;README 未說 id 從哪來,也未列 `recommend.py` / `query.py` 用法。
7. `query.py --test` 輸出 8/8「✗」,新手無法判斷是否正常;這是純程式比對的已知上限(意圖一致 41/48,實體解析失敗 11/48)。
8. 目錄樹三處與實際不符:`metrics.py` 不可執行;README 指向被 `.gitignore` 排除的 `原典查核清單.xlsx`;列出不在公開 repo 的 `tools/build_reflection.js`。
9. `.gitattributes` 註解說只有 sources.csv 是 CRLF,實際 seed_entities.csv 也是。
10. `docs/verification-sources.md` 一處檔名含作者本名。
11. `docs/decision-log.md` 是內部工作日誌,含補助報銷、給老師的問題、帳號與同步流程等,無憑證、不影響重現;是否公開由作者決定。
12. README 未提 venv;Ubuntu 24.04 系統 Python 直接 pip 會遇 PEP 668。

## README 數字 vs 實跑

節點 1882(792 / 704 / 150 / 157 / 79)、關係 3672、正式入圖 3457(15 + 3442)、待查證 184、已剔除 31、稽核硬性錯誤 0、關係欄位 11 個、requirements 兩個套件:全部符合。不符的只有「怎麼跑」註解的 2606 / 283、測試 25 項、xlsx 與 build_reflection.js 兩個不在 repo 的檔案、以及「瀏覽器開即可」未提網路。

## 結論

可以重現,而且很快:README 五條指令全部 exit 0,純執行約 15 秒,加瀏覽器 17 秒,陌生人約 6 分鐘內能看到會動的圖;核心數字與「目前狀態」表完全一致,三個會重寫檔案的工具產出與 repo byte 相同。唯一環境性阻擋是 viewer 必須連得上 cdnjs。其餘 11 項是文件落差或訊息問題,不會讓流程停下,但會讓新手懷疑自己跑錯。

## 當天依報告所做的修正(2026-11-09)

- 卡點 1、4、6、8、12:README 數字、venv、`recommend.py` / `query.py` 用法、`metrics.py` 說明、xlsx 與 build_reflection.js 的註記全部改正。
- 卡點 2、3:`graph_build.py --with-review` 改寫到 `build/graph_with_review.json`,摘要行改為「入圖 3641(正式 3457 + 待查證 184,供檢視)」;`build_viewer.py --with-review` 讀該檔、寫 `build/viewer_with_review.html`,頁首標明「含 N 條待查證(虛線),非定論」。正式 `graph.json` 與 `viewer.html` 不再被覆寫。
- 卡點 5:viewer 在 vis-network 載入失敗時於畫面說明需要網路(已用 Playwright 斷網驗證);README 註明。
- 卡點 7:`query.py --test` 末行加總結(意圖一致 41/48、實體解析失敗 11/48),並標明是診斷報表。
- 卡點 9:`.gitattributes` 註解改正。
- 卡點 10:檔名改為 `原典查核清單.xlsx`。
- 卡點 11:保留,待作者決定。
- 未重跑第二次完整驗證;上述修正各自以 `graph_build.py`、`build_viewer.py`(含 `--with-review`)、`test_core.py`(35 項)、`recommend.py Barthes`(exit 1)、`query.py --test`、斷網 Playwright 檢查過。
