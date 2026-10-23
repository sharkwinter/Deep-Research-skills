# Deep Research Skill for Claude Code / OpenCode / Codex / DeepSeek Harness

[English](README.md) | [中文](README.zh.md)

> If you find this project helpful, please give it a star! :star:

> Inspired by [RhinoInsight: Improving Deep Research through Control Mechanisms for Model Behavior and Context](https://arxiv.org/abs/2511.18743)

A structured research workflow skill for Claude Code, OpenCode, Codex, and DeepSeek Harness. Two research modes — **table** (item × field outline → deep dive → report) and **deep-narrative** (angle-based subagents → primary sources saved to disk → narrative report) — plus downstream deliverables (**Word report**, **two-page slide outlines**, **research knowledge base**) and a survey toolchain (**build → backfill → analyze**). Human-in-the-loop design ensures precise control at every stage.

![Deep Research Skills Workflow](workflow.png)

## Use Cases

- **Academic Research**: Paper surveys, benchmark reviews, literature analysis
- **Technical Research**: Technology comparison, framework evaluation, tool selection
- **Market Research**: Competitor analysis, industry trends, product comparison
- **Due Diligence**: Company research, investment analysis, risk assessment
- **Data Capture, Surveys & Backfill**: Turn an Excel/Word questionnaire into a bilingual online survey with results export (`/xlsx-to-survey`); recognize handwritten/scanned paper surveys and backfill them into an online survey, then audit results pages against the questionnaire (`/survey-backfill`)
- **Survey Analytics**: Turn online survey responses into a reproducible, updatable analysis notebook — snapshot tiers → core estimates → deep dives → LLM coding of free text — plus target-list coverage and a subject-level merged master table (`/survey-analysis-notebook`)
- **Formal Reports & Briefings**: Render a Word report from an existing `.docx` template with preserved styles and superscript citations (`/docx-report`); turn finished research into a two-page slide outline per subject for interviews or briefings (`/research-slides`)
- **Knowledge Base** (DSH): Before starting, check whether a subject/topic has been researched and which fields already have evidence; after finishing, write evidence-backed conclusions back and review the change history (`/research-kb`)

## Installation

```bash
git clone https://github.com/Weizhena/deep-research-skills.git
cd deep-research-skills
```

### Claude Code
```bash
# English version
cp -r skills/research-en/* ~/.claude/skills/

# Chinese version
cp -r skills/research-zh/* ~/.claude/skills/

# Required: Install agent and modules
cp agents/web-search-agent.md ~/.claude/agents/
cp -r agents/web-search-modules ~/.claude/agents/

# Required: Install Python dependency
pip install pyyaml
```

### OpenCode (default: gpt-5.4)
```bash
# Skills (same as Claude Code)
cp -r skills/research-en/* ~/.claude/skills/   # or research-zh for Chinese

# Required: Enable web search for current shell
export OPENCODE_ENABLE_EXA=1

# Optional: make it permanent
echo 'export OPENCODE_ENABLE_EXA=1' >> ~/.bashrc
source ~/.bashrc

# Required: Install agent and modules
cp agents/web-search-opencode.md ~/.config/opencode/agents/web-search.md
cp -r agents/web-search-modules ~/.config/opencode/agents/

# Required: Install Python dependency
pip install pyyaml
```

> **Important**: In OpenCode, ANY model's websearch requires `OPENCODE_ENABLE_EXA=1`. A plain `export` only affects the current shell; writing it to `~/.bashrc` makes it persistent. Without it, you only get `web fetch`, which is weaker for the deep research phase.

### Codex
```bash
# English version
mkdir -p ~/.codex/skills ~/.codex/agents
cp -r skills/research-codex-en/* ~/.codex/skills/

# Chinese version
mkdir -p ~/.codex/skills ~/.codex/agents
cp -r skills/research-codex-zh/* ~/.codex/skills/

# Required: Install web researcher agent and modules
cp agents-codex/web-researcher.toml ~/.codex/agents/
cp -r agents-codex/web-search-modules ~/.codex/agents/

# Required: Install Python dependency
pip install pyyaml
```

Add or update `~/.codex/config.toml` using either method below:

**Option A: Automatic script**

```bash
cd deep-research-skills
bash scripts/install-codex.sh
```

**Option B: Manual edit**

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
# Chinese version (currently the only DSH variant)
bash scripts/install-dsh.sh zh
```

Installs into `$DSH_HOME` (default `~/.dsh`):
- Skills → `~/.dsh/skills/` (`research`, `research-add-items`, `research-add-fields`, `research-deep`, `research-report`, `research-kb`, `docx-report`, `research-slides`, `survey-analysis-notebook`, `survey-backfill`, `xlsx-to-survey`)
- Web-search subagent persona + strategy modules → `~/.dsh/agents/` (`web-search-agent.md`, `web-search-modules/`)

Platform notes:
- DSH has no named-agent registry: the research skills read `~/.dsh/agents/web-search-agent.md` themselves and inline its full text as the preamble of every `subagent` prompt.
- Web search uses DSH's built-in `web_search` tool — no `OPENCODE_ENABLE_EXA` or other env vars needed.
- The installer rewrites `~/.dsh` literals in the installed files to the absolute `$DSH_HOME` path, because DSH's `read` tool does not expand `~`.
- Required: `pip install pyyaml` (the installer checks it).

DSH watches the skill roots, so running sessions pick the skills up without a restart.

## Commands

> **Claude Code 2.1.0+**: Direct `/skill-name` trigger is now supported!
>
> **Older versions**: Use `run /skill-name` format instead.
>
> **Codex**: You can trigger these skills from `/skills` -> `List Skills`, or ask naturally, for example `Use the research skill to build an outline for AI Agent Demo 2025`.
>
> **DSH**: `/skill-name` works directly in the Web GUI input box (the `/` menu lists user-invocable skills; a hand-typed token works the same).

| Command (2.1.0+) | Description |
|------------------|-------------|
| `/research` | Two modes: **Table** (outline with items and fields) or **Deep-narrative** (angle-based subagents + saved primary sources + narrative report) |
| `/research-add-items` | Add more research items to existing outline |
| `/research-add-fields` | Add more field definitions to existing outline |
| `/research-deep` | Deep research each item with parallel agents |
| `/research-report` | Generate markdown report from JSON results |
| `/research-kb` (DSH) | The read/write face of a research knowledge base: check coverage before starting, write evidence-backed conclusions back through a controlled channel, review change history and citation resolution |
| `/docx-report` | Render a formal Chinese Word report from an existing `.docx` template: full style fidelity, clickable superscript citations, detailed bibliography |
| `/research-slides` | Turn finished research into a two-page slide outline **per subject**: page 1 business architecture (direction / pain points / trend), page 2 technical architecture (AI-agent idea + compute tiers) |
| `/xlsx-to-survey` | Turn an Excel/Word questionnaire into a bilingual (zh-TW/en-US) online survey: row dump, spec authoring, order-aware self-check, create, submit-verify, then results export (web page + CSV/JSON) and structure re-sync |
| `/survey-backfill` | Backfill handwritten/scanned paper surveys into an online survey: vision transcription + multi-pass review/adjudication + platform-rule adaptation + pilot submit/read-back + results-page audit |
| `/survey-analysis-notebook` | Turn online survey responses into a reproducible, updatable analysis notebook: paged API pull → per-subject snapshot (lower/mid/upper tiers) → core estimates → summary → deep dives → LLM coding of free text → execute & verify in the Jupyter container; extends to target-list coverage and a subject-level merged master table (bucket-upper tier, "1+4" industry tagging, human "trust" marks) |

### Two research modes

`/research` asks which mode fits before it starts:

- **Table mode** (default) — the item x field workflow below (`outline.yaml` + `fields.yaml` -> `/research-deep` -> `/research-report`). Best for benchmarks, technology selection, competitor comparison.
- **Deep-narrative mode** — splits the topic into 3-5 research *angles*, gives each its own subagent, **saves every primary source to `sources/`** with a per-angle manifest, self-verifies load-bearing facts, and writes a narrative `Deep_Research_Report.md` that cites the saved files. Best for tracing an evolution, telling approaches apart, or technical due diligence on an existing system. Discipline: `skills/research-*/research/deep_narrative_playbook.md`.

### From research to deliverables

Both modes stop at a report; four siblings take it further (they are separate skills, usable on their own):

| Skill | Takes | Produces |
|---|---|---|
| `/research-report` | `results/*.json` (table mode) | `report.md` with TOC |
| `/docx-report` | report draft + a `.docx` template | formal Word report — template styles preserved, superscript citations, bibliography |
| `/research-slides` | `results/<slug>.json` | one **two-page slide outline per subject** (business view / technical view) for interviews or briefings |
| `/research-kb` (DSH) | a subject or topic | "have we researched this, which fields already have evidence" + controlled write-back of conclusions, with change history |

Narrative mode's output (`深度调研报告.md` + `sources/`) is markdown with in-place file citations, so it can go straight into `/docx-report`.

## Workflow & Example

> **Example**: Researching "AI Agent Demo 2025" (Table mode)

### Phase 1: Generate Outline
```
/research AI Agent Demo 2025
```
💡 **What will happen**: Tell it your topic → It creates a research list for you

**You get**: A list of 17 AI Agents to research (ChatGPT Agent, Claude Computer Use, Cursor, etc.) + what info to collect for each

### (Optional) Not satisfied? Add more
```
/research-add-items
/research-add-fields
```
💡 **What will happen**: Add more research items or field definitions

### Phase 2: Deep Research
```
/research-deep
```
💡 **What will happen**: AI automatically searches the web for each item, one by one

**You get**: Detailed info for each Agent (company, release date, pricing, tech specs, reviews...)

### Phase 3: Generate Report
```
/research-report
```
💡 **What will happen**: All data → One organized report

**You get**: `report.md` - A complete markdown report with table of contents, ready to read or share

### Example: Deep-narrative mode

```
/research How a city's AI-compute policy evolved, and how the competing proposals differ
```
💡 **What will happen**: `/research` asks which mode fits → pick **B (deep-narrative)** → it splits the topic into 3–5 **angles**, gives each angle its own subagent that **saves every primary source** under `sources/` (with a per-angle manifest), re-checks the load-bearing facts, and only then writes the narrative.

**You get** (paths follow the skill's language variant; shown for the zh skills):
```
<topic>/
  ├── 深度调研报告.md        # narrative conclusions, citing the saved files in place
  └── sources/<angle>/       # manifest + raw pages / snippets per angle
```
Then, if you need a formal deliverable: `/docx-report` (Word, template styles preserved) or
`/research-slides` (two-page outline per subject).

## Need Help?

If you have questions, ask Claude Code, OpenCode, or Codex to explain this project:
```
Help me understand this project: https://github.com/Weizhena/deep-research-skills
```

## References

- RhinoInsight: Improving Deep Research through Control Mechanisms for Model Behavior and Context

## License

MIT
