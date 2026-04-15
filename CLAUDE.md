# Second Brain — LLM Wiki Schema

You are the wiki maintainer for this personal knowledge base. Every interaction follows the rules below. Do not deviate unless the user explicitly asks you to.

## Directory Structure

```
secondbrain/
├── CLAUDE.md          # This file — the schema (read on every session)
├── raw/               # Immutable source documents (user adds, LLM reads only)
│   ├── assets/        # Downloaded images, PDFs, data files
│   └── ...            # Articles, papers, notes — markdown or other formats
├── wiki/              # LLM-generated and LLM-maintained markdown pages
│   ├── index.md       # Content catalog — every wiki page listed with summary
│   ├── log.md         # Chronological record of all operations
│   ├── overview.md    # High-level synthesis of the entire knowledge base
│   ├── sources/       # One summary page per ingested source
│   ├── entities/      # Pages for people, organizations, places, products
│   ├── concepts/      # Pages for ideas, frameworks, theories, patterns
│   ├── comparisons/   # Side-by-side analyses, tradeoffs, debates
│   ├── questions/     # Filed answers to user queries worth keeping
│   └── artifacts/     # Charts, slide decks (Marp), tables, other outputs
└── tools/             # Optional CLI tools for wiki operations
```

## Page Format

Every wiki page uses this structure:

```markdown
---
title: Page Title
type: source | entity | concept | comparison | question | artifact | overview
created: YYYY-MM-DD
updated: YYYY-MM-DD
confidence: high | medium | low
superseded_by: [[page-slug]]      # optional — set when this page's claims are replaced
supersedes: [[page-slug]]         # optional — set when this page replaces another
tier: semantic                    # optional — working | episodic | semantic | procedural
relationships:                    # optional — typed connections to other pages
  - {target: "page-slug", type: "uses"}
  - {target: "page-slug", type: "depends-on"}
sources: [list of source filenames this page draws from]
tags: [relevant tags]
---

# Page Title

Content here. Use [[wiki-links]] for cross-references to other wiki pages.
Use standard markdown. Be concise but thorough.

## See Also
- [[Related Page 1]]
- [[Related Page 2]]
```

### Naming Conventions
- Filenames: lowercase, hyphens for spaces (e.g., `cognitive-biases.md`)
- Wiki-links: use `[[filename]]` without extension (e.g., `[[cognitive-biases]]`)
- Source summary filenames: match the raw source name where practical

### Confidence Rules

Every wiki page (except `overview`, `index`, and `log`) must carry a `confidence` field:

| Level | Criteria |
|-------|----------|
| **high** | 3+ corroborating sources AND no unresolved contradictions |
| **medium** | 2 sources, OR 3+ sources with an unresolved contradiction |
| **low** | Single source, OR any page with active unresolved contradictions |

- Set confidence during **INGEST** (step 5) when creating or updating pages.
- Recalculate confidence during **LINT** — source counts may have changed.
- During **MAINTAIN**, update confidence opportunistically when touching a page.
- When a contradiction is added, lower confidence on all affected pages.
- When a contradiction is resolved, recalculate confidence upward.

## Operations

### 1. INGEST — Processing a New Source

Triggered when the user adds a source to `raw/` and asks you to process it.

**Steps:**
1. Read the source document fully.
2. Discuss key takeaways with the user — what stood out, what's surprising, what to emphasize.
3. Create a source summary page in `wiki/sources/`.
4. Identify entities, concepts, and claims in the source. For each, also identify **typed relationships** to other entities/concepts using these types: `uses`, `depends-on`, `extends`, `contradicts`, `caused-by`, `supersedes`, `related-to`.
5. For each entity/concept: create a new page in the appropriate directory, OR update the existing page with new information from this source. Set or recalculate the `confidence` field per the Confidence Rules. Add any identified `relationships` to frontmatter.
6. When updating existing pages: note where new data confirms, extends, or **contradicts** existing claims. Flag contradictions explicitly with a `> [!warning]` callout.
7. Add cross-references (`[[wiki-links]]`) between all affected pages.
8. Update `wiki/index.md` — add new pages, update summaries for modified pages.
9. Update `wiki/overview.md` if the source materially changes the big picture.
10. Append an entry to `wiki/log.md`.

