# LLM Wiki

A personal knowledge base powered by Claude Code, inspired by [Andrej Karpathy's LLM Wiki pattern](https://github.com/karpathy/LLM-Wiki). Drop sources in, get a structured, cross-referenced wiki out.

The system uses a `CLAUDE.md` schema to govern all LLM operations. Every wiki page follows a consistent format with typed frontmatter, confidence scores, cross-references, and source citations. Knowledge is automatically captured from your Claude Code sessions and promoted through memory tiers — from raw conversation logs to permanent, reusable concepts.

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (CLI, desktop, or IDE extension)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- Python 3.12+

## Quick Start

```bash
# Clone the repo
git clone https://github.com/mhylle/llm-wiki.git
cd llm-wiki

# Run the installer
bash install.sh

# Open the project in Claude Code
claude
```

That's it. Claude reads `CLAUDE.md` on session start and knows how to operate the wiki.

## What the Installer Does

`install.sh` performs five steps:

1. **Installs Python dependencies** via `uv sync`
2. **Creates directories** (`daily/`, `.state/`)
3. **Installs global Claude Code skills** (`/ingest`, `/compile`) to `~/.claude/skills/` — these work from any project
4. **Configures hooks** in `~/.claude/settings.json` and `~/.claude/hooks.json`:
   - **SessionStart** — injects wiki index and recent activity into every Claude session
   - **SessionEnd** (Stop) — captures conversation insights when a session ends
   - **PreCompact** — captures insights before context compaction in long sessions
5. **Prints a summary** with manual steps if your config files already exist

## How It Works

### The Core Loop

```
┌─────────────────────────────────────────────────────┐
│  1. SOURCES                                         │
│     Drop articles, papers, notes into raw/          │
│                                                     │
│  2. INGEST                                          │
│     Claude reads the source, extracts entities,     │
│     concepts, and relationships, creates wiki pages │
│                                                     │
│  3. QUERY                                           │
│     Ask questions — Claude synthesizes answers      │
│     across all ingested sources with citations      │
│                                                     │
│  4. LINT                                            │
│     Audit for contradictions, orphan pages,         │
│     missing links, stale confidence scores          │
└─────────────────────────────────────────────────────┘
```

### Automatic Conversation Capture

The hooks run a background pipeline that captures knowledge from **all** your Claude Code sessions, not just wiki sessions:

```
Session ends → SessionEnd hook fires
    → Extracts conversation turns from the JSONL transcript
    → Sends to Claude Agent SDK for insight extraction
    → Appends structured insights to daily/<date>.md
    → If after 6pm, triggers compile automatically

Compile runs → Processes daily logs into wiki pages
    → Creates/updates entity, concept, and source pages
    → Rebuilds search index and knowledge graph
    → Auto-lints every 3 compiles
```

This means debugging a server issue, exploring a new library, or designing an API in any project will automatically contribute knowledge to your wiki.

### Memory Tiers

Knowledge naturally promotes through four tiers:

| Tier | Location | Lifetime | What lives here |
|------|----------|----------|-----------------|
| **Working** | `daily/*.md` | Hours | Raw session observations |
| **Episodic** | `wiki/sources/conversation-log-*.md` | Days–weeks | Compressed session summaries |
| **Semantic** | `wiki/concepts/`, `wiki/entities/` | Months–years | Cross-session facts |
| **Procedural** | `wiki/concepts/` (tagged `procedural`) | Permanent | Reusable workflows |

The lint operation proposes promotions: episodic pages older than 30 days with multiple sources get promoted to semantic; semantic pages describing processes used across 3+ contexts get promoted to procedural.

## Directory Structure

```
llm-wiki/
├── CLAUDE.md              # The schema — governs all LLM operations
├── install.sh             # One-command setup
├── raw/                   # Your source documents (immutable, never modified by LLM)
├── daily/                 # Auto-captured conversation logs
├── wiki/                  # LLM-maintained wiki pages
│   ├── index.md           # Full page catalog
│   ├── log.md             # Chronological operation log
│   ├── overview.md        # High-level synthesis
│   ├── sources/           # One summary per ingested source
│   ├── entities/          # People, organizations, products
│   ├── concepts/          # Ideas, patterns, frameworks
│   ├── comparisons/       # Side-by-side analyses
│   ├── questions/         # Filed answers worth keeping
│   └── artifacts/         # Charts, tables, other outputs
├── tools/                 # Python pipeline
│   ├── config.py          # Paths, limits, prompt templates
│   ├── flush.py           # Extract insights from conversations
│   ├── compile.py         # Process daily logs into wiki pages
│   ├── lint.py            # Wiki health checks
│   ├── ingest_session.py  # Manual session ingestion
│   ├── search_index.py    # Full-text search index builder
│   ├── graph.py           # Knowledge graph builder
│   └── hooks/             # Claude Code hook scripts
│       ├── session_start.py   # Inject wiki context
│       ├── session_end.py     # Capture on session end
│       └── pre_compact.py     # Capture before compaction
└── .claude/
    ├── settings.json      # Hook to prevent editing raw/ files
    └── commands/           # Project-scoped slash commands
        ├── ingest.md      # /ingest — capture sessions
        ├── compile.md     # /compile — build wiki pages
        ├── crystallize.md # /crystallize — distill research threads
        └── backfill-confidence.md
```

## Usage

### Capturing Sources

The `raw/` directory accepts any markdown file. You can create sources manually, but the fastest way to capture web articles is the [Obsidian Web Clipper](https://obsidian.md/clipper) browser extension. Configure it to save clipped pages directly into your `raw/` folder as markdown. One click captures a full article, ready to ingest.

Other good options:
- **Copy-paste** into a markdown file — quick and works for anything
- **Markdownload** browser extension — another web-to-markdown tool
- **PDF files** — Claude can read PDFs directly from `raw/`

### Ingesting a Source

1. Save an article, paper, or note as markdown in `raw/`:

   ```
   raw/how-transformers-work.md
   ```

2. Open Claude Code in the wiki project and tell it to ingest:

   ```
   > Ingest raw/how-transformers-work.md
   ```

3. Claude will:
   - Read the full source
   - Discuss key takeaways with you
   - Create a source summary in `wiki/sources/`
   - Create or update entity and concept pages
   - Add cross-references between all affected pages
   - Update the index and log

### Querying the Wiki

Ask any question. Claude reads the index, finds relevant pages, and synthesizes an answer with citations:

```
> What do my sources say about attention mechanisms?
```

If the answer is substantial, Claude offers to file it as a permanent page in `wiki/questions/`.

### Linting

Ask Claude to audit the wiki:

```
> Lint the wiki
```

It checks for: contradictions between pages, orphan pages with no links, missing cross-references, incorrect confidence scores, stale pages, and pages that should be split or promoted.

### Manual Session Ingestion

From any Claude Code session, capture its insights into the wiki:

```
> /ingest
```

Or ingest all unprocessed sessions:

```
> /ingest --all
```

### Compiling Daily Logs

Process accumulated conversation insights into wiki pages:

```
> /compile
```

This also runs automatically after 6pm when a session ends.

## Page Format

Every wiki page follows this structure:

```markdown
---
title: Page Title
type: source | entity | concept | comparison | question | artifact
created: 2025-01-15
updated: 2025-01-20
confidence: high | medium | low
tier: semantic
sources: [source-filename-1.md, source-filename-2.md]
tags: [relevant, tags]
relationships:
  - {target: "related-page", type: "uses"}
  - {target: "other-page", type: "extends"}
---

# Page Title

Content with [[wiki-links]] to other pages.

## See Also
- [[Related Page 1]]
- [[Related Page 2]]
```

### Confidence Scores

Every page carries a confidence level based on evidence:

| Level | Criteria |
|-------|----------|
| **high** | 3+ corroborating sources, no unresolved contradictions |
| **medium** | 2 sources, or 3+ with an unresolved contradiction |
| **low** | Single source, or any active contradictions |

### Contradiction Handling

When sources disagree, both affected pages get a warning:

```markdown
> [!warning] Contradiction
> [[source-a]] claims X, but [[source-b]] claims Y.
> **Current assessment:** [synthesis or "unresolved"]
```

When resolved, the old page gets `superseded_by` in its frontmatter and its confidence drops to `low`.

## Customization

### Changing the Schema

Edit `CLAUDE.md` to change how the wiki operates. This file is the single source of truth — Claude reads it at the start of every session. You can:

- Add new page types or directories
- Change confidence rules
- Modify the ingest, query, or lint procedures
- Adjust the style guide

### Adjusting Pipeline Behavior

Edit `tools/config.py` to change:

- `MAX_TRANSCRIPT_CHARS` / `MAX_TRANSCRIPT_TURNS` — how much conversation to capture
- `COMPILE_AFTER_HOUR` — when auto-compile triggers (default: 6pm)
- `LINT_AFTER_N_COMPILES` — how often auto-lint runs (default: every 3 compiles)
- `FLUSH_DEDUP_SECONDS` — dedup window for session captures
- Tier promotion thresholds (`EPISODIC_PROMOTION_DAYS`, `PROCEDURAL_MIN_CONTEXTS`, `STALE_REVIEW_DAYS`)

### Adding a Web Viewer

The pipeline generates `.state/search-index.json` and `.state/graph.json` on every compile. These can power a web frontend — build a static site that reads these JSON files for full-text search and interactive knowledge graph visualization.

## How It Differs from Karpathy's LLM Wiki

Karpathy's original pattern is a single `WIKI.md` file maintained by an LLM. This project extends it with:

- **Multi-file wiki** — separate pages per entity, concept, and source, with typed frontmatter
- **Automatic conversation capture** — hooks capture knowledge from all Claude Code sessions
- **Memory tiers** — working, episodic, semantic, procedural — with automated promotion
- **Confidence scoring** — evidence-based confidence levels with contradiction tracking
- **Tooling** — Python pipeline for flush, compile, lint, search index, and knowledge graph
- **Cross-referencing** — bidirectional wiki-links with typed relationships

## License

MIT
