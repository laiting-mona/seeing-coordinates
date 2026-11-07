# 觀看的座標：攝影論述知識圖譜 Agent

把攝影理論與攝影史裡「誰影響誰、哪本書談哪個概念、哪個流派有哪些成員」
這類關係,建成一張**每條連結都附出處與可信度**的知識圖譜,
並以此做個人化的閱讀推薦。

核心原則:**程式能做的用程式,只有判斷才交給 LLM**。
關係不是請模型「生成」出來的,而是經過結構化抽取 → 權威加權評分 →
(低信心的)人工/上網查證三道關卡,confidence 低於門檻就進佇列,不會被當成定論。

---

## 目前狀態(可重現)

從專案根目錄執行 `python graph_build.py`,會重跑出下列數字:

| 指標 | 數 | 說明 |
|---|---|---|
| 節點 | 1850 | 人物 790 · 著作 697 · 館所 145 · 事件 139 · 概念 79 |
| 關係(全) | 3540 | 每條皆附 claim / evidence / source / confidence |
| **正式入圖** | **3332** | 自動通過 15 + 上網查證確認 3317(第 13–15 輪逐頁回查與換源後:除 9 條原典自證外皆附可讀的機構、評論或原文網址,不再有只靠聚合站名單或 wiki 頁的關係;第 21 輪起 `source_ref` 一律指向 evidence 最新查證頁) |
| 待查證 | 177 | 隔離在佇列、不進正式圖:80 條是第 21–22 輪研究者只找到摘要式引句的新關係(多為新聞稿「提及」作品、沒有展品清單,第 22 輪已二查過 63 條、只救回 7 條);51 條待回原典補頁碼或找到頁面後才採用(其中 40 條已上網查兩次未果);36 條是本專案的詮釋層(找不到外部來源作此連結,依使用者決定保留於此);10 條是第 21 輪把 Monoskop wiki 頁、個人網站與書商列表剔出查證來源後查無替代頁的降級 |
| 已剔除 | 31 | 查證不成立或關係類型不成立(如 1977 Pictures 展未含辛蒂·雪曼;Krauss 1977 的〈Notes on the Index〉不可能修正 1980 的《明室》;Steichen 買下少年 Shore 的照片不等於影響) |

177 條待查證的明細(依影響力排序,每條註明仍待查證的原因)見 `docs/原典查核清單.xlsx`(附書名、待補頁碼欄、決定欄)。
查證來源網址見 `docs/verification-sources.md`。
涵蓋範圍:第 1–7 輪建立西方攝影史與理論的主幹(發明史、分離派到新地誌、後現代理論、主要獎項、選集與 MoMA/Tate 主題展);第 8 輪起轉向東亞:日本(木村伊兵衛賞、土門拳賞、写真新世紀、MoMA 1974《New Japanese Photography》、Provoke 巡迴展)、臺灣(《臺灣攝影家》系列叢書 35 冊、國家攝影文化中心與國美館四個展覽)、中國(《Between Past and Future》、三影堂)與韓國(《Chaotic Harmony》)的首批 hub;第 9 輪回頭補西方「葉節點」:108 位只靠一條收錄/得獎邊掛在圖上的人物,各以其機構頁補上代表作與師承/流派;第 10 輪續補其餘 198 人(西方人物葉節點 299→22);第 11 輪回到東方做縱深:日本 VIVO 與「10人之眼」、Camera Mainichi/山岸章二、Provoke 同人的攝影集、WORKSHOP 寫真學校,臺灣 V-10 視覺藝術群、《人間》雜誌與報導攝影、三劍客與中國攝影學會,中國四月影會與《新攝影》,韓國林應植的生活主義寫實與新線會、具本昌與裴炳雨;第 12 輪不擴充,改做資料流程稽核:新增 `tools/audit_data.py`,122 條無網址或人工給分的關係逐條回查機構頁,只靠維基或聚合站的關係改引機構頁,查不到的降為待查證;第 13 輪把 2,395 條已附網址的核可關係逐頁重讀一遍,頁面沒寫或只支持較窄說法的 111 條降為待查證,155 條把 claim 收窄到頁面原文;第 14 輪把讀不到或偏弱(課程頁、學生彙編、個人網站)的 16 個頁面換成原文、圖書館書目或機構頁,並找到 Campany〈Safety in Numbness〉原文,把 16 條重新掛回;第 15 輪把 48 條只靠聚合站名單的關係(土門拳賞得主、越戰攝影師、《Chaotic Harmony》)逐屆、逐人改引機構頁;第 16 輪依影響力排序處理全部 375 條待查證:248 條找到頁面核可(其中 27 條更正關係類型),23 條剔除,104 條仍待查證並註明原因(查無、純屬詮釋、審核否決、與既有關係重複);第 17 輪盲測第 14–15 輪的 138 條核可、二查其餘 70 條待查證,並把 4 個孤立節點接進圖;第 18–19 輪新增 `role` 與 `year` 欄位,把「屬於」拆成七種意思;第 20 輪替 70 條只靠書的正式關係補上頁面;第 21 輪再擴充 93 個節點、355 條關係,重點是智識關係(影響、討論、延伸、對照)、只有作者邊的作品的展出紀錄,以及非洲、南亞、東南亞、中東、東歐與拉美的首批節點,同時把 Monoskop(wiki)、個人網站與書商列表剔出查證來源,並讓每條關係的 `source_ref` 指向 evidence 裡最新的查證頁;第 22 輪再擴充 112 個節點、279 條關係(港韓中台日人物、沒有智識邊的人物、只有作者邊的作品、非洲南亞東南亞中東東歐拉美第二批、邊數少的概念節點),把 udn 部落格、PZI wiki、拍賣行圖錄換成大學書目資料庫、出版社與藝術家基金會頁,稽核加上弱主機警告。

