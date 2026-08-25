# Deep-Narrative Mode · Research Playbook

Follow this after choosing **Deep-Narrative mode (B)** in `/research`. Goal: read primary sources closely and produce **traceable, checkable** narrative conclusions (evolution / distinctions / due diligence) — not a filled-in table.

## 1. Split into angles (not items)
Derive 3-5 **research angles** from the topic. Each must be answerable by evidence and capable of changing the conclusion. Candidate pool:
1. **Academic/theory** — what recent papers actually achieve, on what benchmark (arXiv/Scholar).
2. **Industry/reference implementations** — who deployed this in production, and what they reported.
3. **Standards/specs** — the relevant standard numbers, versions, and adoption relationships.
4. **Engineering/open-source landscape** — which maintained components already implement most of it (GitHub: stars + last commit). **This angle MUST start with an API sweep — see §2b.**
5. **Failure modes/criticism** — what practitioners report going wrong (forums, issues, postmortems, third-party critiques).

Bad angle: "which model should we use?" (settled by platform policy, not research). Good angle: "what accuracy does X reach on benchmark Y, and what do teams do about the residual error?"

## 2. Subagent brief (one per angle, self-contained)
Subagents do not share your context, so the brief must carry everything:
> **Overall goal**: <one sentence, including what the final report must answer>
> **Your angle**: <academic | reference implementations | standards | open-source landscape | criticism/failure modes>
> **Find**: <the concrete search surface: paper topics, official docs of candidates, maintained repos, practitioner discussions>
> **If this is the open-source angle**: **run the GitHub API topic enumeration in §2b first**, and report the query strings you used; without an enumeration you may **not** claim "no project in this field does X".
> **If this angle reads a vendor's docs**: **pull the nav tree per §2c first**, read the architecture/concepts tier before any feature page, and list the architecture pages you read.
> **Save** (mandatory) every source you rely on into `<abs>/sources/`:
>   - web pages: `doc_<slug>.md` with a `# Title` / `Source URL:` / `Access date: <YYYY-MM-DD>` header and the substantive extract you actually used (include stars/last-commit for repos);
>   - PDFs: `curl -L -o <abs>/sources/arxiv_<id>_<slug>.pdf <url>`, verified non-zero and starting with `%PDF`.
> **Manifest**: write `<abs>/sources/SOURCES-<angle>.md` — a table of local filename | title | authors/year | URL | one-line relevance, grouping primary vs secondary sources.
> **Return**: structured findings — per finding: the claim, the number/date, the source filename, whether it supports or contradicts the hypothesis. Close with "what is reusable" and "the gaps". **Do not write the final report.**

## 3. Filenames encode provenance
`doc_<slug>.md` (web), `arxiv_<id>_<slug>.pdf`, `github_<repo>.md`, `case_<org>.md`, `discussion_<topic>.md`, `local_<repo>.md` (your own first-hand survey of a local repo). Every saved page keeps its URL and access date — an undated extract is unusable a month later.

## 2b. Open-source landscape: sweep by API first, read closely second

**Web search alone systematically misses the leader of a field.** Two mechanisms:

1. GitHub repo search indexes **name / description / topics** — **not the README body** (that needs `in:readme`). Projects usually put the positioning slogan in the README and a technical phrase in the description.
2. SEO for "X alternative" is saturated by listicles and small projects optimizing for that phrase. The actual leader has no need to.

**So this angle must begin with enumeration, not sampling:**

```bash
# 1. Enumerate by capability topic (name the capability, not the vendor); run 2-4 topics
curl -s -G "https://api.github.com/search/repositories" \
  --data-urlencode 'q=topic:<topic> pushed:>YYYY-MM-DD' \
  --data 'sort=stars&order=desc&per_page=20'

# 2. Re-run the marketing phrase against the README body
curl -s -G "https://api.github.com/search/repositories" \
  --data-urlencode 'q="<positioning phrase>" in:readme' --data 'sort=stars&per_page=10'

# 3. Pull real metrics for each hit (stars/forks/licence/created/pushed/topics)
curl -s "https://api.github.com/repos/<owner>/<repo>"
```

Only then use web search — for **narrative and critique**, never to **decide the roster**.

**Discipline:**
* A **negative universal claim** ("no project has reached scale", "the field has no mature implementation") may **only** rest on an enumeration query, never on web search.
* **Record the query strings themselves in `SOURCES-*.md`.** A landscape claim is exactly as good as the query behind it — the reader must be able to re-run it.
* Treat second-hand listicles as leads only; **hit the API for every candidate**. Before writing "could not confirm", try `/repos/<owner>/<repo>` once.

> **Field evidence (2026-08)**: an ontology study's open-source angle used web search plus one listicle and concluded "as of Aug 2026 no OSS project has reached meaningful community scale in this niche". Re-checked afterwards: `topic:ontology&sort=stars` returns `semantica-agi/semantica` as the **very first hit** (10,769 stars / 1,173 forks / MIT / committed that same day). Its README opens with "The Open Source Palantir for AI Agents" — but that phrase lives only in the README body and the description contains no "Palantir", so both phrase search and web search missed it. Also missed in the same pass: `simplifaisoul/osiris` (7,925 stars) and `trustgraph-ai/trustgraph` (#2 on topic:ontology). **One API query would have prevented this.**

## 2c. Vendor technical docs: **enumerate the doc site's structure before keyword-searching it**

