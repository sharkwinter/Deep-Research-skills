# Deep-Narrative Mode · Research Playbook

Follow this after choosing **Deep-Narrative mode (B)** in `/research`. Goal: read primary sources closely and produce **traceable, checkable** narrative conclusions (evolution / distinctions / due diligence) — not a filled-in table.

## 1. Split into angles (not items)
Derive 3-5 **research angles** from the topic. Each must be answerable by evidence and capable of changing the conclusion. Candidate pool:
1. **Academic/theory** — what recent papers actually achieve, on what benchmark (arXiv/Scholar).
2. **Industry/reference implementations** — who deployed this in production, and what they reported.
3. **Standards/specs** — the relevant standard numbers, versions, and adoption relationships.
4. **Engineering/open-source landscape** — which maintained components already implement most of it (GitHub: stars + last commit).
5. **Failure modes/criticism** — what practitioners report going wrong (forums, issues, postmortems, third-party critiques).

Bad angle: "which model should we use?" (settled by platform policy, not research). Good angle: "what accuracy does X reach on benchmark Y, and what do teams do about the residual error?"

## 2. Subagent brief (one per angle, self-contained)
Subagents do not share your context, so the brief must carry everything:
> **Overall goal**: <one sentence, including what the final report must answer>
> **Your angle**: <academic | reference implementations | standards | open-source landscape | criticism/failure modes>
> **Find**: <the concrete search surface: paper topics, official docs of candidates, maintained repos, practitioner discussions>
> **Save** (mandatory) every source you rely on into `<abs>/sources/`:
>   - web pages: `doc_<slug>.md` with a `# Title` / `Source URL:` / `Access date: <YYYY-MM-DD>` header and the substantive extract you actually used (include stars/last-commit for repos);
>   - PDFs: `curl -L -o <abs>/sources/arxiv_<id>_<slug>.pdf <url>`, verified non-zero and starting with `%PDF`.
> **Manifest**: write `<abs>/sources/SOURCES-<angle>.md` — a table of local filename | title | authors/year | URL | one-line relevance, grouping primary vs secondary sources.
> **Return**: structured findings — per finding: the claim, the number/date, the source filename, whether it supports or contradicts the hypothesis. Close with "what is reusable" and "the gaps". **Do not write the final report.**

## 3. Filenames encode provenance
`doc_<slug>.md` (web), `arxiv_<id>_<slug>.pdf`, `github_<repo>.md`, `case_<org>.md`, `discussion_<topic>.md`, `local_<repo>.md` (your own first-hand survey of a local repo). Every saved page keeps its URL and access date — an undated extract is unusable a month later.

## 4. Verify, don't trust the report
When a subagent finishes: `ls sources/`, check file sizes, open one manifest. "Reported 15 sources, saved 3" really happens.

## 5. Self-verify load-bearing facts
Before a fact becomes a commitment — licence, version, performance/VRAM number, standard ID, API capability, regulatory requirement — check it yourself with one targeted search. Anything unverifiable is labelled "to be verified" in the report, never written up as a settled assumption.

## 6. Tier the cost
Fetching / saving / writing manifests -> subagents (haiku is fine); angles needing high-quality summarization -> sonnet subagents; cross-angle synthesis and the writing -> the main model.

## 7. Write it
`Deep_Research_Report.md`: header (date / method / evidence base count + manifest pointers) -> `## 0 Key Conclusions (TL;DR)` -> body sectioned by angle, citing saved source filenames inline -> conclusions/recommendations -> `## References` (pointing at each `SOURCES-*.md`). Deliver with SendUserFile and say where `sources/` lives.

## 8. Local repo survey (when the topic involves one)
Read the code and docs yourself and write a `local_<repo>.md` source note (subagents cover the web side only, to avoid duplicating your work). Cover: what it is, the key design constructs you actually observed (schemas, interfaces, fields), its licence, what is reusable, and where it agrees or conflicts with the approach under evaluation.
