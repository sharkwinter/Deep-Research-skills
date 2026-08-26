---
name: research
user-invocable: true
description: 对目标话题进行初步调研。支持两种模式——表格模式（item×field 生成 outline，用于 benchmark/技术选型/多对象横评）与深度叙事模式（按角度分派子代理、落盘一手资料、产出叙事对比报告，用于演进/区别辨析/技术尽调）。
---

# Research Skill - 初步调研

## 触发方式
`/research <topic>`

## DSH 工具映射
本 skill 运行在 DeepSeek Harness（DSH）中：
- 询问用户 → `ask_user_question` 工具
- 联网检索 → `web_search` 工具；抓取网页原文/PDF → `bash`（curl）
- 启动子代理 → `subagent` 工具（后台）
- 文件读写 → `read` / `write` / `glob`；命令执行 → `bash`

## Step 0: 模式选择（先做）

用 `ask_user_question` 工具让用户选择调研模式（若从 topic 措辞已能明确判断，可直接建议默认项并说明，仍给用户改选机会）：

| 模式 | 适用 | 产物 |
|---|---|---|
| **A. 表格模式**（默认，多对象横评） | benchmark 调研、技术选型、竞品对比、"N 个对象 × 若干字段" | `outline.yaml` + `fields.yaml` → `/research-deep` → `/research-report` |
| **B. 深度叙事模式**（演进/区别/尽调） | "X 的演进与区别"、方案尽调、把一手资料读透形成文字结论、"搜索并获得文件形成结论" | `<topic>/深度调研报告.md`（叙事）+ `<topic>/sources/`（一手资料落盘）+ 可选 outline |

判断启发：话题是"一批同类对象各填相同字段"→ A；话题是"梳理脉络、辨析区别、对已有系统/方案做尽调"→ B。

- 选 A → 执行下方 **模式 A** 流程（Step 1~5）。
- 选 B → 执行下方 **模式 B** 流程（见"## 模式 B：深度叙事模式"），并遵循 `deep_narrative_playbook.md`（本 skill 目录下的资源文件，按 skill 资源指引中的 base directory 解析读取）。

---

## 模式 A：表格模式

### Step 1: 模型内部知识生成初步框架
基于topic，利用模型已有知识生成：
- 该领域的主要研究对象/items列表
- 建议的调研字段框架

输出{step1_output}，使用 `ask_user_question` 工具确认：
- items列表是否需要增减？
- 字段框架是否满足需求？

### Step 2: Web Search补充
使用 `ask_user_question` 工具询问时间范围（如：最近6个月、2024年至今、不限）。

**参数获取**：
- `{topic}`: 用户输入的调研话题
- `{YYYY-MM-DD}`: 当前日期
- `{step1_output}`: Step 1生成的完整输出内容
- `{time_range}`: 用户指定的时间范围

**硬约束**：以下prompt必须严格复述，仅替换{xxx}中的变量，禁止改写结构或措辞。

**子代理启动方式（DSH）**：
1. 用 `read` 工具读取 `~/.dsh/agents/web-search-agent.md` 全文，作为子代理 prompt 的 preamble（web-search 研究员人设与策略模块加载纪律）；
2. 子代理完整 prompt = preamble + 空行 + 下方模板渲染结果（仅替换变量，不改结构）；
3. 用 `subagent` 工具启动（`run_in_background: true`），description 填 `web-search: {topic}`。

启动1个web-search子代理（后台），**Prompt模板**：
```python
prompt = f"""## 任务
调研话题: {topic}
当前日期: {YYYY-MM-DD}

基于以下初步框架，补充最新items和推荐调研字段。

## 已有框架
{step1_output}

## 目标
1. 验证已有items是否遗漏重要对象
2. 根据遗漏对象进行补充items
3. 继续搜索{topic}相关且{time_range}内的items并补充
4. 补充新fields

## 输出要求
直接返回结构化结果（不写文件）：

### 补充Items
- item_name: 简要说明（为什么应该加入）
...

### 推荐补充字段
- field_name: 字段描述（为什么需要这个维度）
...

### 信息来源
- [来源1](url1)
- [来源2](url2)
"""
```

**One-shot示例**（假设调研AI Coding发展史）：
```
## 任务
调研话题: AI Coding 发展史
当前日期: 2025-12-30

基于以下初步框架，补充最新items和推荐调研字段。

## 已有框架
### Items列表
1. GitHub Copilot: Microsoft/GitHub开发，首个主流AI编程助手
2. Cursor: AI-first IDE，基于VSCode
...

### 字段框架
- 基本信息: name, release_date, company
- 技术特性: underlying_model, context_window
...

## 目标
1. 验证已有items是否遗漏重要对象
2. 根据遗漏对象进行补充items
3. 继续搜索AI Coding 发展史相关且2024年至今内的items并补充
4. 补充新fields

## 输出要求
直接返回结构化结果（不写文件）：

### 补充Items
- item_name: 简要说明（为什么应该加入）
...

### 推荐补充字段
- field_name: 字段描述（为什么需要这个维度）
...

### 信息来源
- [来源1](url1)
- [来源2](url2)
```

