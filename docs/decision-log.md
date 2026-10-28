# 決策日誌

記錄方法選擇與取捨,供結案報告與反思心得引用。

## 2026-10-23 技術選型(右尺寸原則:不殺雞用牛刀)

| 決策 | 選擇 | 理由 | 否決的牛刀 |
|---|---|---|---|
| 圖儲存 | JSON + NetworkX | 40-50 節點,dict 即可;NetworkX 只為算中心性,近零成本 | 向量資料庫、圖資料庫 |
| 檢索 | 圖鄰接走訪 | 前緣=一跳鄰居,幾行寫完 | embedding 語意檢索 |
| Agent | Python 迴圈 + Pydantic 驗證 | 規劃/工具/記憶/迴圈四件事都在,程式短、好讀 | LangGraph、AutoGPT 框架 |
| 抽取運算 | Claude 訂閱(prepare/ingest 兩步) | 不碰付費 API,符合補助只報訂閱費 | 按量 API |
| 推薦 | confidence × 權威 × 中心性 排序 | 可解釋、可審查 | 訓練推薦模型 |
| 介面 | 單頁 HTML 讀 graph.json | 靜態、好分享、零維運 | React + 後端 |

## 2026-10-23 補助工具決策

- 只報 Claude 訂閱。ChatGPT(生圖)與專案核心無關,不報。
- Notion AI(訪談逐字稿)CP 值低且需額外關聯說明,beta 前不報。
- API:經評估目前用不到,僅在產品對外推廣時才需要。

## confidence 分流(初版,2026-10-23)

- 共抽出 30 條關係;21 條 ≥0.70 自動入圖,9 條 <0.70 進人工佇列待審。
- 待審多為跨學派的詮釋性連結(如 Krauss↔Barthes、Batchen→Sontag),正是需要人工判斷之處。

## 2026-10-23（二次）架構與儲存決策

- **成本架構原則(標準做法):** 程式能做的(抓取、解析、去重、評分、指標、建圖、查詢)一律用程式;只有「讀一段文本、判斷關係並附證據」才丟給 LLM/agent。目的是省 token。
- **儲存與版控:** 原始擷取內容存 `data/captures.jsonl`(純文字、可 git diff、以內容雜湊做版本與去重);需要 SQL 時由 `captures.py` 載進記憶體 sqlite 查,不落地二進位檔。策展後的圖留在 git 版控的 JSONL/CSV,不進 SQL(該規模 SQL 是牛刀)。整個 repo 放 GitHub 做版控。
- **防汙染:** 原始擷取(captures)與策展圖(raw_relations)分開;實驗(experiments/)對圖唯讀,結果另存 results/。對話紀錄不進來源資料。
- **9 條待審關係:** 一律先不入圖,逐條查證後再決定。第 3(伊凡斯→蕭爾)、6(柏金→意識形態)預期查證後過關;第 1(巴特→班雅明,無直接引用)、4(克勞絲→巴特,時序早於《明室》)、8(弗雷德→蕭爾,中心性存疑)有真問題,須重構或續留。
- **popular 層:** 新增最低層,權重先試 0.30 / 0.15 / 0.10。
- **華人圈評論:** 僅收真正與這些西方理論對話者,列為次要層、低權重,主軸維持西方正典不偏。

## 2026-10-27 第 3 輪擴充：西方攝影與理論（298→433 節點）

- **擴充策略：** 以「叢集」而非散點新增——每個叢集錨定一個可查證的 hub 頁面（展覽官網、館藏頁、書目頁、哲學百科），一頁同時確認多條關係，查證成本 ≈ 每叢集 1–2 次抓取。
- **新增叢集：** 攝影哲學（Walton/Scruton/Cavell/Peirce/索引性）、19 世紀論爭（Baudelaire/Emerson vs Robinson/Rejlander）、Camera Work 與分離派、FiFo 1929 與 Dada 蒙太奇、美國紀實（Agee/Abbott/Atget 檔案/DeCarava）、歐洲紀實（Koudelka/Brandt/Killip）、Pictures 1977 與圖景世代（Met 2009）、概念攝影（Wall〈Marks of Indifference〉、Sultan & Mandel《Evidence》）、凝視理論（Mulvey/Lacan）、《Thinking Photography》、Sekula 檔案論、Rosler、Bourdieu/Kracauer/Flusser、Fried、《明室》討論對象、後攝影（Steyerl/Ritchin/Didi-Huberman/Rancière）。
- **數字：** 關係 294→539；正式入圖 251→432（自動 99 + 查證確認 333）；待查證 41→105；剔除維持 2。
- **著作成為 hub：** 中心性 Top5 首次出現著作節點（Fried《Why Photography Matters》、巴特《明室》），印證「一本書應長出多條線」的設計。
- **重構案例：** Sherman 不在 1977 Pictures 展（rejected 維持），但確屬圖景世代（Met 2009 圖錄）→ 新增概念節點 `pictures_generation` 並 approved，將事件歸屬與世代歸屬分開記錄。
- **誠實邊界：** FiFo 其餘參展者、Weegee/Brandt/Killip 歸屬、《明室》其餘攝影家等 65 條本輪未抓到直接來源，一律留 review；一次性擴充腳本放 scratchpad，不進 repo。

## 2026-10-27（二次）第 4 輪擴充：西方（433→535 節點）

