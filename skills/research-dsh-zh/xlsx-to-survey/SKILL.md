---
name: xlsx-to-survey
user-invocable: true
description: 把 Excel／Word 問卷（xlsx/docx）轉成線上雙語問卷（Formbricks 等平台）：抽列 → 寫 spec → 自檢（含題序）→ 建卷 → 雙語與提交驗證 → 結果頁與 CSV/JSON 導出 → 改題後結構同步。當用戶要求「根據 xlsx/docx 生成問卷／創建問卷／導出問卷結果／問卷改題後同步」時使用。已填答的紙本／PDF 要回填成「一份答卷」請改用 /survey-backfill。
---

# xlsx-to-survey — Excel／Word 問卷 → 線上雙語問卷（建卷 · 驗證 · 導出）

將一份以 Excel 或 Word 撰寫的問卷（多為繁中，含 `□` 選項與 `____` 填空）轉為**線上雙語問卷**（`zh-TW` 預設 + `en-US`），並提供**結果導出**（單頁 web 報告 + CSV/JSON）與**改題後的結構同步**。

## 觸發方式

`/xlsx-to-survey <問卷.xlsx|問卷.docx> [目標平台]`

## 適用場景

- 手上是**空白問卷**的 xlsx／docx（尚未有人作答）→ 要建成線上問卷；
- 已建好的線上問卷要**導出結果**（web 報告 / CSV / JSON）；
- 線上問卷**改了題目結構**（增刪題、改題型、調順序）→ 同步 spec；
- 輸入也可以是**有文字層的 PDF**（Word 導出的問卷）：先轉文字再走同一流程。

## 不適用（請改用別的 skill）

| 情境 | 用哪個 |
|---|---|
| 已填答的**紙本／掃描 PDF**要當成「**一份答卷**」灌進**既有**問卷 | **`/survey-backfill`** |
| 訪談音檔轉寫、需要主觀判讀的材料 | 不適用 |
| 平台無管理 API 且無法自動化 | 不適用 |

> **邊界一句話**：本 skill 管「**造問卷／管問卷／出結果**」，`survey-backfill` 管「**把填好的紙本變成答卷**」。兩者共用同一套題目定義與結果頁。

## 輸入契約（開工前盤點）

| 輸入 | 說明 | 缺省 |
|---|---|---|
| 問卷源檔 | `.xlsx`／`.xlsm`／`.docx`，或**有文字層**的 PDF | 必需 |
| 目標平台 | 見 `adapters/<platform>.md` | 依實際部署 |
| 憑據 | API key 的**檔案路徑**或環境變數 | 必需，**不寫進產物** |
| 語言 | 預設 `zh-TW` + `en-US` | 依平台已註冊語言 |
| 結果頁 | 靜態 HTML 的 `static_name` + `result_dir` | 可省（不導出） |

## 硬約束（紅線）

- **R1 源檔為準**：選項、必填、題型一律回讀源檔；不確定就不要臆造選項。
- **R2 一律線上為準**：對映題目時**以線上問卷定義（`blocks`）為準**，不信 spec、不信紙本題號（問卷改版後題號會位移）。
- **R3 先自檢後建卷**：`check_spec.py` 必須先通過，才可 `create_survey_from_spec.py`。
- **R4 憑據與 PII**：API key 只從指定檔／環境變數讀取，**不寫入產物、不回顯**；問卷若含個人資料，報告不得公開發佈。
- **R5 不要用 fileUpload 題型**：自托管常見 presigned URL 指向內網物件儲存，受訪者瀏覽器不可達。
- **R6 改題前先暫停問卷**：受訪者瀏覽器持舊版題目時，服務端按**當前**問卷校驗 → 舊值不匹配 → 400「你的回覆無法提交且無法重試」。**先 `paused` 再改，改完恢復**。
- **R7 建卷後必做測試答卷並刪除**：測試資料不可殘留。
- **R8 原檔與中間產物保留**：源檔不改；spec／dump／回讀一律落盤可追溯。

## 工作流

### Step 0　盤點
確認源檔型別、目標平台、憑據路徑、語言設定；確認**是否有既有 spec**（有就別重複建卷）。

### Step 1　讀源檔
```bash
python3 assets/dump_xlsx.py <問卷.xlsx>      # 逐列印出（換行顯示為 ⏎）
python3 assets/dump_xlsx.py <問卷.docx>      # 段落＋表格，依文件順序
```
（無需安裝 openpyxl／python-docx：直接讀 OOXML。日期會是序號，需要真實日期時再另裝 openpyxl。）

**讀法要點**：
- xlsx 常見四欄：`調研專案`=分節、`序號`=題號、`專案資訊收集項`=題幹、`資訊回饋`=選項／填空格式；
- `□` 開頭的行 = 一個選項；`____` = 填空；文中「可多選」= multi；
- **複合題**（一題含多個子問）→ 拆成多個子題，id 用 `qN_xxx`，子題 `required` 依原意（純說明性的填空可不必填）；
- 附表明細表（如《企業場景調研明細表》）→ 用一個 openText 題 + 模板下載連結；
- 源檔多為簡體時：先轉繁（`zh-TW`），再譯英（`en-US`）。

