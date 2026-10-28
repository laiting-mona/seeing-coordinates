const {
  Document, Packer, Paragraph, TextRun, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  TableLayoutType, VerticalAlign
} = require("docx");
const fs = require("fs");
const path = require("path");

// 輸出到專案 docs/(腳本在 tools/,上一層為專案根)
const OUT_DIR = path.join(__dirname, "..", "docs");
const OUT_FILE = path.join(OUT_DIR, "NTU_Challengers_學習反思心得一_賴亭穎_投稿版.docx");

// 字型:Windows 版 Word 內建繁中字型;無此字型的環境會自動替換。
const FONT = "Microsoft JhengHei";
const CW = 9746, HDR = "F0F0F0", RED = "C00000";

// @@...@@ 內標紅(重點詞)
function runs(t, base = 22) {
  const parts = t.split("@@");
  const out = [];
  for (let i = 0; i < parts.length; i++) {
    if (parts[i] === "") continue;
    const red = (i % 2 === 1);
    out.push(new TextRun({ text: parts[i], size: base, color: red ? RED : undefined, bold: red }));
  }
  return out;
}

const docLine=t=>new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:60},children:[new TextRun({text:t,size:18,color:"555555"})]});
const title=t=>new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:160},children:[new TextRun({text:t,bold:true,size:30})]});
const q=t=>new Paragraph({spacing:{before:230,after:100},border:{bottom:{style:BorderStyle.SINGLE,size:6,color:"555555",space:3}},children:[new TextRun({text:t,bold:true,size:23})]});
const sub=t=>new Paragraph({spacing:{before:140,after:60},children:[new TextRun({text:t,bold:true,size:22})]});
const p=t=>new Paragraph({alignment:AlignmentType.JUSTIFIED,spacing:{after:120,line:320,lineRule:"auto"},children:runs(t)});
const bullet=t=>new Paragraph({bullet:{level:0},alignment:AlignmentType.JUSTIFIED,spacing:{after:50,line:300,lineRule:"auto"},indent:{left:360,hanging:180},children:runs(t)});

function cell(t,w,o={}){const {bold=false,fill=null,align=AlignmentType.LEFT,size=21}=o;
  return new TableCell({width:{size:w,type:WidthType.DXA},verticalAlign:VerticalAlign.CENTER,
    shading:fill?{type:ShadingType.CLEAR,color:"auto",fill}:undefined,margins:{top:40,bottom:40,left:90,right:90},
    children:[new Paragraph({alignment:align,spacing:{after:0,line:264,lineRule:"auto"},children:[new TextRun({text:t,bold,size})]})]});}
const thin={top:{style:BorderStyle.SINGLE,size:4,color:"999999"},bottom:{style:BorderStyle.SINGLE,size:4,color:"999999"},left:{style:BorderStyle.SINGLE,size:4,color:"999999"},right:{style:BorderStyle.SINGLE,size:4,color:"999999"},insideHorizontal:{style:BorderStyle.SINGLE,size:4,color:"999999"},insideVertical:{style:BorderStyle.SINGLE,size:4,color:"999999"}};
const table=(w,rows)=>new Table({width:{size:CW,type:WidthType.DXA},columnWidths:w,layout:TableLayoutType.FIXED,borders:thin,rows});
const spc=()=>new Paragraph({spacing:{after:40},children:[new TextRun({text:"",size:10})]});

const counted=[];
const B=t=>{counted.push(t.replace(/@@/g,""));return p(t);};
const L=t=>{counted.push(t.replace(/@@/g,""));return bullet(t);};

const children=[];
children.push(docLine("115-1 NTU Challengers｜#PBL #AI Agent"));
children.push(title("學習反思心得（一）"));
children.push(table([2600,7146],[new TableRow({children:[cell("專案主題名稱",2600,{bold:true,fill:HDR}),cell("觀看的座標：攝影論述譜系地圖與個人化閱讀路徑 AI Agent",7146)]})]));
children.push(spc());
children.push(table([1700,1700,2200,4146],[
  new TableRow({children:[cell("學生姓名",1700,{bold:true,fill:HDR}),cell("學號",1700,{bold:true,fill:HDR}),cell("系級",2200,{bold:true,fill:HDR}),cell("指導教師簽名",4146,{bold:true,fill:HDR})]}),
  new TableRow({children:[cell("賴亭穎",1700),cell("B12303147",1700),cell("經濟學系四年級",2200),cell("謝吉隆　　　　（簽名）",4146)]}),
]));