Keyword-searching a vendor's docs finds **feature pages**. The pages that define *what the thing is*
usually contain none of your keywords, so you will never find them that way. They tend to live in
their own small section (`architecture-center` / `concepts` / `whitepaper` / `platform overview`) —
a handful of pages, each far denser than any feature page. **Miss them and you have seen the parts
but never the blueprint.**

**Reverse the order:**

```bash
# 1. Pull the nav tree — the most reliable enumeration surface (every doc page embeds the whole nav)
curl -sL -A "$UA" "<any docs page>" | \
  python3 -c "import sys,re,html; t=re.sub(r'<script.*?</script>','',sys.stdin.read(),flags=re.S); \
              t=re.sub(r'<[^>]+>','\n',t); print(html.unescape(t))" | less
#    pick out the 'architecture / concepts / platform overview' tier — usually 5-10 pages

# 2. Read those first. Only then go back to keyword search for feature detail.
```

**Do not rely on `sitemap.xml`**: it may be **truncated**, may omit the section you need, may be split
by locale. Before trusting it, count the entries (a round number like 5000/10000 means truncation)
and grep for the target section.

**Test**: before writing "vendor X's architecture is …", confirm you have read the pages X itself
labels *architecture* or *concepts*. Inferring the blueprint from feature pages is not the same thing.

> **Field evidence (2026-08)**: a Palantir study ran **two rounds** and captured 17 product-doc pages,
> all found by feature keywords (Functions / Automate / Action types / anti-patterns …) — and **both
> rounds missed the entire `architecture-center` section**, which contains **just 7 pages**. One of
> them, *The Ontology system*, carries definition-level statements that overturned the study's core
> conclusion ("The Ontology is not a 'semantic layer'"; the Ontology's Language includes actions **and
> automations** and the literal logic defining how those actions operate). It was never found by
> search — it was stumbled upon while verifying a third party's quotation. Checked afterwards:
> `docs/sitemap.xml` returns 200 but is **truncated at 5,000 entries** and omits architecture-center
> entirely; **the nav tree listed all 7 pages in one shot.**

## 4. Verify, don't trust the report
When a subagent finishes: `ls sources/`, check file sizes, open one manifest. "Reported 15 sources, saved 3" really happens.

## 5. Self-verify load-bearing facts
Before a fact becomes a commitment — licence, version, performance/VRAM number, standard ID, API capability, regulatory requirement — check it yourself with one targeted search. Anything unverifiable is labelled "to be verified" in the report, never written up as a settled assumption.

## 5b. Quotation discipline: **a clean extraction layer does not make a clean synthesis layer**

`sources/` can be verbatim-perfect while the report still contains "quotes" that do not exist on the
page. The mechanism is **compression**: to make a claim land, you merge two sentences into one, turn
a summary into a quotation, or collapse two different axes into a single line — and the moment it
gets quotation marks, an inference is wearing the costume of evidence. Fetch tools that summarize do
the same thing: their output is **not** the source text.

**Three rules:**

1. **Anything in quotation marks must be traceable.** Every quoted span in the report must be findable
   verbatim in `sources/`. Not there → either save the source, or drop the quotation marks.
2. **Write inference as inference.** Your summary, your judgement, your characterization: **no quotation
   marks**, and say plainly that it is your inference. In particular, when a source supports "X *may*
   be Y" and you write "X *must* be Y", state explicitly that the MUST is **your** tightening and why.
3. **Watch for compression artefacts.** Merging two sentences, stitching across sections, flipping a
   negative into a positive — if quotation marks survive any of those, you have probably fabricated.
   Collapsing two distinct axes into one sentence is the most common way this happens.

**Run the mechanical check before delivering** (`quotecheck.py` ships with this skill):

```bash
python3 quotecheck.py <report.md> <sources dir>
# extracts every English quoted span from the report, matches each against sources/,
# lists the ones that do not trace, exits non-zero
```

It strips markdown emphasis, leading `>` blockquote markers and nested quote characters before
comparing — quotes routinely wrap across lines and nest, and without normalization you get nothing
but false positives. **Avoid wrapping a sentence that contains an English quotation inside another
pair of double quotes** (nested quotes shred the span).

> **Field evidence (2026-08)**: a delivered study had 19 verbatim-clean extracts in `sources/`, yet the
> mechanical check found **two "quotes" that appear nowhere on the pages** — both compression
> artefacts: one flattened the Golden Hammer selection table into "Match tool to job — ..."; the other
> merged Action Sprawl's two actual sentences ("Design action types around business operations, **not
> database updates**. Create actions that bundle related changes into meaningful workflows.") into one.
> It also exposed a third class: **quotes that were genuine but had never been saved into `sources/`**
> (quoted straight out of a transient curl buffer) — unverifiable a month later, therefore not
> evidence. One command surfaced all three.

## 6. Tier the cost
Fetching / saving / writing manifests -> subagents (haiku is fine); angles needing high-quality summarization -> sonnet subagents; cross-angle synthesis and the writing -> the main model.

## 7. Write it
`Deep_Research_Report.md`: header (date / method / evidence base count + manifest pointers) -> `## 0 Key Conclusions (TL;DR)` -> body sectioned by angle, citing saved source filenames inline -> conclusions/recommendations -> `## References` (pointing at each `SOURCES-*.md`). Deliver with SendUserFile and say where `sources/` lives.

## 8. Local repo survey (when the topic involves one)
Read the code and docs yourself and write a `local_<repo>.md` source note (subagents cover the web side only, to avoid duplicating your work). Cover: what it is, the key design constructs you actually observed (schemas, interfaces, fields), its licence, what is reusable, and where it agrees or conflicts with the approach under evaluation.