---

## 目錄結構

```
.
├── schema.py          資料結構:Entity / Relation(每條關係強制附出處)、方向慣例
├── data_io.py         共用載入器 + 顯示名稱規則(display_label / short_label)
├── authority.py       權威加權評分:confidence = f(來源層級, 佐證數, 直接程度)
├── graph_build.py     建圖、算中心性 → build/graph.json  ★主入口
├── build_viewer.py    graph.json → 單頁互動圖 build/viewer.html
├── recommend.py       個人化推薦(走知識前緣,非熱門)
├── query.py           自然語言問句 → 圖查詢
├── agent.py           Agent v1(可直接 demo)
├── metrics.py         覆蓋率/可信度指標
├── extract.py         抽取管線(訂閱制、不亂猜)
├── captures.py        原始擷取紀錄
├── review_queue.py    把 status=review 的關係輸出成待審清單
├── test_core.py       最小回歸測試(純 assert,25 項)
│
├── data/              正典資料(唯一事實來源)
│   ├── seed_entities.csv      節點(id, type, name_zh, name_en, label_pref)
│   ├── sources.csv            書目/來源
│   ├── raw_relations.jsonl    ★所有關係 + status + 出處
│   ├── captures.jsonl         擷取紀錄
│   ├── review_notes.json      人工註記
│   └── test_prompts.json      測試題庫
│
├── tools/             一次性/輔助工具(非核心流程)
│   ├── make_checklist.py      產生 docs/原典查核清單.{md,xlsx}
│   ├── audit_data.py          資料流程稽核 → docs/data-audit.md(硬性錯誤須為 0,測試會檢查)
│   └── build_reflection.js    產生學習反思 docx(需 Node + docx;含個資,僅存本機、不進公開 repo)
│
├── prompts/extract.txt        抽取用 prompt
├── experiments/               權重敏感度實驗
├── docs/                      文件、查證來源、查核清單、投稿文件
└── build/                     產出(graph.json / viewer.html,可重建)
```

---

## 怎麼跑

```bash
pip install -r requirements.txt       # pydantic, networkx

python graph_build.py                 # 建正式圖(2606 條)→ build/graph.json
python graph_build.py --with-review   # 連 283 條待查證一起畫(供檢視,非定論)
python build_viewer.py                # 產生 build/viewer.html,瀏覽器開即可
python test_core.py                   # 跑 25 項回歸測試
python agent.py                       # Agent demo
```

輔助工具(需額外套件):

```bash
pip install openpyxl && python tools/make_checklist.py    # 更新查核清單
npm install docx && node tools/build_reflection.js        # 重建反思 docx
```

---

## 關係的生命週期(status)

| status | 意思 | 進正式圖? |
|---|---|---|
| `auto` | confidence ≥ 0.70,公式自動通過(第 1 輪依原典;第 20 輪後只剩 15 條,其餘已補上頁面改為 approved) | ✓ |
| `approved` | 人工/上網查證確認,evidence 附來源網址 | ✓ |
| `review` | confidence < 0.70,待回原典查核 | ✗(在佇列) |
| `rejected` | 查證不成立 | ✗(永遠排除) |

