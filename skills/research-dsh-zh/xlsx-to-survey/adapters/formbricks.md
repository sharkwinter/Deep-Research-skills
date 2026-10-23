# 適配器：Formbricks（自托管）

本檔收錄 **平台相關**的一切：spec schema、管理 API、雙語寫入、提交側校驗、結果頁渲染。
`SKILL.md` 的流程本身與平台無關；換平台只要換掉本檔。

---

## 1. 認證與地址

| 項目 | 值 |
|---|---|
| 地址 | `WEBAPP_URL`（自托管常見 `http://localhost` / 對外網域） |
| 認證頭 | `X-API-KEY: <workspace api key>`（形如 `fbk_...`） |
| Key 位置 | 部署目錄 `.env` 的自訂變數（如 `MACAO_API_KEY`） |
| 管理 API 前綴 | `/api/v1/management/` |
| 自檢 | `GET /api/v1/management/me` → 回傳 workspace／environment（兩者 id 常相同） |

`assets/survey_lib.py` 的可移植設定（**本 repo 版**）：

```bash
export SURVEY_API_BASE=http://localhost     # 或 http://host:port
export SURVEY_WORKSPACE_ID=<workspaceId>
export SURVEY_API_KEY=fbk_...
export SURVEY_DEPLOY_DIR=/path/to/deploy    # SQL / redis 操作需要（docker compose 專案目錄）
# 或以設定檔：export SURVEY_CONFIG=/path/to/.env（KEY=VALUE）
```
舊變數名 `MACAO_API_KEY` 仍相容。**Key 不寫進任何產物。**

> **參考部署**（本 skill 的來源專案）：`/root/Working/polling/deploy`，workspace `cmth1r8g1000101ql8rcdp3it`，
> key 在 `deploy/.env` 的 `MACAO_API_KEY`，已註冊語言 `zh-TW`（預設）＋ `en-US`。
> 該部署自帶一份**寫死設定**的同名 `survey_lib.py`；repo 這份是可移植版，預設值下行為一致。

---

## 2. spec schema（全欄位）

```jsonc
{
  "survey_id": null,            // 建卷後由 create_survey_from_spec.py 回寫
  "slug": "macao-univ",         // 供結果頁記住 條形圖/分布圖 的檢視偏好
  "name": "…", "name_en": "…",
  "welcome": { "headline_zh","headline_en","subheader_zh","subheader_en","button_zh","button_en" },
  "ending":  { "headline_zh","headline_en","subheader_zh","subheader_en" },
  "sections": [ { "title_zh","title_en","questions": ["q1","q4",…] } ],
  "questions": [
    {
      "id": "q1",                       // 語意化短 id；子題用 qN_xxx
      "type": "open",                   // open | single | multi
      "required": true,
      "headline_zh": "…", "headline_en": "…",
      "subheader_zh": "…", "subheader_en": "…",
      "placeholder_zh": "…", "placeholder_en": "…",
      "long_answer": false,             // open 題用 textarea
      "numeric": true,                  // open 題：<input type=number> + 服務端 pattern
      "choices": [ { "zh": "…", "en": "…" } ],   // single/multi 必填
      "other": true,                    // 自動追加一個 id="other" 的選項
      "other_label_zh": "其他", "other_label_en": "Other",
      "other_placeholder_zh": "…", "other_placeholder_en": "…",
      "max_selections": 3               // multi 限選
    }
  ],
  "results": { "static_name": "xxx_results.html", "result_dir": "…", "title_zh": "…", "title_en": "…" }
}
```

**注意**
- `choices` 只寫 `{zh,en}`，**id 由建卷程式生成**（`q9_brands_c1`、`q9_brands_c2`…）。**不要**自己寫 `id: "other"`，否則會與自動生成的「其他」衝突。
- `sections` 的 questions 與 `questions` 必須**一一對應**；`check_spec.py` 另外要求**兩者順序一致**（見 §5）。
- 選項文案請與線上既有題目**保持一字不差**：結果頁是用 **label 文字**反查選項的（見 §4）。

