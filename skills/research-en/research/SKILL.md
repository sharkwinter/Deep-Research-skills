---
name: research
user-invocable: true
allowed-tools: Read, Write, Glob, Bash, WebSearch, Task, AskUserQuestion
description: Conduct preliminary research on a topic. Two modes — Table mode (item x field outline, for benchmarks/tech selection/multi-object comparison) and Deep-narrative mode (angle-based subagents, primary sources saved to disk, narrative comparison report, for evolution/distinction analysis/technical due diligence).
---

# Research Skill - Preliminary Research

## Trigger
`/research <topic>`

## Step 0: Choose Mode (do this first)

Use AskUserQuestion to let the user pick the research mode (if the topic wording already makes it clear, recommend a default and say why — still let the user override):

| Mode | Fits | Deliverables |
|---|---|---|
| **A. Table mode** (default, multi-object comparison) | benchmark research, technology selection, competitor comparison, "N objects x the same fields" | `outline.yaml` + `fields.yaml` -> `/research-deep` -> `/research-report` |
| **B. Deep-narrative mode** (evolution / distinctions / due diligence) | "the evolution of X and how it differs", solution due diligence, reading primary sources closely into written conclusions, "search, save the files, produce conclusions" | `<topic>/Deep_Research_Report.md` (narrative) + `<topic>/sources/` (primary sources saved) + optional outline |

Heuristic: a batch of similar objects each filled with the same fields -> A; tracing a lineage, telling approaches apart, or doing due diligence on an existing system/solution -> B.

- Mode A -> run the **Mode A** workflow below (Steps 1-5).
- Mode B -> run the **Mode B** workflow (see "## Mode B: Deep-Narrative Mode") and follow `deep_narrative_playbook.md`.

---

## Mode A: Table Mode

### Step 1: Generate Initial Framework from Model Knowledge
Based on topic, use model's existing knowledge to generate:
- Main research objects/items list in this domain
- Suggested research field framework

Output {step1_output}, use AskUserQuestion to confirm:
- Need to add/remove items?
- Does field framework meet requirements?

### Step 2: Web Search Supplement
Use AskUserQuestion to ask for time range (e.g., last 6 months, since 2024, unlimited).

**Parameter Retrieval**:
- `{topic}`: User input research topic
- `{YYYY-MM-DD}`: Current date
- `{step1_output}`: Complete output from Step 1
- `{time_range}`: User specified time range

**Hard Constraint**: The following prompt must be strictly reproduced, only replacing variables in {xxx}, do not modify structure or wording.

Launch 1 web-search-agent (background), **Prompt Template**:
```python
prompt = f"""## Task
Research topic: {topic}
Current date: {YYYY-MM-DD}

Based on the following initial framework, supplement latest items and recommended research fields.

## Existing Framework
{step1_output}

## Goals
1. Verify if existing items are missing important objects
2. Supplement items based on missing objects
3. Continue searching for {topic} related items within {time_range} and supplement
4. Supplement new fields

## Output Requirements
Return structured results directly (do not write files):

### Supplementary Items
- item_name: Brief explanation (why it should be added)
...

### Recommended Supplementary Fields
- field_name: Field description (why this dimension is needed)
...

### Sources
- [Source1](url1)
- [Source2](url2)
"""
```

**One-shot Example** (assuming researching AI Coding History):
```
## Task
Research topic: AI Coding History
Current date: 2025-12-30

Based on the following initial framework, supplement latest items and recommended research fields.

## Existing Framework
### Items List
1. GitHub Copilot: Developed by Microsoft/GitHub, first mainstream AI coding assistant
2. Cursor: AI-first IDE, based on VSCode
...

### Field Framework
- Basic Info: name, release_date, company
- Technical Features: underlying_model, context_window
...

## Goals
1. Verify if existing items are missing important objects
2. Supplement items based on missing objects
3. Continue searching for AI Coding History related items within since 2024 and supplement
4. Supplement new fields

## Output Requirements
Return structured results directly (do not write files):

### Supplementary Items
- item_name: Brief explanation (why it should be added)
...

### Recommended Supplementary Fields
- field_name: Field description (why this dimension is needed)
...

### Sources
- [Source1](url1)
- [Source2](url2)
```

### Step 3: Ask User for Existing Fields
Use AskUserQuestion to ask if user has existing field definition file, if so read and merge.

