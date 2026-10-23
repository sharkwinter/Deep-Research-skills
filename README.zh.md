# Deep Research Skill for Claude Code / OpenCode / Codex / DeepSeek Harness

[English](README.md) | [中文](README.zh.md)

> 如果喜欢就请 star 一下吧！:star:

> 灵感来源：[RhinoInsight: Improving Deep Research through Control Mechanisms for Model Behavior and Context](https://arxiv.org/abs/2511.18743)

适用于 Claude Code、OpenCode、Codex 和 DeepSeek Harness（DSH）的结构化调研工作流技能。两种调研模式——**表格模式**（item × field outline → 深度调研 → 报告）与**深度叙事模式**（按角度分派子代理 → 一手资料落盘 → 叙事报告）——加上下游交付（**Word 报告**、**两页胶片提纲**、**调研知识本体**）与问卷工具链（**建卷 → 回填 → 分析**）。人在回路设计确保每个阶段的精确控制。

![Deep Research Skills 工作流](workflow.png)

## 使用场景

- **学术研究**：论文综述、benchmark评测、文献分析
- **技术研究**：技术对比、框架评估、工具选型
- **市场研究**：竞品分析、行业趋势、产品比较
- **尽职调查**：公司研究、投资分析、风险评估
- **问卷建卷与数据回填**：把 Excel/Word 问卷转成双语线上问卷并导出结果（`/xlsx-to-survey`）；纸质/扫描问卷识别并回填线上问卷、结果页与问卷一致性核查（`/survey-backfill`）
- **问卷分析**：把线上问卷答卷做成可复现、可更新的分析 notebook——逐主体快照（下限/中值/上限）→ 核心估算 → 深入剖析 → 自填文本 LLM 归类；并可扩展出「目标清单 × 问卷反馈」覆盖表与主体级合并总表（`/survey-analysis-notebook`）
- **正式报告与宣讲**：以既有 `.docx` 模板出正式 Word 报告（样式完整还原、上标引用角标、参考文献）（`/docx-report`）；把调研成果逐对象转成两页宣讲提纲（`/research-slides`）
- **知识本体**（DSH）：立项前查「这家/这个议题查过没有、哪些字段已有证据」，收工后把带证据的结论经受控通道落进本体并回看改动史（`/research-kb`）

## 安装

```bash
git clone https://github.com/Weizhena/deep-research-skills.git
cd deep-research-skills
```

### Claude Code
```bash
# 中文版
cp -r skills/research-zh/* ~/.claude/skills/

# 英文版
cp -r skills/research-en/* ~/.claude/skills/

# 必需：安装agent和模块
cp agents/web-search-agent.md ~/.claude/agents/
cp -r agents/web-search-modules ~/.claude/agents/

# 必需：安装Python依赖
pip install pyyaml
```

### OpenCode (默认: gpt-5.4)
```bash
# Skills (同 Claude Code)
cp -r skills/research-zh/* ~/.claude/skills/   # 或 research-en 英文版

# 必需：为当前 shell 启用 web search
export OPENCODE_ENABLE_EXA=1

# 可选：写入 ~/.bashrc，永久生效
echo 'export OPENCODE_ENABLE_EXA=1' >> ~/.bashrc
source ~/.bashrc

# 必需：安装agent和模块
cp agents/web-search-opencode.md ~/.config/opencode/agents/web-search.md
cp -r agents/web-search-modules ~/.config/opencode/agents/

# 必需：安装Python依赖
pip install pyyaml
```

> **重要**：在 OpenCode 中，任何模型要想使用 `websearch`，需要设置 `OPENCODE_ENABLE_EXA=1`。单纯 `export` 只对当前 shell 生效；写入 `~/.bashrc` 后才是永久生效。不设置时，只有 `web fetch`，对深度调研阶段会弱很多。

### Codex
```bash
# 英文版
mkdir -p ~/.codex/skills ~/.codex/agents
cp -r skills/research-codex-en/* ~/.codex/skills/

# 中文版
mkdir -p ~/.codex/skills ~/.codex/agents
cp -r skills/research-codex-zh/* ~/.codex/skills/

# 必需：安装 web researcher agent 和模块
cp agents-codex/web-researcher.toml ~/.codex/agents/
cp -r agents-codex/web-search-modules ~/.codex/agents/

# 必需：安装 Python 依赖
pip install pyyaml
```

使用以下两种方式之一更新 `~/.codex/config.toml`：

**方式 A：自动脚本**

```bash
cd deep-research-skills
bash scripts/install-codex.sh
```

**方式 B：手动编辑**

```toml
suppress_unstable_features_warning = true

[features]
multi_agent = true
default_mode_request_user_input = true

[agents.web_researcher]
description = "Use this agent when you need to research information on the internet, particularly for debugging issues, finding solutions to technical problems, or gathering comprehensive information from multiple sources. This agent excels at finding relevant discussions. Use when you need creative search strategies, thorough investigation, or compilation of findings from multiple sources."
config_file = "agents/web-researcher.toml"
```

### DeepSeek Harness (DSH)
```bash
# 中文版（当前唯一的 DSH 变体）
bash scripts/install-dsh.sh zh
```

安装到 `$DSH_HOME`（默认 `~/.dsh`）：
- Skills → `~/.dsh/skills/`（`research`、`research-add-items`、`research-add-fields`、`research-deep`、`research-report`、`research-kb`、`docx-report`、`research-slides`、`survey-analysis-notebook`、`survey-backfill`、`xlsx-to-survey`）
- web-search 子代理人设 + 策略模块 → `~/.dsh/agents/`（`web-search-agent.md`、`web-search-modules/`）

平台差异说明：
- DSH 没有 Claude Code 式的命名 agent 注册表：research skills 会自行读取 `~/.dsh/agents/web-search-agent.md`，把全文内联为每个 `subagent` prompt 的 preamble。
- 联网检索使用 DSH 内置的 `web_search` 工具——无需 `OPENCODE_ENABLE_EXA` 等环境变量。
- 安装脚本会把已安装文件中的 `~/.dsh` 字面量改写为 `$DSH_HOME` 的绝对路径，因为 DSH 的 `read` 工具不展开 `~`。
- 必需：`pip install pyyaml`（安装脚本会检查）。

DSH 会监听 skill 根目录，正在运行的会话无需重启即可发现新装的 skills。

## 命令

> **Claude Code 2.1.0+**：现已支持直接 `/skill-name` 触发！
>
> **旧版本**：请使用 `run /skill-name` 格式。
>
> **Codex**：可以通过 `/skills` -> `List Skills` 选择这些 skills，也可以用自然语言触发，例如 `Use the research skill to build an outline for AI Agent Demo 2025`。
>
> **DSH**：在 Web GUI 输入框直接输入 `/skill-name` 即可触发（输入 `/` 会弹出用户可调用 skills 列表，手打 `/research` 效果相同）。

| 命令 (2.1.0+) | 描述 |
|---------------|------|
| `/research` | 两种模式：**表格模式**（生成含 items 和 fields 的 outline）或**深度叙事模式**（按角度分派子代理 + 一手资料落盘 + 叙事报告） |
| `/research-add-items` | 向现有outline添加更多调研对象 |
| `/research-add-fields` | 向现有outline添加更多字段定义 |
| `/research-deep` | 使用并行agents对每个item进行深度调研 |
| `/research-report` | 从JSON结果生成markdown报告 |
| `/research-kb`（DSH） | 调研本体的读写面：立项前查「这家/这个议题查过没有、哪些字段已有证据」，收工后把带证据的结论经受控通道落进本体，并回看改动史与引用解析状态 |
| `/docx-report` | 以既有 Word（.docx）模板为骨架生成正式中文调研报告：完整还原模板样式，产出无自动编号、带可点击上标引用角标与详尽参考文献的 .docx |
| `/research-slides` | 把调研成果**逐对象**转成两页沟通胶片提纲：第一页业务架构（方向-痛点-趋势），第二页技术架构（AI/Agent 构想与算力需求分层） |
| `/xlsx-to-survey` | Excel/Word 问卷 → 双语（zh-TW/en-US）线上问卷：抽列 → 写 spec → 含题序的自检 → 建卷 → 提交验证 → 结果导出（web 报告 + CSV/JSON）→ 改题后结构同步 |
| `/survey-backfill` | 手写/扫描纸质问卷 PDF → 线上问卷：视觉转写 + 多轮复核仲裁 + 平台校验适配 + pilot 提交回读 + 结果页一致性核查 |
| `/survey-analysis-notebook` | 线上问卷答卷 → 可复现、可更新的分析 notebook：分页拉数 → 逐主体快照（下限/中值/上限）→ 核心估算 → 汇总 → 深入剖析 → 自填文本 LLM 归类 → 容器内执行验证并落地 Jupyter；可扩展出「目标清单 × 问卷反馈」覆盖表与主体级合并总表（桶上限口径、「1+4」产业分类、人工「采信」标注） |

### 两种调研模式

`/research` 启动前会先询问采用哪种模式：

- **表格模式**（默认）—— 即下方的 item × field 流程（`outline.yaml` + `fields.yaml` -> `/research-deep` -> `/research-report`）。适合 benchmark 调研、技术选型、竞品横评。
- **深度叙事模式** —— 把话题拆成 3~5 个研究**角度**，每角度一个子代理，**把每份一手资料落盘到 `sources/`** 并写分角度清单，对承重事实二次核验，最终产出就地引用这些源文件的叙事报告 `深度调研报告.md`。适合梳理演进脉络、辨析路线区别、对已有系统做技术尽调。纪律见 `skills/research-*/research/deep_narrative_playbook.md`。

### 从调研到交付物

两种模式都止于一份报告；另有四个兄弟技能接着往下做（都是独立技能，也可单独使用）：

| 技能 | 吃什么 | 产出什么 |
|---|---|---|
| `/research-report` | `results/*.json`（表格模式） | 带目录的 `report.md` |
| `/docx-report` | 报告初稿 + `.docx` 模板 | 正式 Word 报告（模板样式还原、上标引用角标、参考文献） |
| `/research-slides` | `results/<slug>.json` | 每对象一份**两页胶片提纲**（业务视角／技术视角），用于走访或宣讲 |
| `/research-kb`（DSH） | 某个主体或议题 | 「查过没有、哪些字段已有证据」＋经受控通道回写结论＋改动史 |

深度叙事模式的产物（`深度调研报告.md` + `sources/`）是带就地文件引用的 markdown，可直接交给 `/docx-report` 出正式版。

## 工作流 & 示例

> **示例**：调研 "AI Agent Demo 2025"（表格模式）

### 阶段1：生成Outline
```
/research AI Agent Demo 2025
```
💡 **会发生什么**：告诉它你要研究什么 → 它帮你列出调研清单

对于 Codex，可以这样说：
```
Use the research skill to build an outline for AI Agent Demo 2025
```

**你会得到**：17个待调研的AI Agent清单（ChatGPT Agent、Claude Computer Use、Cursor等）+ 每个要收集哪些信息

### （可选）不满意？继续添加
```
/research-add-items
/research-add-fields
```
💡 **会发生什么**：补充更多调研对象或字段定义

### 阶段2：深度调研
```
/research-deep
```
💡 **会发生什么**：AI自动上网搜索每个item的详细信息，逐个完成

**你会得到**：每个Agent的详细资料（公司、发布日期、定价、技术规格、用户评价...）

### 阶段3：生成报告
```
/research-report
```
💡 **会发生什么**：所有数据 → 一份整理好的报告

**你会得到**：`report.md` - 带目录的完整Markdown报告，可直接阅读或分享

### 示例：深度叙事模式

```
/research 某城市 AI 算力政策的演进，以及几种方案的路线区别
```
💡 **会发生什么**：`/research` 先问用哪种模式 → 选 **B（深度叙事）** → 把话题拆成 3~5 个**角度**，
每角度一个子代理，**把每份一手资料落盘到 `sources/`**（含分角度清单），对承重事实二次核验，最后才写叙事。

**你会得到**：
```
<topic>/
  ├── 深度调研报告.md        # 叙事结论，就地引用已落盘的源文件
  └── sources/<angle>/       # 每角度的清单 + 原文/片段
```
需要正式交付时再接：`/docx-report`（Word，模板样式还原）或 `/research-slides`（逐对象两页胶片提纲）。

## 遇到问题？

如果过程中有什么不懂的，可以让 Claude Code、OpenCode 或 Codex 帮你理解这个项目：
```
帮我理解这个项目: https://github.com/Weizhena/deep-research-skills
```

## 参考文献

- RhinoInsight: Improving Deep Research through Control Mechanisms for Model Behavior and Context

## 许可证

MIT
