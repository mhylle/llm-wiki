# Second Brain

A personal knowledge base powered by LLMs, inspired by [Andrej Karpathy's LLM Wiki pattern](https://github.com/karpathy/LLM-Wiki). Sources go in, structured wiki pages come out.

## How It Works

1. **Drop a source** into `raw/` (articles, papers, notes)
2. **Ingest** it with an LLM session — entities, concepts, and cross-references are extracted automatically
3. **Query** the wiki to synthesize answers across all ingested sources
4. **Lint** to find contradictions, orphan pages, and gaps

The schema in `CLAUDE.md` governs all LLM operations. Every wiki page follows a consistent format with frontmatter, cross-references, and source citations.

## Structure

```
raw/           # Immutable source documents
wiki/          # LLM-maintained markdown pages
  sources/     # One summary per ingested source
  entities/    # People, orgs, products
  concepts/    # Ideas, patterns, frameworks
  comparisons/ # Side-by-side analyses
  questions/   # Filed answers worth keeping
  artifacts/   # Charts, tables, other outputs
  index.md     # Full page catalog
  log.md       # Chronological operation log
  overview.md  # High-level synthesis
```