- **新增叢集：** 19 世紀法國（Mission Héliographique）與美國內戰攝影、超現實主義攝影（L'Amour fou）、October 1978 攝影專號與後現代理論、Elkins《Photography Theory》研討會、Kamoinge 非裔攝影集體、Archive Fever 檔案轉向、再攝影調查計畫、Campany「遲到的攝影」、Aperture 創刊、LIFE、Brodovitch 與時尚攝影、Mapplethorpe《Perfect Moment》文化戰爭、道格拉斯與肖像攝影、Ghirri、Mirrors and Windows 參展名單、Ray-Jones 與 Parr。
- **新概念節點：** 超現實主義攝影、遲到的攝影、時尚攝影、肖像攝影、文化戰爭與審查、再攝影。
- **數字：** 關係 539→754；正式入圖 432→615（自動 99 + 查證確認 516）；待查證 105→137；剔除維持 2。
- **方法觀察：** 展覽與機構頁面（MoMA 新聞稿、Whitney、ICP、Corcoran 圖錄）是最高效的 hub，一頁可確認 10–20 條成員/參展關係；理論文獻則多靠書目頁與論文摘要，一頁僅確認 2–4 條。
- **誠實邊界：** 「X 屬於時尚攝影/肖像攝影」這類歸類多為教科書常識但本輪未抓到直接頁面，一律留 review，不借 hub 之名夾帶。

## 2026-10-27（三次）自我審核 + 程式重構 + 命名規則

- **審核方法：** 把第 1–4 輪全部 approved 關係逐條對回 evidence 內的 hub 頁面，問「這頁有沒有**明說**這條關係」。結果：結構面乾淨（無孤立方向錯誤的大宗），但 6 條屬「頁面提到人名、關係是我推的」，一律降回 review 並在 evidence 標記；2 條著作↔作者方向反了（導致「只給書名」的推薦橋接失效）、LIFE→Luce 方向反了、xu_qiling 對《靈光消逝的年代》應為 translate 而非 belongs_to，均修正。
- **透明數字：** approved 中有 100 條來自第 1–2 輪「依標準攝影史參考升級」、evidence 沒有單一網址，保留 approved 但在 README 與 verification-sources B 節明寫，不混入「上網查證通過」。
- **來源完整性：** 16 個早期 source_ref（asx、cphmag、interpretation、*_knowledge、wiki:*）原本不在 sources.csv，補為 legacy 列（tier other/popular），讓每條關係的 source_ref 都查得到。
- **程式重構原則：** 一個 function 一件事；`main()` 只呼叫與組裝；共用載入器集中在新檔 `data_io.py`；函式與變數名稱說明用途；只用常見套件。所有模組加英文 docstring 與「Last edited」標頭。pyflakes 乾淨、20 項測試通過、query 解析快約 4 倍。
- **命名規則（使用者指定）：** 西方人物／著作／概念以英文為主、括號中譯；華人圈耳熟能詳者（班雅明、桑塔格、巴特、布列松等）中文為主、括號英譯；華人圈的只用中文，除非原題是英文。實作為 `seed_entities.csv` 新欄 `label_pref`（en / zh_en / zh）+ `data_io.display_label`，並做拉丁字核心重疊去重（避免「Kodachrome (1978) (Kodachrome)」）。
- **查詢修正：** 解析器曾把 Bourdieu 誤配到 Bourdin、Sontag 誤配到 Tagg、「攝影理論」誤配到「遲到的攝影」。改為先精確子字串（含 ≥4 字元且不歧義的姓氏索引、子字串去重），再 difflib 模糊比對（cutoff 0.8、視窗 4–14）。口語問句的穩定性掃描仍多為「不一致」，這是規則式解析的真實限制，誠實記錄而非調參掩蓋。

## 2026-10-28 第 5 輪擴充：西方（535→618 節點）+ 推薦脈絡權重

- **新增叢集：** Hasselblad Award 歷屆得主、Deutsche Börse Prize 歷屆得主、紐約學派（Livingston）、FSA/OWI 全員（LoC）、Group f/64 十一位原始成員（Britannica）、Kemp & Amelunxen《Theorie der Fotografie I–IV》作者名單、越戰攝影（art2art 巡迴展、普立茲、World Press Photo）。
- **數字：** 關係 754→920；正式入圖 609→768（自動 99 + 查證確認 669）；待查證 143→150；剔除維持 2。
- **查核更正自己：** 重抓 Hasselblad 官網後，發現我記憶中的 2024/2025 得主順序有誤（實為 2024 Pollard、2025 Ristelhueber、2026 Muholi），以官網為準。Deutsche Börse 2026 因頁面自相矛盾不收；Livingston 書的出版年、Ut 的普立茲年份頁面未載，不借 hub 之名夾帶。
- **判斷：獎項是脈絡不是路徑。** 得獎名單 hub 加入後，攝影家的第一推薦變成「Hasselblad Award」:關係準確但對讀者沒幫助（正是給老師信中提出的問題）。處理：資料不動（關係是對的），在 `recommend.py` 對「屬於 institution」的邊乘 `CONTEXT_EDGE_WEIGHT = 0.5`，並新增測試「institution 名單不會成為攝影家第一推薦」。這是「準確 ≠ 有幫助」的第一個可操作的例子，可作為日後排序指標的起點。
- **誠實邊界：** 新增 83 個節點中約 50 個目前只有一條「得獎」邊（葉節點）；它們的價值在於為日後補充作品與影響關係提供已查證的錨點，不是現在就能推薦。
- **viewer v11（使用者回饋）：** 固定黑底白字、拿掉面板提示文字；UX：搜尋框（鍵盤可選）、類型篩選 chips、點節點只亮鄰居並放大標籤、視角自動框住鄰居、查證來源可點、佈局穩定後凍結物理；61 個尚無入圖關係的節點預設隱藏（chip「未連結」可開）。查核清單把「關係(來源→目標)」拆成「來源」「目標」兩欄。