// ───────── Q1 ─────────
children.push(q("1. 請對照計畫書中所規劃之時程，簡述專案目前的實際執行進度。"));
children.push(B("計畫書將前兩週規劃為建立骨架、整理種子語料與完成抽取管線，建圖、推薦、監控、介面與測試則排於後段。實際執行下來，骨架已經完成，原訂後期才進行的數個部分亦提前實作。目前系統由九個核心模組構成，並在其上完成 AI Agent 雛型、自然語言查詢層與互動式譜系圖，全案以 Git 版本控管，並附自動回歸測試與靜態檢查。九個模組分別為："));
children.push(L("資料結構（Pydantic）：實體分為人物、著作、概念、事件、館所五類；關係分為影響、批判、延伸、屬於、對照、討論六種，欄位格式不符的關係無法進入。"));
children.push(L("抽取管線：走訂閱制、不呼叫付費 API。"));
children.push(L("建圖（NetworkX）：以 MultiDiGraph 容納同一對節點之間的多重關係。"));
children.push(L("權威加權評分：依來源分級、佐證數與直接程度計算可信度。"));
children.push(L("個人化推薦：沿知識前緣給出下一步閱讀建議。"));
children.push(L("監控:量測重複率與涵蓋率。"));
children.push(L("原始擷取儲存：保留可溯源的證據。"));
children.push(L("人工判斷佇列：集中低信心關係待查證。"));
children.push(L("回歸測試：固定核心行為，防止修改時破壞既有功能。"));
children.push(B("這一階段的主要進展是知識圖的規模擴充。圖目前有 @@298 個節點、294 條關係@@，涵蓋範圍已從原本的西方理論主線，向外延展為一張較完整的攝影論述地圖："));
children.push(L("理論主線：班雅明、克拉考爾、巴贊、桑塔格、巴特、蕭爾、克勞絲、傅拉瑟、阿祖萊等。"));
children.push(L("西方攝影脈絡：畫意攝影與攝影分離派、直接攝影與 f/64、包浩斯新視覺與新客觀、FSA 社會紀實、馬格南與戰地攝影、New Documents 與社會地景、New Topographics 與新彩色、杜塞道夫貝歇學派、圖景世代（Pictures Generation）與舞台式攝影。"));
children.push(L("東亞脈絡：日本的 Provoke 同人（中平卓馬、森山大道、多木浩二）與 VIVO、土門拳與木村伊兵衛；台灣的郎靜山集錦攝影、張才／鄧南光／李鳴鵰「三劍客」、張照堂、阮義忠；以及香港何藩、韓國具本昌等。"));
children.push(B("以中心性（degree centrality）觀察，連結最密的節點為「@@紀實攝影@@」，其後依序為桑塔格、巴特、蕭爾、班雅明。紀實攝影成為樞紐，反映出眾多攝影家經由流派與議題匯入此一概念；原本的理論主線則仍居核心，顯示擴充後的結構並未偏離原本的重心。"));
children.push(B("然而規模擴大，也使需要查證的關係同步增加。這 294 條關係中，有 @@251 條@@已進入正式圖（其中 99 條由評分自動通過、152 條經逐條上網查核確認）；另有 @@41 條@@因尚未確認、被保留在「待判斷佇列」等待查證；另有 2 條經查證判定不成立，已標記為 rejected 並排除於正式圖之外。待審比例偏高並非資料品質下降，而是擴充時加入了大量詮釋性與風格性的傳承關係，這類關係本就應由人工確認。因此此階段的「完成」，指的是架構完整，且已將未經確認的關係明確標記、隔離於正式圖之外。相較計畫書，骨架進度超前；未來需進行 beta 測試，而待判斷清單的原典查證已著手進行（詳見第 3、4 題）。"));
children.push(B("除了規模，這一階段也擴充了關係的「種類」。原本關係僅有影響、批判、延伸、屬於、對照、討論六種，不足以表達一本著作實際會長出的多種連結，因此新增五種關係型別，使同一本書能同時掛上作者、概念、譯本、研究、評論、詮釋與展覽等多條線："));
children.push(L("譯本（translate）：記錄原著與其譯本、譯者。"));
children.push(L("研究（study）：記錄專門探討某作品的學術研究。"));
children.push(L("評論（review）：記錄針對某作品的評論或書評。"));
children.push(L("詮釋（interpret）：記錄對某作品或概念的再詮釋。"));
children.push(L("展覽（exhibit）：記錄展覽所展出的攝影家或作品。"));
children.push(B("以巴特《明室》為例，它在圖中目前已長出 @@十條線@@：向外連到作者巴特，以及它提出的刺點、知面、此曾在三個概念；向內則有三條譯本（許綺玲中譯、Richard Howard 英譯，以及中譯本版本）、一篇研究（Batchen 主編的 Photography Degree Zero 論文集）、一條評論（Batchen《Burning with Desire》對其起源預設的質疑）與一條詮釋（弗雷德對刺點的再讀）。一本書因此不再只是一個端點，而是一個能展開的小網絡。"));

