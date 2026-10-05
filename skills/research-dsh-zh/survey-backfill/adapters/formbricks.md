# 适配器：Formbricks（管理 API）

以下为在自托管 Formbricks（v3.38 系）实测可用的结论，供 `survey-backfill` 使用。

## 认证与地址

- 地址：`WEBAPP_URL`（如 `http://host:port`）。
- 认证头：`X-API-KEY: <workspace api key>`（形如 `fbk_...`）。
- Key 位置：部署目录 `.env` 中的自定义变量（示例部署为 `MACAO_API_KEY`）。**只读文件，不写入产物。**
- 管理 API 前缀：`/api/v1/management/`。
- 自检：`GET /api/v1/management/me` → 返回 workspace/environment（两者 id 常相同）。

## 取问卷结构

```
GET /api/v1/management/surveys/{surveyId}
```

关注字段：
- `questions[]`：`id` / `type`（`openText`/`multipleChoiceSingle`/…）/ `required` / **`inputType`**（`text`|`number`）/ `choices[].label`（`zh-TW`/`default`/`en-US`）；
- `blocks[]`：题目分组（部分接口 PUT 时需要 blocks 而非 questions）；
- `status`：`paused` / `scheduled` / `running`。

## 提交答卷

```
POST /api/v1/management/responses
X-API-KEY: ...
{"workspaceId": "...", "surveyId": "...", "finished": true, "data": {"<questionId>": "<value>"}}
```

实测要点：
- **`workspaceId` 必填**，与 `surveyId` 同放在 body；
- 额外字段（`userId`/`meta`/`ttc`…）非必需；
- 校验按题目 `inputType` 生效：`number` 题只接受纯数字字符串（`40`、`2.5`、`-5` 通过；`2~3`、`30-50`、`80%`、`未知` 全部 400），错误形如
  `{"code":"bad_request","message":"Validation failed","details":{"response.data.<qid>":"Please enter a valid format"}}`；
- **问卷处于 `paused`/`scheduled` 不影响管理 API 写入**（公开链接 /s/ 不可填，但管理 API 可提交）；
- 缺题（未作答）直接不传该 key，汇总页即计为未答/跳过。

## 选项取值口径（关键坑）

汇总页用 `label` 反查选项 id：

```js
choices.find(c => c.label[lang] === value || Object.values(c.label).includes(value))?.id || "other"
```

因此选择题**必须存选项 label 文字**（zh-TW/default 一致时存该文字），存 `option id` 会被判为「其他」。
单选若纸面写了多个选项或自定义文字（如「A和B都可」「GPU+NPU」），按原文存该文字 → 汇总归入「其他」。

## 回读 / 列表（有分页！）

```
GET /api/v1/management/responses?surveyId={sid}&limit=50&skip={n}
```

- **默认每页 25 条**：28 条答卷只取默认页会误判为 25，务必显式 `limit` 并循环 `skip` 直到空页；
- 删除：`DELETE /api/v1/management/responses/{responseId}`（pilot 测试后必须清理）。

## 本平台不支持的接口（避免踩坑）

- `PATCH /api/v1/management/surveys/{sid}` 改状态 → **405**（该部署未开放）；不要试图用 API 启停问卷；
- `/api/v1/client/*`（客户端 API）不存在（返回 SPA HTML）；公开链接的结果提交走 Server Actions，无法直接复用；
- 有无响应体歧义时以 HTTP 状态码 + JSON 判断，SPA HTML 响应说明路由不存在。

## 静态结果页（本类部署常见）

结果页常由 spec + 生成脚本 + cron 产出（如 `deploy/static/<name>_results.html`）：
- 页面按 **spec** 渲染题卡（题干取 live 问卷，题库清单取 spec）→ **spec 缺题会静默少卡**；
- 修复：把缺失 question id 补进 spec 对应分节（顺序与 live 问卷一致）→ 备份 spec → 重跑生成脚本 → 回读页面核对；
- 自查：脚本输出的 `qid answered x/N` 行与 API 回读逐题比对。
