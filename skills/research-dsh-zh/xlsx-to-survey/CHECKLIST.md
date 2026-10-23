# CHECKLIST — xlsx/docx → 線上問卷

## 開工前

- [ ] 源檔型別確認（xlsx／docx／**有文字層**的 PDF）；PDF 無文字層 → 走 `/survey-backfill` 的視覺路線
- [ ] 目標平台與 `adapters/<platform>.md` 已讀
- [ ] API base／workspaceId／key 來源已確認；**key 不會寫進任何產物**
- [ ] 已確認**是否已有既有 spec**（有就別重複建卷；先 `sync_survey_spec.py`）
- [ ] 已確認語言（預設 `zh-TW` + `en-US`）與結果頁設定（`static_name`／`result_dir`）

## 抽列與寫 spec

- [ ] `dump_xlsx.py` 已跑，四欄語意（分節／題號／題幹／選項）已辨明
- [ ] `□` 行已逐個轉成選項；`____` 已轉成填空；「可多選」已轉成 multi
- [ ] 複合題已拆成子題（`qN_xxx`），子題 `required` 依原意
- [ ] 附表／明細表已用 openText + 模板連結處理
- [ ] 簡體內容已轉繁（`zh-TW`），英文（`en-US`）已補
- [ ] **沒有**使用 `fileUpload` 題型
- [ ] `other: true` 的題，`choices` 裡**沒有**自己再寫一個 `other`
- [ ] `numeric: true` 的題，佔位符是**純數字**

## 自檢（建卷前，紅線）

- [ ] `check_spec.py <spec>` 無 FAIL
- [ ] **題序**：`sections` 攤平順序 == `questions` 順序（結果頁按 sections 渲染！）
- [ ] `sections` 的 questions 與 `questions` 集合**且順序**一致
- [ ] CTA／提示卡（`type: cta`）排在**最後**
- [ ] （有既有問卷時）`check_spec.py --live` 無 FAIL

## 建卷與驗證

- [ ] `create_survey_from_spec.py` 成功，`survey_id` 已回寫 spec
- [ ] 語言列已寫入（SQL），`zh-TW` 為預設
- [ ] 受訪頁預設語言渲染正常；`?lang=en-US` 英文渲染正常
- [ ] 提交**一份測試答卷**（`language` 設為預設語言代碼）
- [ ] 測試答卷已導出核對，且**已刪除**（`DELETE /api/v1/management/responses/{id}`）

## 結果導出

- [ ] `export_survey_results2.py` 跑通；`static/<static_name>` 可存取
- [ ] `responses.csv`（UTF-8-BOM）、`results.json`、`survey_definition.json` 已產出
- [ ] 結果頁**題卡數 == 線上題數**，且**題序與線上一致**
- [ ] 結果頁已答數／選項分桶與 API 回讀自洽
- [ ] 已掛進 cron 批量腳本（如需定時重生）
- [ ] 受限沙箱中**沒有**手動跑 exporter（交給 cron）

## 改題後（結構變動）

- [ ] **先 `paused` 再改**，改完恢復（避免受訪者 400 卡死）
- [ ] `sync_survey_spec.py` 已同步 spec
- [ ] 同步後**重跑 `check_spec.py`**（新題會併入末節，易生題序問題）
- [ ] 邏輯條件的 `rightOperand` 選項 id 仍存在
- [ ] redis 已 flush；結果頁已重生並回讀

## 交付

- [ ] spec 檔（含 `survey_id`）
- [ ] 受訪連結（預設語言 + `?lang=en-US`）
- [ ] 結果頁連結 + `responses.csv`／`results.json`
- [ ] 換卷／改題的變更前後快照與原因