---

## 3. 管理 API

### 讀問卷
```
GET /api/v1/management/surveys/{surveyId}
```
關注：`questions[]`（`id`/`type`/`required`/**`inputType`**/`choices[].label`/`validation`）、
`blocks[]`（**題組歸屬與作答順序的真相**）、`status`（`paused`/`scheduled`/`inProgress`）。

> ⚠️ `questions[]` 的**順序可能與 `blocks[]` 不同**。受訪者看到的是 `blocks` 順序，一律以 `blocks` 為準。

### 建卷 / 改卷
- `POST /api/v1/management/surveys`
- `PUT` 時 **`questions` 與 `blocks` 不能同時提交**；建卷時 `create_survey_from_spec.py` 送 `questions`-only，之後服務端自動轉 `blocks`，因此**後續 PUT 要用 `blocks`-only**。

### 語言（`zh-TW` / `en-US`）
- v1 API **無法序列化 ZLanguage 日期欄位** → 語言只能**直接寫 SQL**（`SurveyLanguage` 表）。
- 使用者若在編輯器改題，會寫入 `default` 槽；**導出前先 `normalize_survey`**（把 `default` 鏡像到 `zh-TW`，冪等，`export_survey_results2.py` 已內建）。
- 改完問卷要 **flush redis**（`normalize_survey` PUT 後會自動做）。

### 提交答卷
```
POST /api/v1/client/{workspaceId}/responses
{ "workspaceId": "...", "surveyId": "...", "finished": true, "language": "zh-TW",
  "data": { "<questionId>": "<value>" }, "meta": { ... } }
```
- **`language` 一定要設對**（`zh-TW`）：不設會 fallback 到 `en`，label 比對與結果頁顯示都會走英文槽。
- **管理 API**也可寫入：`POST /api/v1/management/responses`（body 需 `workspaceId` + `surveyId`）。問卷處於 `paused`/`scheduled` **不影響管理 API 寫入**（只是公開連結不能填）。
- v1 **沒有 idempotency**：一次只提交一次；重跑前先確認是否已存在。

### 回讀 / 刪除
```
GET    /api/v1/management/responses?surveyId={sid}&limit=50&skip={n}   # 有分頁！預設 25
DELETE /api/v1/management/responses/{responseId}
```
`/survey-backfill` 的 `assets/submit_responses.py` 提供 `list / pilot / bulk / verify / delete`，可直接借用。

### 本平台不支援
- `PATCH /api/v1/management/surveys/{sid}` 改狀態 → **405**（部分部署未開放）；不要用 API 啟停問卷。
- `/api/v1/client/*` 的**公開提交**走 Server Actions，無法直接複用；但上面那個 `POST .../client/{ws}/responses` 端點可用。
- 回傳 SPA HTML 代表該路由不存在（別把 HTML 當 JSON 解析）。

---

## 4. 提交側校驗規則（讀自 Formbricks 源碼，2026-09 版）

位置：`apps/web/modules/api/lib/validation.ts` → `packages/surveys/src/lib/validation/evaluator.ts`

| 規則 | 位置 | 實務含義 |
|---|---|---|
| **只校驗「有提交」的欄位** | `validateResponseData` 先 `filter(el => el.id in responseData)` | **required 題沒提交不會被擋** → 源檔沒問的題可安全略過 |
| 選項值接受 **choice id 或該語言 label** | `validateChoiceMembership` | 兩者都收；**建議用 label** |
| **有「其他」選項的題完全不校驗成員資格** | `hasOtherOption` → 提前 return | 自由文字直接傳即可 |
| **無「其他」選項的選擇題只接受既有 id/label** | `validateChoiceMembership` 收尾 | ⚠️ 想塞「多選合併文字」到單選題會 **400** |
| 多選的「其他」用**哨兵 `""`** | `value.indexOf("")` → `value[i+1]` 為文字 | 傳 `[...已選 label, "", "自由文字"]`，哨兵後**必須緊跟非空文字** |
| 單選的「其他」**直接傳自由文字** | `validateSingleSelectOtherValue` | 例如傳 `"40%"`，**不要**傳 label |
| 數字題（`inputType=number`）只收純數字 | 建卷時的 `pattern` | `2~3`、`30-50`、`80%`、`未知` 全 400 |