### Step 3: 询问用户已有字段
使用 `ask_user_question` 工具询问用户是否有已定义的字段文件，如有则读取并合并。

### Step 4: 生成Outline（分离文件）
合并{step1_output}、{step2_output}和用户已有字段，生成两个文件：

**outline.yaml**（items + 配置）：
- topic: 调研主题
- items: 调研对象列表
- execution:
  - batch_size: 并行agent数量（需用 `ask_user_question` 工具确认）
  - items_per_agent: 每个agent调研项目数（需用 `ask_user_question` 工具确认）
  - output_dir: 结果输出目录（默认./results）

**fields.yaml**（字段定义）：
- 字段分类和定义
- 每个字段的name、description、detail_level
- detail_level分层：极简 → 简要 → 详细
- uncertain: 不确定字段列表（保留字段，deep阶段自动填充）

### Step 5: 输出并确认
- 创建目录: `./{topic_slug}/`
- 保存: `outline.yaml` 和 `fields.yaml`
- 展示给用户确认

## 输出路径
```
{当前工作目录}/{topic_slug}/
  ├── outline.yaml    # items列表 + execution配置
  └── fields.yaml     # 字段定义
```

## 后续命令（模式 A）
- `/research-add-items` - 补充items
- `/research-add-fields` - 补充字段
- `/research-deep` - 开始深度调研

---

## 模式 B：深度叙事模式

用于"梳理演进 / 辨析区别 / 对已有系统或方案做技术尽调 / 把一手资料读透形成文字结论"。核心纪律见 `deep_narrative_playbook.md`（务必先读），要点：**按角度分派、一手落盘、载重自校、成本分层、叙事成文**。

### Step B1: 建工作区
- 创建 `./{topic_slug}/` 与 `./{topic_slug}/sources/`（用 `bash` 工具 `mkdir -p`）。

### Step B2: 拆解调研角度
从话题本身拆 3~5 个**研究角度**（不是 item），每个角度可被证据回答、且能改变结论。常见角度：学术/理论、产业/参考实现、标准/规范、工程/开源生态、失败模式/批评。用 `ask_user_question` 工具与用户确认角度集与时间范围。

### Step B3: 每角度一个子代理（一手落盘）
每个角度通过 `subagent` 工具启动 1 个子代理（后台运行；DSH 子代理沿用会话默认模型）。子代理 prompt 以 `~/.dsh/agents/web-search-agent.md` 全文为 preamble（保证检索纪律与策略模块加载），后接自包含 brief。每个子代理的 brief **必须自包含**（不共享主控上下文），并强制：
- 用 `web_search` 工具检索、`bash`+`curl` 抓取权威一手源（规范/论文/官方文档/维护活跃的仓库）；
- **把每个采用的源落盘**到 `{topic_slug}/sources/`：网页存 `doc_<slug>.md`（含 `# 标题` / `Source URL:` / `Access date:` 头 + 实质摘录）；PDF 用 `curl -L -o {abs}/sources/arxiv_<id>_<slug>.pdf <url>` 并校验非零且以 `%PDF` 开头；
- 写 `{topic_slug}/sources/SOURCES-<angle>.md` 清单表：本地文件名｜标题｜作者年｜URL｜一句话相关性；
- **返回**结构化 findings（每条：论断＋数字/日期＋源文件名＋是否支持/反驳假设），不写最终报告。

主控**核验**每个子代理的落盘（`bash`: `ls sources/`、查文件非零、抽查清单）——"报告 15 个源却只落 3 个"的情况真实发生过。若话题涉及本地代码/仓库，由主控自己直接勘察并写 `local_*.md` 源note（子代理只做网络侧，避免重复）。

### Step B4: 载重事实自校
成为结论承诺的关键事实（版本号、许可证、性能数字、标准编号、能力边界）在主控侧二次核验；无法核验的在报告中标注"待验"。

### Step B5: 叙事成文
主控综合所有 findings + 本地勘察，写 `./{topic_slug}/深度调研报告.md`：
- 头部：调研日期 / 方法 / 证据基座（sources 份数 + 清单指针）；
- `## 0 核心结论(TL;DR)` 编号要点；
- 按角度分节的正文（就地引用所落盘的源文件名，可追溯）；
- 结论/建议 + `## 参考文献`（指向各 `SOURCES-*.md`）。
- 交付：在回复中告知用户报告文件与 `sources/` 目录的路径，并说明证据基座位置（DSH Web GUI 可直接查看工作区文件）。

### 模式 B 产物
```
{当前工作目录}/{topic_slug}/
  ├── 深度调研报告.md         # 叙事结论（就地引用源文件名）
  └── sources/                # 一手资料落盘
      ├── doc_*.md / *.pdf    # 网页摘录 / 下载的 PDF
      ├── SOURCES-<angle>.md  # 每角度清单
      └── local_*.md          # （可选）本地仓一手勘察 note
```
