# 转写手册：视觉 fan-out、放大复核、冲突仲裁

本手册是 `survey-backfill` Step 3–4 的执行细则。核心经验：**手写中文单轮识别不可信**，承重字段（数字/选项/姓名）必须二轮复核、三轮仲裁。

## 0. 前置：模型与尺寸

- 必须用**支持图像输入**的模型。DSH 里若主模型是纯文本，`read_image` 会报
  `model "..." does not declare image input`；必须在 `workflow` 中覆盖：
  ```js
  agent(prompt, { label: `page-${n}`, schema, provider: "zijie", model: "glm-5.3-flash" })
  ```
  （provider/model 以当前会话可用清单为准。）
- 页图缺省 150 DPI 渲染（A4 纵向约 1241×1754）。复核时用**上/下半页裁剪图**：等效分辨率翻倍，是小字与连笔的关键。
- 一页通常 = 一位受访者。多页一份时先判页角色（`start`/`continuation`），再按笔迹与题号拼接。

## 1. 初始转写（每页一个子代理）

要点：
- prompt 里给出**线上问卷题目清单**（题号+题意），让代理按内容对齐，而不是死认纸面编号；
- 明确列出页面上哪些是**印刷内容**（提示框、图表截图、样例数据），避免被当成手写答案；
- 输出用 schema 约束；**不要让它回传印刷题干全文**（体积大且无信息量）。

紧凑 schema（推荐）：
```json
{
  "type": "object",
  "properties": {
    "page": {"type": "number"},
    "page_role": {"type": "string", "enum": ["start", "continuation", "blank", "unknown"]},
    "respondent_name": {"type": "string"},
    "answers": {"type": "array", "items": {"type": "object", "properties": {
      "question_ref": {"type": "string"},
      "answer": {"type": "string"},
      "ticked_options": {"type": "array", "items": {"type": "string"}},
      "empty": {"type": "boolean"}
    }, "required": ["question_ref"]}},
    "notes": {"type": "string"}
  },
  "required": ["page", "page_role", "respondent_name", "answers", "notes"]
}
```

Prompt 骨架：
```
你是手写问卷识别员。用 read_image 读取：<绝对路径>

背景：<问卷主题>；纸版一页覆盖全部 N 题（或按分节）。印刷的<提示框/图表>不是手写答案。

线上题目：
Q1 <题干> … Q16 <题干>

任务：
1. page_role / respondent_name / answers（question_ref 用 Q1..Qn；逐字转写，数字精确；
   无法辨认用「？」标注；勾选题把被勾选选项的完整文字放进 ticked_options；留空则 empty=true）。
2. notes：一行内说明辨认难点。只写你确实看到的内容，绝不编造。
```

**fan-out 用 `pipeline`**（每页独立，无 barrier）：
```js
const results = await pipeline(pageList, (prev, n) =>
  agent(promptFor(n), { label: `page-${n}`, schema, provider, model }));
return { pages: results };
```

## 2. ⚠️ 结果体积与落盘（真实翻车点）

`workflow` 的返回值在工具结果里**会被截断**（本次 28 页约 74 KB 只回传 37 KB），临时 spill 文件会被清理。对策：

- schema 里**剔除冗余字段**（如印刷题干全文）；必要时**分两批**跑（例如 1–14 / 15–28）；
- 拿到返回值后**立刻**落盘（`final_pages.json`），不要等待后续步骤；
- 若已被截断：会话日志 `$DSH_SESSION_JSONL` 里存有工具结果原文，可解出；完整对象可用
  `json.JSONDecoder().raw_decode` 从断点前**逐对象抢救**（本次据此救回 23/28 页）；
- 剩余缺失页**只补跑缺失部分**，不要整批重跑。

## 3. 放大复核（第二轮，只查不确定字段）

给每个有待核字段的页一个子代理，喂**上下半页裁剪图**，附上第一轮结果，要求逐字段给最终值与置信度（high/medium/low），并显式说明「空白未作答」与「无法辨认」的区别。

## 4. 冲突仲裁（第三轮，只裁承重字段）

第二轮常与第一轮在**数字/姓名/选项**上冲突。把冲突字段单独列出，附两轮读法，用裁剪图重新裁决：

```
你是手写识别仲裁员。裁决第 N 页以下字段：Q2、Q11、Q15
图片：<上/下半页裁剪图>
争议：Q2 第一轮「50」/第二轮「30」；Q15 第一轮「B」/第二轮「A」
要求：逐个字段给最终值与置信度；无法辨认填「无法辨认」。
```

合并优先级：**仲裁 > 复核 > 初读**。仍有分歧的低置信值照常填入，但必须进报告的低置信清单。

## 5. 手写识别的常见坑（实测）

| 坑 | 表现 | 处理 |
|---|---|---|
| 易混字形 | `6/0`、`7/9`、`3/5`、`1/7`、`50/5` | 仲裁轮专项确认；与同页其他题交叉验证（如 10 人中 10 人用 AI ⇒ 100%） |
| 区间作答 | `30-50`、`2~3` | 数字题不接受 → 取中值并进审计表 |
| 汉字作答数字题 | 「未知」「不少於」「數十」 | 无法数值化 → 留空（该题为未答）并记录 |
| 选择题写字母 | 括号内写 `A/B/C` 而非勾选 | 映射为选项 label 文字 |
| 多选题/自定义 | 「A和B都可」「GPU+NPU」 | 单选平台按原文存入「其他」 |
| 签名式姓名 | 连笔、形近字多解 | 三轮多数表决；仍不确定则取最可能值 + 低置信标注 |
| 页边批注 | 题目区域外的潦草笔记 | 归入其所在题区域；无法辨认则不填 |
| 空白页/仅签名 | 无任何作答 | 仍作为一条答卷提交（仅姓名或全空），并在报告标注 |