children.push(B("這次擴充本身，也是一次對架構的壓力測試。節點自 75 增至 298、關係自 64 增至 294，但主線理論節點的中心性排序幾乎未變，分流機制照常運作、未出現崩潰或大量格式錯誤。這顯示先前把判斷與資料分離、把驗證寫成固定規則的設計，確實能在規模放大近四倍時維持穩定，也讓我對後續把節點再推向 500 以上較有把握。"));

// ───────── Q2 ─────────
children.push(q("2. 專案執行至今，已接觸哪些重要利害關係人或目標受眾？獲得哪些重要回饋？是否對「專案目標」或「問題解決策略」產生影響？"));
children.push(B("最早且最具份量的回饋，是計畫審查委員的評語，共兩點："));
children.push(L("知識圖目前以人工核驗為主，應更清楚說明哪些步驟由 Agent 自主、哪些仍須人工。"));
children.push(L("來源與關係規模偏小，推薦可能重複，建議於測試時觀察後再決定擴充方式。"));
children.push(B("這兩點直接改變了做法。針對第一點，我將跨來源交叉驗證由人工移交 Agent 自動執行，由其計算可信度，高信心者自動入圖、低信心者進入人工佇列，並繪製一張 Agent 與人工的分工表。針對第二點，我並未貿然灌入資料，而是先建立重複率與涵蓋率的量測；此次將節點 @@自 75 擴充至 298@@，正是依這套量測逐步進行。擴充的結果也回頭驗證了委員的顧慮：規模放大後，風格性與傳承性的關係顯著增加，待判斷佇列也隨之成長，這恰好說明人工審查這一層必須隨資料規模等比例擴充，而非一次性作業。"));
children.push(B("使用者端，我先前已與成大攝影社的一位幹部初步討論此一構想，對方亦確認本學期仍在社團擔任幹部，故此條聯繫管道確實可行。指導老師謝吉隆老師的角色主要在於確認技術與穩定性；我尚未正式請益，計畫待那 165 條關係審查完成後，再一併帶著技術上的疑義請教。至於攝影內容與理論層面的問題，因不屬謝老師專長，我規劃向臺灣藝術大學的張國治老師請教，其專業涵蓋攝影、繪畫與藝術評論，本學期亦開設攝影課程。將正式接觸安排於雛型完成之後，是希望帶著可實際操作的版本進行討論，使對方更易理解此工具欲解決的問題，所得回饋也更為具體。更進一步的合作，例如與課程教師、攝影社團、攝影圖書室洽談，亦將待 Agent 雛型較為確定後再行推進。"));