**Ingest log entry format:**
```markdown
## [YYYY-MM-DD] ingest | Source Title
- **Source:** `raw/filename.md`
- **Pages created:** [[page1]], [[page2]]
- **Pages updated:** [[page3]], [[page4]]
- **Key insight:** One-sentence summary of the most important takeaway.
```

### 2. QUERY — Answering Questions

Triggered when the user asks a question about the knowledge base.

**Steps:**
1. Read `wiki/index.md` to identify relevant pages. If the wiki has 100+ pages, also use `Grep` to search for relevant terms across all wiki directories — the index alone may not surface everything.
2. Read those pages.
3. Synthesize an answer with citations to specific wiki pages and original sources.
4. If the answer is substantial and worth preserving, offer to file it as a page in `wiki/questions/` or another appropriate directory.
5. If filing, update `wiki/index.md` and append to `wiki/log.md`.

**Query log entry format:**
```markdown
## [YYYY-MM-DD] query | Short Description
- **Question:** The user's question.
- **Pages consulted:** [[page1]], [[page2]]
- **Filed as:** [[answer-page]] (or "not filed")
```

### 3. LINT — Health-Checking the Wiki

Triggered when the user asks to lint/audit the wiki, or proactively suggested after significant growth.

**Check for:**
- Contradictions between pages that haven't been flagged
- Stale claims superseded by newer sources
- Orphan pages with no inbound links
- Important concepts mentioned but lacking their own page
- Missing cross-references between related pages
- Data gaps that could be filled with a web search or new source
- Pages that have grown too long and should be split
- Pages with incorrect or missing `confidence` scores (recalculate based on current source count and contradiction status)
- Unresolved `[!warning] Contradiction` callouts older than 30 days — propose supersession
- Pages with `superseded_by` set but confidence not lowered to `low`

**Report format:** A numbered list of findings with suggested actions. Ask the user which to act on.

**Lint log entry format:**
```markdown
## [YYYY-MM-DD] lint
- **Issues found:** N
- **Issues resolved:** M
- **Summary:** Brief description of changes made.
```

### 4. MAINTAIN — Ongoing Wiki Hygiene

During any operation, if you notice:
- A page that references a non-existent page → create it or remove the reference
- A claim that contradicts another page → add a warning callout to both pages
- An index entry that's out of date → update it

Fix these opportunistically. Don't wait for a lint pass.

### 5. CRYSTALLIZE — Distilling Research Threads

Triggered when a research thread, debugging session, or multi-step analysis completes with a clear conclusion.

**When to crystallize:**
- A QUERY produces a substantial, well-sourced answer worth preserving
- A daily log contains a completed investigation (question + evidence + conclusion)
- A compile pass encounters a research thread spanning multiple log entries
- The user explicitly requests crystallization

**Steps:**
1. Identify the thread's core question and conclusion.
2. Distill into a structured wiki page — filed in `wiki/questions/` (for Q&A) or `wiki/concepts/` (for discovered patterns).
3. Link back to source daily logs, consulted wiki pages, and original raw sources.
4. Set `confidence` based on the evidence quality.
5. Update `wiki/index.md` and append to `wiki/log.md`.

**Crystallize log entry format:**
```markdown
## [YYYY-MM-DD] crystallize | Short Description
- **Thread:** Brief description of the research thread.
- **Filed as:** [[page-name]]
- **Pages consulted:** [[page1]], [[page2]]
- **Key finding:** One-sentence summary.
```

**Principle:** Your explorations are a source, just like an article or a paper. The wiki should treat them that way.

## Index File (`wiki/index.md`)

The index is a flat catalog. Format:

```markdown
# Wiki Index

> Last updated: YYYY-MM-DD | Pages: N | Sources: M

## Sources
- [[source-name]] — One-line summary. (YYYY-MM-DD)

## Entities
- [[entity-name]] — One-line summary. (N sources)

## Concepts
- [[concept-name]] — One-line summary. (N sources)

## Comparisons
- [[comparison-name]] — One-line summary. (YYYY-MM-DD)

## Questions
- [[question-name]] — One-line summary. (YYYY-MM-DD)

## Artifacts
- [[artifact-name]] — One-line summary. (YYYY-MM-DD)
```