### Step 4: Generate Outline (Separate Files)
Merge {step1_output}, {step2_output} and user's existing fields, generate two files:

**outline.yaml** (items + config):
- topic: Research topic
- items: Research objects list
- execution:
  - batch_size: Number of parallel agents (confirm with AskUserQuestion)
  - items_per_agent: Items per agent (confirm with AskUserQuestion)
  - output_dir: Results output directory (default: ./results)

**fields.yaml** (field definitions):
- Field categories and definitions
- Each field's name, description, detail_level
- detail_level hierarchy: brief -> moderate -> detailed
- uncertain: Uncertain fields list (reserved field, auto-filled in deep phase)

### Step 5: Output and Confirm
- Create directory: `./{topic_slug}/`
- Save: `outline.yaml` and `fields.yaml`
- Show to user for confirmation

## Output Path
```
{current_working_directory}/{topic_slug}/
  ├── outline.yaml    # items list + execution config
  └── fields.yaml     # field definitions
```

## Follow-up Commands (Mode A)
- `/research-add-items` - Supplement items
- `/research-add-fields` - Supplement fields
- `/research-deep` - Start deep research

---

## Mode B: Deep-Narrative Mode

For tracing an evolution, telling approaches apart, doing technical due diligence on an existing system or solution, or reading primary sources closely into written conclusions. The discipline lives in `deep_narrative_playbook.md` (read it first): **dispatch by angle, save primary sources, self-verify load-bearing facts, tier the cost, write it as narrative.**

### Step B1: Create the workspace
- Create `./{topic_slug}/` and `./{topic_slug}/sources/` (Bash `mkdir -p`).

### Step B2: Break the topic into research angles
Derive 3-5 **research angles** (not items) from the topic itself. Each must be answerable by evidence and capable of changing the conclusion. Common angles: academic/theory, industry/reference implementations, standards/specs, engineering/open-source landscape, failure modes/criticism. Confirm the angle set and time range with AskUserQuestion.

### Step B3: One subagent per angle (primary sources to disk)
Launch one subagent per angle (in the background; haiku for fetch-heavy angles, sonnet where conclusion quality matters). Each brief must be **self-contained** (it does not share your context) and must require:
- WebSearch/WebFetch for authoritative primary sources (specs, papers, official docs, maintained repos);
- **Saving every source used** into `{topic_slug}/sources/`: web pages as `doc_<slug>.md` with a `# Title` / `Source URL:` / `Access date:` header plus the substantive extract; PDFs via `curl -L -o {abs}/sources/arxiv_<id>_<slug>.pdf <url>`, verified non-zero and starting with `%PDF`;
- Writing `{topic_slug}/sources/SOURCES-<angle>.md`: a table of local filename | title | authors/year | URL | one-line relevance;
- **Returning** structured findings (per finding: the claim, the number/date, the source filename, whether it supports or contradicts the hypothesis) — not the final report.

You then **verify** each subagent's saved output (`ls sources/`, check sizes, open a manifest) — "reported 15 sources, saved 3" has happened. If the topic involves local code/repos, survey those yourself and write `local_*.md` source notes (subagents cover the web side only, to avoid duplicate work).

### Step B4: Self-verify load-bearing facts
Any fact that becomes a commitment (version, licence, performance number, standard ID, capability boundary) gets a second targeted check by you. Mark anything unverifiable as "to be verified" in the report.

### Step B5: Write the narrative
Synthesize all findings plus your local survey into `./{topic_slug}/Deep_Research_Report.md`:
- Header: research date / method / evidence base (source count + manifest pointers);
- `## 0 Key Conclusions (TL;DR)` as numbered points;
- Body sectioned by angle, citing the saved source filenames inline so every claim is traceable;
- Conclusions/recommendations + `## References` (pointing at each `SOURCES-*.md`).
- Deliver with SendUserFile and say where the evidence base lives.

### Mode B Output Path
```
{current_working_directory}/{topic_slug}/
  ├── Deep_Research_Report.md   # narrative conclusions (cites saved source filenames)
  └── sources/                  # primary sources saved to disk
      ├── doc_*.md / *.pdf      # web extracts / downloaded PDFs
      ├── SOURCES-<angle>.md    # one manifest per angle
      └── local_*.md            # (optional) first-hand local repo survey notes
```