// ───────── Q3 ─────────
children.push(q("3. 請對照「解方具體實施步驟」所需之關鍵能力，盤點目前的綜合狀態。"));
children.push(sub("3-1　已具備的關鍵能力"));
children.push(B("對照計畫書的實施步驟，以下幾項能力為我目前已具備者："));
children.push(L("資料與網絡分析：就讀經濟系、雙主修資工，並在資料科學與社會分析學程；曾於社會網絡分析課程完成泰雅族遷徙網絡專案，建立節點與關係、計算中心性的經驗可直接移植至本知識圖，也是此階段能迅速完成骨架的主因。"));
children.push(L("程式與資料管線：曾於財經資料公司擔任資料實習，並以語言模型進行批次標註、再以評分者間信度（inter-rater reliability）驗證標註品質；因此本案自然納入去重、版本控制與回歸測試，而非僅止於讓程式執行完成。"));
children.push(L("攝影的問題意識：長期從事紀實與街頭攝影，並讀過桑塔格《論攝影》，清楚此領域的核心困境在於論述散落、缺乏地圖，此一問題意識源於自身的拍攝經驗。"));
children.push(L("專案管理：曾共同創辦打工度假知識社群，並擔任資料分析社團課程長，習於將複雜工作拆解為可交付的階段。"));
children.push(sub("3-2　尚未（完全）具備的關鍵能力與補強方式"));
children.push(B("仍待補強之處與對應做法如下："));
children.push(L("攝影理論的縱深：要確認那些待判斷關係（目前 41 條），須回到原典與來源查證，例如許綺玲翻譯的班雅明《迎向靈光消逝的年代》與巴特《明室》，補上頁碼級引用。這項查驗已經著手：本階段我已逐條查證並確認了一批關係（詳見第 4 題），將其自待判斷移入正式圖。具體做法為每週固定撥出時段閱讀原典與核對來源，凡查得某關係的直接出處，即補入該關係的 source_ref 欄位並更新狀態；攝影內容的疑義，則向張國治老師請教。"));
children.push(L("權威判斷的方法學：在缺乏引用資料庫的領域判斷何者為權威，目前採來源分級加交叉驗證，惟此準則仍需以實驗持續打磨；因此我會持續進行權重敏感度測試，並將每次取捨記入決策日誌，使判斷有跡可循。"));
children.push(L("評估與介面：目前的檢核多集中在關係層次（可信度、重複率），對「推薦是否真的對使用者有用」仍缺乏實際回饋。這部分須待雛型交付攝影社與課程老師試用後，才能補上使用者端的評估；在此之前，先以穩定性測試集與小規模自測代替。"));