可信度公式:`confidence = min(1.0, 來源層級權重 + 0.10 × (佐證數−1)) × 直接程度`。

## 關係的欄位(data/raw_relations.jsonl)

| 欄位 | 內容 | 填法 |
|---|---|---|
| `source_id`、`target_id` | 兩端節點 id | 方向依慣例(見上) |
| `kind` | 關係類型(11 種) | `belongs_to`、`exhibit`、`influence`、`discusses`、`extend`、`contrast`、`critique`、`study`、`interpret`、`translate`、`review` |
| `role` | 只用於 `belongs_to`:這條「屬於」是什麼意思 | 七種:`author` 作者、`contributor` 收錄或刊登、`movement` 流派歸屬、`member` 成員或任職、`award` 得獎、`participant` 參展或參與、`part_of` 主辦、出版或隸屬。由 `data_io.infer_role` 依兩端節點類型自動判定,稽核會比對 |
| `year` | 這段關係成立的年份(出版、得獎、展出、加入) | 作者關係以作品標題所載年份為準;其餘只在 claim 恰好寫了一個年份、或事件節點 id 帶年份時填入;不猜 |
| `claim` | 一句話的主張 | 繁體中文,半形逗號,不加句號,不用破折號 |
| `evidence` | 原文引句、查證網址與歷次查核紀錄 | 以「｜」分段;最新一段在最後 |
| `source_ref`、`source_tier` | 來源 id 與其層級 | 層級必須與 `sources.csv` 一致 |
| `confidence`、`status` | 信心值與狀態 | 信心值由公式算出;`auto`/`approved` 入圖 |

`sources.csv` 的 `year` 欄對網頁來源記的是抓取年份(2026),對書籍與文章才是出版年。`kind` 欄的 `review`(評論)與關係狀態 `review`(待查證)是不同的東西。
`graph_build.py` 預設只納入 `auto` + `approved`;`rejected` 任何情況都不進圖。

---

## 命名與程式慣例

- **顯示名稱(`label_pref`)**:西方來源以英文為主、括號中譯(`en`,預設);華人圈耳熟能詳者以中文為主、括號英譯(`zh_en`,如 班雅明 (Walter Benjamin));華人圈人物與著作只用中文(`zh`),除非原題即為英文。規則集中在 `data_io.display_label`,所有輸出(圖、查詢、推薦、清單)共用。
- **資料方向慣例**(見 `schema.py` 註解):著作 →`belongs_to`→ 作者;人物 →`belongs_to`→ 機構/事件/概念/選集;展覽 →`exhibit`→ 人物/著作;譯本 →`translate`→ 原著。
- **查證來源**:維基百科、百度百科、namu wiki 不算查證來源。只靠它們的 approved/auto 邊、資料檔混用換行符、`auto` 信心值無法由公式重現,`tools/audit_data.py` 都列為硬性錯誤,`test_core.py` 會擋下。
- **產生檔一律 LF**:`docs/review-queue.md`、`docs/原典查核清單.md`、`build/*` 皆經 `data_io.write_text_lf` 寫出,Windows 與 Linux 產出 byte 相同,避免換行符造成的假差異。
- **程式結構**:一個 function 一件事,`main()` 只負責呼叫與組裝;共用載入器集中在 `data_io.py`;只用常見套件(pydantic、networkx、openpyxl)。一次性的擴充腳本不進 repo。
- **推薦的脈絡權重**:`belongs_to` 依目標類型加權(institution 0.5、選集/著作 0.7、展覽 0.8),避免 40 位得主的獎項或 44 篇的選集壓過真正的閱讀路徑;推薦同時走「入邊」:攝影家自身的著作、展出過他的展覽、討論他的文本都是候選(讀 Koudelka 會得到《Gypsies》,而不只是獎項)。

---

## 誠實聲明

這份圖目前最大的價值不是「大」,而是「每條都查得到出處、且把查過與沒查過分得很清楚」。
177 條待查證是一條**正在前進的查驗路徑**,不是被藏起來的缺口:
它們被明確標記、隔離於正式圖之外,任何一條要當成論文證據前,都得回原典補到頁碼級引用。
