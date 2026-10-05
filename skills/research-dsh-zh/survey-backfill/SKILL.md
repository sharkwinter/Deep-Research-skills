---
name: survey-backfill
user-invocable: true
description: 把手写/扫描的纸质问卷 PDF 逐份识别并回填到线上问卷（Formbricks 等平台）：先拉取在线问卷结构，再并行视觉转写 + 放大复核 + 冲突仲裁，按平台校验适配取值，pilot 提交回读后全量提交，最后核查结果页与问卷一致性并落盘报告。
---

# Survey Backfill - 纸质问卷识别与线上回填

## 触发方式

`/survey-backfill <问卷PDF> <线上问卷URL或ID> [凭据文件]`

例：`/survey-backfill /root/Working/Macao/EndClass_Survey/xxx（回填结果）.pdf http://host/workspaces/<ws>/surveys/<sid> /root/Working/polling/deploy/.env`

## 适用场景

- 一批**手写/扫描**纸质问卷（扫描件通常无文本层）需要搬进线上问卷系统；
- 线上问卷题目与纸质问卷一一对应（多为同一份问卷的电子化）；
- 交付要求：线上答卷 + 可追溯的识别/转换审计 + 低置信字段清单。

不适用：访谈音频转写、需要主观判读的材料、平台无提交接口且无法浏览器自动化、纸质与电子题目无法对齐。

## 输入契约（开工前逐一盘点，缺项先问）

| 输入 | 说明 | 缺省 |
|---|---|---|
| 问卷 PDF | 扫描件；先 `pdftotext` 判断有无文本层、`pdfinfo` 看页数与旋转 | 必需 |
| 目标问卷 | URL 或 survey id（同时记下 workspace/environment id） | 必需 |
| 凭据 | API key 的**文件路径**（如 `deploy/.env` 里的 `*_API_KEY`） | 必需 |
| 题目映射 | 纸质题号 ↔ 线上 question id | 缺省按内容自动对齐，并请用户确认 |
| 数值处置 | 区间/百分比/「未知」等文本如何进数字题 | 缺省：去单位；区间取中值；不可数值化→留空 |
| 身份口径 | 每页一份还是每份多页；是否需要去重标记 | 缺省每页一份，用 AskUserQuestion 确认 |

## 硬约束（红线）

- **R1 绝不编造**：看不清就留空；低置信字段必须单列清单交人工复核。
- **R2 先 pilot 后批量**：批量写入前先提交 1 条并回读校验结构。
- **R3 不污染、可重跑**：测试答卷必须删除；重跑前先核对是否已有本批答卷（幂等），避免重复灌入。
- **R4 凭据与 PII**：API key 只从指定文件读取，不写入产物、不回显；姓名等 PII 不外传第三方、不写进可公开的报告。
- **R5 选项口径**：选择题按平台的**匹配口径**存值——Formbricks 汇总页按选项 **label 文字**匹配，存 option id 会全部落进「其他」。
- **R6 数字题**：多数平台的数字题只接受纯数字；区间/汉字值必须按策略转换或留空，并逐条留审计。
- **R7 保留原件**：原 PDF 与页图不做破坏性处理；识别中间结果一律落盘。

## 工作流

### Step 0　盘点参数与凭据
`pdfinfo`/`pdftotext` 判断扫描件性质；确认目标问卷 id；定位 API key。
用 AskUserQuestion 确认：页数=受访者数？数值处置策略？是否允许写入线上？

### Step 1　拉取线上问卷结构
用平台 API 取问卷定义并落盘 `survey.json`，必须记录：
- 每题 `id`／`type`／`required`／**`inputType`（数字题！）**／选项 **label**（zh/default/en）；
- 提交接口必填字段与校验规则；列表接口的分页参数。
> 结构没拿到就不要开始识别——识别结果无处映射。

### Step 2　渲染页图
`bash assets/render_pages.sh <pdf> <outdir> [dpi]`：PDF→PNG（缺省 150 DPI）并生成上/下半页裁剪图（供复核）。

### Step 3　并行视觉转写（必须用支持图像的模型）
按 `playbook_transcribe.md` 的模板 fan-out：每页一个子代理，**结构化输出**（页角色／姓名／逐题答案／勾选项／备注）。
> DSH 注意：主模型若不支持图像，`read_image` 会直接报错；用 `workflow` 的 `agent(prompt, {provider, model})` 覆盖到图像模型。

### Step 4　放大复核 + 冲突仲裁
第二轮用裁剪图复核不确定字段；第三轮只对**数字/选项/姓名**等承重字段的冲突逐条仲裁。
合并优先级：**仲裁 > 复核 > 初读**。

### Step 5　取值适配
- 数字题：按策略转换（去 `%`、去「約」、区间取中值…），不可数值化→留空；
- 选择题：映射为平台口径的**选项文字**；单选出现多选或自定义文字时，按原文存为「其他」；
- 产出**转换审计表**（原值 → 写入值）。

### Step 6　pilot 提交 + 回读
提交 1 条 → GET 回读 → 核对字段数/取值/选项口径 → 无误再继续。

### Step 7　全量提交 + 计数核对
批量提交（失败逐条记录、可重试）；提交后用列表 API **分页**拉全量，核对条数与每题已答数。
`assets/submit_responses.py` 提供 `list / pilot / bulk / verify / delete` 子命令。

### Step 8　结果页/汇总一致性核查
若存在静态结果页或报表（常由 spec/模板 + cron 生成）：
- 逐题比对 **live 问卷题库 ↔ 结果页题卡**（题号、题序、是否覆盖）：结果页按 spec 渲染时，**spec 缺题会静默少一张卡**；
- 核对每题「已答数」与 API 一致；选择题分桶、均值/总和等统计与数据自洽；
- 需要改 spec/模板时先备份原文件，再重跑生成脚本，并回读页面验证。

### Step 9　报告与交付
落盘 `BACKFILL_REPORT.md`：受访者清单、识别轮次、数值转换审计、低置信字段表、提交与核对证据、遗留问题。

## 产物

```
<workdir>/
  survey_pages/        # 页图（page-NN.png）
  crops/               # 复核用裁剪图（上下半页）
  pages_all.json       # 初读结果
  pages_verified.json  # 复核结果
  final_dataset.py     # 人工裁决后的最终数据（或 final_dataset.json）
  final_payloads.json  # 提交载荷
  verify_responses.json# 提交后 API 回读
  BACKFILL_REPORT.md   # 交付报告
```

## DSH 工具映射

| 用途 | 工具 |
|---|---|
| PDF 元信息/渲染、调 API | `bash`（`pdfinfo`/`pdftotext`/`pdftoppm`）+ `assets/*.sh|py` |
| 视觉转写与复核 | `workflow`（`agent(prompt, {provider, model})` 指定图像模型）+ `read_image` |
| 单点复看 | `read_image`（读裁剪图） |
| 落盘/修改 | `write` / `edit` |
| 关键决策 | `ask_user_question`（页数口径、数值策略、是否写入线上） |

## 平台适配

- `adapters/formbricks.md` —— Formbricks 管理 API：提交/回读/删除、选项 label 口径、数字题校验、分页、暂停态仍可写入等**实测结论**。
- 接入新平台时新增 `adapters/<platform>.md`：认证方式、取问卷结构、提交、回读、删除、已知坑。

## 质量门（全过才算完成）

1. 提交条数 == 页数（或差异有据并记录）；
2. 每题已答数与 API 回读一致；
3. 选择题分桶与原始勾选一致，数字题无非法值；
4. 结果页/汇总与 live 问卷逐题对齐（覆盖 + 题序）；
5. 转换审计表与低置信清单齐备。