**結果頁的選項分桶**（`export_survey_results2.py`）：
```python
choices.find(c => c.label[lang] === value || Object.values(c.label).includes(value))?.id || "other"
```
→ 存到**選項 label 文字**才對得上；對不上的一律落進「其他（自填）」。這是**逐字校驗**，全形/半形、空格、破折號都要一致。

---

## 5. 結果頁渲染（與題序陷阱）

- 結果頁由 `export_survey_results2.py` 依 spec 生成，cron 可每 10 分鐘重生。
- **題目文字／選項／副標題取自「線上 API」；題目清單與順序取自「spec」** → 改文案不必動 spec，**改結構必須同步 spec**。
- ⚠️ **題序陷阱**：結果頁按 **`spec['sections']` 順序**渲染，受訪者按 **`spec['questions']`（＝線上 `blocks`）順序**作答。兩者順序不一致時，結果頁會把題卡掛到錯的題組、甚至排到 CTA 卡之後。
  - **`set(questions) == set(section_refs)` 這種比法會靜默通過**（集合相等但順序不同）。
  - 用 `check_spec.py`（比順序）或 `check_spec.py --live` 抓。
  - 修法：把跑錯位置的題目移回**它所屬的題組**；CTA 卡（`type: cta`）必須是最後一張。
- 結果頁特性：條形圖／分布圖切換（偏好存 localStorage，按 `slug` 區分）；openText 以**直方圖**呈現（全為純數字則按數值升序，否則按次數降序）；多選分布圖角度＝各選項被選次數佔總選擇次數比；舊標籤標「舊選項 old label」；「其他」自由文字單獨列出。
- logo 取 `styling.logo` → workspace logo → 預設圖。

---

## 6. 已知坑（歷史教訓）

1. **改題會讓受訪者卡死**：受訪者持舊版題目（舊選項文案），服務端按**當前**問卷校驗 → 400「你的回覆無法提交且無法重試」，中間狀態答卷 `finished=false` 卡住，只能請對方重填或刪掉。→ **改題前先 `paused`**，改完恢復；改完 `sync_survey_spec.py`。
   - 邏輯條件的 `rightOperand` 存的是**選項 ID**（如 `q18_c1`），增刪選項後要檢查 id 是否還在。
2. **`questions`／`blocks` 不能同時 PUT**（見 §3）。
3. **v1 無法寫語言**（ZLanguage 日期）→ 只能 SQL。
4. **Redis 有快取**：改問卷後 `FLUSHALL`。
5. **`fileUpload` 不可用**：presigned URL 指向內網 minio（`S3_ENDPOINT_URL=http://minio:9000`），受訪者瀏覽器不可達；logo／上傳走 `S3_PUBLIC_ENDPOINT_URL` 換公網 host 才正常。
6. **要複製既有問卷當新版本時**：副本會掉 `showLanguageSwitch`（變 `null`），且編輯器新增的題／選項常缺 `en-US` 值（**空字串會阻斷 v1 PUT**）。切副本流程：歸檔原卷答卷 → 修副本 `showLanguageSwitch`／en-US → 原卷改名 `- old` 並 `paused` → spec 的 `survey_id` 改指副本 → `sync_survey_spec.py` → 導出。
7. **`inputType` 會漂移**：spec 寫 `numeric: true` 但線上被編輯器改成 text（`check_spec.py --live` 的 R10 會提醒）。此時數字題其實不校驗，非純數字值也能提交 — **不要因此就塞非數字**，分析時要能算。