// ───────── Q4 ─────────
children.push(q("4.【個人組】如何設計自己與 AI 工具的分工模式？又預計透過何種檢核方式，確保此模式能達到最大效益？"));
children.push(B("人機分工的原則很單純：程式能完成的交由程式，僅在需要判斷時才交給 AI。整個系統以一個循環運作，分為七個步驟："));
children.push(L("規劃下一個擴充目標"));
children.push(L("檢索來源"));
children.push(L("抽取關係（此步由 AI 判斷）"));
children.push(L("評分分流"));
children.push(L("更新圖"));
children.push(L("監控重複率"));
children.push(L("決定是否繼續擴充"));
children.push(B("七步之中，@@僅「抽取關係」一步由 AI 判斷@@，其餘六步皆為確定性程式。如此安排，一方面使流程可重現、易於維護，另一方面將語言模型的用量集中於最需要之處，並控制 token 成本。人工在整個流程中僅負責三件事：於起點設定種子與權威準則、抽查被標為低信心的少數關係、以及檢視推薦結果。所謂設定種子，是先置入主線思想家與其代表作為起點，並訂立來源分級規則，明確界定何者為原典、何者為館所、何者僅為大眾轉述。"));
children.push(B("技術上，是否自動入圖取決於一個可信度分數。每條關係均帶有來源分級（原典、館所、評論、大眾）、佐證數，以及該關係在來源中被陳述的直接程度。分數為來源基礎權重，加上多來源佐證的加成，再乘以直接程度；其中原典基礎權重最高（0.85），大眾最低（0.30）。分數達 @@0.7@@ 以上自動入圖，未達者一律進入人工佇列。直接程度一項，用以區別「原文明言」與「自行推論」：伯格改寫班雅明為書中明載，直接程度給滿；若關係須仰賴前後文方能推得，直接程度即打折，分數隨之降低而落入待判斷。知識圖採可容納多重關係的結構（@@MultiDiGraph@@），故同一對人物間若同時存在影響與批判兩種關係，不會相互覆蓋。"));
children.push(B("這道人工檢驗的作用，以實例最為清楚。會通過、自動入圖者，多為結構性或原典明載的關係，例如："));
children.push(L("「刺點與知面互為對照」：出自巴特《明室》本人，全書即以此組張力組織，可信度 0.9 以上。"));
children.push(L("「伯格延伸班雅明」：《觀看的方式》開宗明義即在改寫班雅明。"));
children.push(L("概念原創，如「卡提耶-布列松提出決定性瞬間」「貝歇夫婦以並置格狀確立類型學」：皆出自其本人著作。"));
children.push(L("成員關係，如「卡提耶-布列松屬馬格南」「古斯基師從貝歇夫婦」：屬可查證的結構性事實。"));
children.push(B("會被擋下、留待查證者，多為詮釋性或風格性的傳承，例如："));
children.push(L("「克勞絲批判巴特」：系統一度生成此關係，我審查時發現克勞絲〈Notes on the Index〉為 1977 年，早於巴特《明室》的 1980 年，時序上不可能批判一本尚未出版的書，遂退回重構。"));
children.push(L("「巴特延伸班雅明」：查證後《明室》並未直接引用班雅明，此連結為譯者與評論者的主張（《明室》中譯者許綺玲恰亦譯過班雅明），屬二手說法。"));
children.push(L("風格歸屬與跨脈絡呼應，如「古斯基的冷面美學」「森山大道的 are-bure-boke」「郎靜山的集錦攝影」「巴贊與巴特遙相呼應」：看似合理，但缺乏頁碼級的直接出處，故一併保留於待判斷。"));
children.push(B("擴充至 298 節點後，待判斷佇列原為 167 條；經兩輪逐一上網查證、確認其中 124 條後，目前為 41 條（另有 2 條查證判定不成立、已 reject 排除），主要是需回原典補頁碼才能確認的風格性與傳承性連結。這些連結若無人工這道關卡，會被當成事實留在圖上，這正是我將低信心關係一律攔下的理由。"));
children.push(B("檢驗不只人工一層，另有三項輔助："));
children.push(L("權重敏感度實驗：以不同權重各跑一次、觀察推薦變動。將權重拉平或拉陡，名次幾乎不動（相關係數皆在 0.98 以上），僅在刻意顛倒層級時才明顯改變，顯示推薦對權重相當穩健。"));
children.push(L("穩定性測試集：以社群論壇口吻、並刻意加入錯字，撰寫 48 條問句，測試同一問題的不同寫法是否導向同一答案。此處反而發現，純程式解析口語化問句會漏接，佐證了這一步確應交由 AI。"));
children.push(L("回歸測試：目前 13 項，每次修改程式後執行即可檢出核心行為是否被破壞。"));
children.push(B("至於被擋下的關係，程式會自動彙整成一份清單，每條附上調查紀錄、參考來源與建議，末欄留待我填入 approved、rejected 或重構；經我確認後，程式方據此更新圖，使人工判斷有固定出口，不致散落各處。"));
children.push(B("這套出口，也讓「逐步查驗待確認清單」成為可操作的日常，而非一次性工程。本階段我已就待判斷清單逐一上網查證，將 @@152 條@@關係標為已確認（approved）並移入正式圖，涵蓋譯本與書目（各書譯者）、可查的結構性事實（馬格南／FSA／VIVO 成員、班雅明〈攝影小史〉與桑塔格《論攝影》具名討論的攝影家、新彩色與冷面美學的代表、台灣三劍客等），以及評論家具名的著作立場（Rosler、Sekula、Azoulay、Batchen 等）。查證過程也抓出需要修正的條目並據實保留：1977 年 Pictures 展的原始參展者並不含辛蒂·雪曼（僅雪莉·萊文），桑塔格《論攝影》具名討論的清單中亦不含愛德華·威斯頓，兩者經查證判定不成立，已標記為 rejected、排除於正式圖之外。其餘 41 條多為需回原典補頁碼才能確認的風格性與詮釋性連結，會依同樣流程逐步消化。這也讓待判斷清單從一個「未完成的缺口」，轉為一條「正在前進的查驗路徑」。"));
children.push(B("更深一層的體會，是這套權威啟發式有其邊界。來源分級、佐證數與直接程度能分辨「原典明載」與「純屬推論」，卻無法單憑程式區分一條有紮實文獻支撐的影響關係，和一條看似合理、實則查無出處的傳承。這也是我選擇把驗證這一步留給人、而非一路自動化的原因：在補上頁碼級引用之前，人工閱讀仍是唯一能把「合理」升級為「可查證」的環節。系統目前能做到的，是把不確定明確標示、集中到一處，而非消除不確定；在一個以防幻覺為核心價值的專案裡，這比一張外觀完整的圖更重要。這一階段也讓我較為具體地體會到：人機分工的界線不應憑猜測劃定，而可藉由實驗加以確立。"));