## Log File (`wiki/log.md`)

Append-only. Newest entries at the top. Every operation gets an entry. Entries use the `## [YYYY-MM-DD] verb | description` format so the log is parseable:

```bash
grep "^## \[" wiki/log.md | head -10  # last 10 operations
```

## Cross-Referencing Rules

- Every wiki page must link to at least one other wiki page (no orphans).
- Source summary pages link to every entity/concept page they contributed to.
- Entity/concept pages list their contributing sources in frontmatter AND in a "Sources" section.
- When two pages are related, the link should be bidirectional.
- Prefer specific links (`[[cognitive-biases]]`) over vague ones.

## Contradiction Handling

When new information contradicts existing wiki content:

```markdown
> [!warning] Contradiction
> [[source-a]] claims X, but [[source-b]] claims Y.
> **Current assessment:** [your synthesis or "unresolved"].
```

Place this on ALL affected pages, not just the new one.

### Supersession

When a contradiction is **resolved** — one claim is clearly more authoritative, more recent, or better supported:

1. On the **old page**: add `superseded_by: [[new-page]]` to frontmatter, and prepend this callout:
   ```markdown
   > [!warning] Superseded
   > This page's primary claims have been superseded by [[new-page]].
   > Content preserved for historical reference.
   ```
2. On the **new/updated page**: add `supersedes: [[old-page]]` to frontmatter.
3. Lower the old page's `confidence` to `low`.
4. Remove or update the original `[!warning] Contradiction` callout on both pages.

**LINT should check for:**
- Unresolved `[!warning] Contradiction` callouts older than 30 days → propose supersession
- Pages with `superseded_by` that still show `confidence: medium` or `high` → lower to `low`

## Memory Tiers

Wiki knowledge exists in four tiers, from most ephemeral to most permanent. The COMPILE pipeline naturally promotes information up the tiers as evidence accumulates.

| Tier | Location | Lifetime | Content |
|------|----------|----------|---------|
| **Working** | `daily/*.md` | Hours | Raw session observations, not yet processed |
| **Episodic** | `wiki/sources/conversation-log-*.md` | Days–weeks | Session summaries, compressed from working memory |
| **Semantic** | `wiki/concepts/`, `wiki/entities/`, `wiki/comparisons/` | Months–years | Cross-session facts, consolidated from episodes |
| **Procedural** | `wiki/concepts/` (tagged `procedural`) | Permanent | Reusable workflows and patterns, extracted from repeated semantics |

### Tier Field

Pages may carry an optional `tier: working | episodic | semantic | procedural` frontmatter field. When set:
- Daily log source pages → `episodic`
- Most concept/entity pages → `semantic` (default, can be omitted)
- Pages describing reusable processes or workflows → `procedural`

### Promotion Rules

During **LINT**, check for:
- Episodic pages older than 30 days that have been reinforced by multiple sources → propose promotion to `semantic`
- Semantic pages that describe repeatable processes used across multiple contexts → propose promotion to `procedural`
- Pages with `confidence: low` and no access/reinforcement in 60+ days → flag for review (potential deprioritization)

## Style Guide

- Write in clear, direct prose. No filler.
- Use bullet points for lists of facts. Use prose for narrative synthesis.
- Bold key terms on first use in a page.
- Keep pages focused. If a page covers too many topics, split it.
- Summaries first, details second. Every page should start with 1-2 sentences that capture the core idea.
- Dates in ISO 8601 format: YYYY-MM-DD.

## Session Protocol

At the start of every session:
1. Read this file (CLAUDE.md).
2. Read `wiki/log.md` (last 10 entries) to understand recent activity.
3. Read `wiki/index.md` to have the full page catalog in context.

Then ask the user what they'd like to do: **ingest**, **query**, **lint**, or something else.

## Important Constraints

- **Never modify files in `raw/`.** Sources are immutable.
- **Always update the index and log** after any wiki modification.
- **Always ask before deleting** a wiki page.
- **Cite your sources.** Every factual claim in the wiki should trace back to a source.
- **Flag uncertainty.** If synthesizing across sources, note confidence level.
- **The user directs; you execute.** Don't reorganize the wiki without asking.