### Step 2　寫 spec
存到 `<專案>/specs/<slug>_survey.json`。**欄位 schema 見 `adapters/formbricks.md`**（不同平台只差在這一層）。

必守：
- 每題 `headline_zh` + `headline_en`；選擇題必填 `choices: [{zh,en}]`；
- `other: true` → 平台會**自動**加一個 id 為 `other` 的「其他」選項，**spec 的 choices 不要再寫一個 other**；
- `numeric: true`（open 題）：純數字題才加 — 會渲染 `<input type=number>` 並加 `^-?\d+(\.\d+)?$` 服務端校驗，**佔位符也必須是純數字**（寫「約 50」「30-50」「80%」會被拒）；
- `sections` 的 questions 必須與 `questions` **一一對應**。

### Step 3　自檢（必做，紅線 R3）
```bash
python3 assets/check_spec.py <spec路徑>                     # 集合 + 順序 + 選項 + 題型
python3 assets/check_spec.py <spec路徑> --live --base <URL>  # 再與線上逐題對齊
```
**為什麼要比順序**：結果頁按 **`sections` 順序**渲染，受訪者按 **`questions` 順序**（＝線上 `blocks` 順序）作答。只比 `set()` 的話，順序錯位會**靜默通過**，結果頁就會把題卡掛到錯的題組、或把題卡排到 CTA 卡之後。`--strict` 可把順序問題升為 fatal。

### Step 4　建卷
```bash
python3 assets/create_survey_from_spec.py <spec路徑>
```
輸出 survey_id 並回寫 spec；並完成：建立問卷 → 寫入語言（`zh-TW` 預設 + `en-US`）→ 發佈 → 落 `survey_definition.json` 快照。

### Step 5　驗證（必做）
- 受訪頁預設語言與 `?lang=en-US` 各渲染一次，抽查題幹關鍵詞；
- 提交**一份測試答卷**（用 `language` = 預設語言代碼！否則會 fallback 到 `en`，選項比對與結果頁都會走英文槽）→ 導出 → 核對 → **刪除測試答卷**；
- 確認 `required` 題沒被繞過、`numeric` 題拒絕非數字（若設了）。

### Step 6　結果導出
```bash
python3 assets/export_survey_results2.py <spec路徑>    # 單卷
bash    assets/export_all_results.sh                    # 全部（掛 cron）
```
產出 `static/<results.static_name>`（web）與 `<result_dir>/`：`survey_results.html`、`responses.csv`（UTF-8-BOM，Excel 直開）、`results.json`、`survey_definition.json`。

> **受限沙箱提醒**：若 `static/`／`result_dir/` 在會話工作區之外，**不要手動跑 exporter**（會被沙箱擋下或半途失敗）；交給 cron，等它跑完再回讀頁面。

### Step 7　改題後同步
題目**文字／選項／副標題**取自線上 API，改這些不必動 spec；只有**結構變動**才同步：
```bash
python3 assets/sync_survey_spec.py <spec路徑>                    # 線上 → spec
python3 assets/sync_survey_spec.py --from-live <SID> <out.json>  # 無 spec 的舊問卷
```
同步後**再跑一次 `check_spec.py`**（`sections` 是「保留既有歸屬、新題併入末節」，很容易出現順序問題）。

### Step 8　交付
- spec 檔（含回寫的 `survey_id`）；
- 受訪連結（預設語言 + `?lang=en-US`）；
- 結果頁連結與 `responses.csv`／`results.json`；
- 若做過換卷／改題：變更前後的 spec 快照與原因。

## 產物

```
<專案>/
  specs/<slug>_survey.json          # 問卷定義（+ survey_id）
  <result_dir>/survey_results.html  # 結果頁副本
  <result_dir>/responses.csv        # 逐份答卷
  <result_dir>/results.json         # 統計
  <result_dir>/survey_definition.json  # 建卷/同步時的線上快照
  static/<static_name>              # 對外結果頁
```

## DSH 工具映射

| 用途 | 工具 |
|---|---|
| 讀 xlsx/docx、調 API、跑腳本 | `bash` + `assets/*.py`、`assets/*.sh` |
| 寫／改 spec | `write` / `edit` |
| 關鍵決策（平台、是否沿用既有 spec、是否發佈） | `ask_user_question` |
| 結果頁回讀 | `web_fetch`（或 `bash` + `curl`） |

## 平台適配

- `adapters/formbricks.md` —— spec schema 全欄位、管理 API、雙語寫入（需 SQL）、**提交側校驗規則**、結果頁渲染與題序陷阱、已知坑。
- 接入新平台時新增 `adapters/<platform>.md`：認證、建卷、讀卷、提交、刪除、結果導出、已知坑。

## 質量門（全過才算完成）

1. `check_spec.py` 無 FAIL（含**題序**與線上對齊）；
2. 問卷雙語皆可渲染，預設語言正確；
3. 測試答卷可提交**並已刪除**；
4. 結果頁題卡數 == 線上題數，題序與線上一致（`check_spec.py --live`）；
5. 結果頁統計與 API 回讀自洽（已答數、選項分桶）；
6. 交付物清單齊備，憑據未入產物。