// ───────── Q5 ─────────
children.push(q("5. 新版預算規劃（本題字數不列入稿費計算）"));
children.push(p("AI 工具補助採實報實銷，補助期間為 115/10/01 至 12/31，訂閱制依「補助期間訂閱天數 ÷ 30 × 月費」計算。"));
children.push(table([2200,5146,2200],[
  new TableRow({children:[cell("項目",2200,{bold:true,fill:HDR}),cell("說明",5146,{bold:true,fill:HDR}),cell("估算（NT$）",2200,{bold:true,fill:HDR,align:AlignmentType.CENTER})]}),
  new TableRow({children:[cell("Claude 訂閱",2200),cell("核心開發與 Agent 抽取運算。10 月 Pro、11 月 Max、12 月 Pro",5146),cell("≈ 4,450",2200,{align:AlignmentType.RIGHT})]}),
  new TableRow({children:[cell("ChatGPT Plus 訂閱",2200),cell("跨模型交叉驗證：以第二個模型獨立複核 Agent 抽出的關係，降低單一模型偏誤。11、12 月",5146),cell("≈ 1,300",2200,{align:AlignmentType.RIGHT})]}),
  new TableRow({children:[cell("Notion AI",2200),cell("訪談逐字稿整理，以及洽談合作時以 AI 協助彙整文件。12 月",5146),cell("≈ 320",2200,{align:AlignmentType.RIGHT})]}),
  new TableRow({children:[cell("GPT API（儲值制）",2200),cell("自動化、大量之抽取運算。須於補助期間內用罄；因 Claude API 成本較高，改用 GPT API",5146),cell("≈ 3,900",2200,{align:AlignmentType.RIGHT})]}),
  new TableRow({children:[cell("合計",2200,{bold:true,fill:HDR}),cell("實報實銷，上限 10,000（以實際帳單為準）",5146,{fill:HDR}),cell("≈ 9,970",2200,{bold:true,fill:HDR,align:AlignmentType.RIGHT})]}),
]));
children.push(spc());
children.push(p("說明：金額為概算，含約百分之一點五的國外交易手續費，實際以帳單與當日匯率為準；外幣付款另附當日臺灣銀行牌告匯率。訂閱制按實際訂閱天數比例核銷；GPT API 為儲值制，僅於確定會在補助期間用罄時申請。"));

const doc = new Document({styles:{default:{document:{run:{font:FONT,size:22}}}},
  sections:[{properties:{page:{margin:{top:1300,bottom:1300,left:1100,right:1100}}},children}]});

const cnt=counted.join("");
const zh=(cnt.match(/[一-鿿]/g)||[]).length;
console.log("Q1-Q4 中文字=",zh," 含標點非空白=",cnt.replace(/\s/g,"").length);
Packer.toBuffer(doc).then(buf=>{fs.mkdirSync(OUT_DIR,{recursive:true});fs.writeFileSync(OUT_FILE,buf);console.log("written",OUT_FILE,buf.length);});
