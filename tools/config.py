"""Path constants and prompt templates for the secondbrain memory pipeline."""

import os
import platform
from pathlib import Path

# Auto-detect project root from this file's location
SECONDBRAIN_ROOT = Path(__file__).resolve().parent.parent

# Git-bash path for Agent SDK on Windows
if platform.system() == "Windows":
    GIT_BASH_PATH = os.environ.get(
        "CLAUDE_CODE_GIT_BASH_PATH", r"C:\Programs\Git\bin\bash.exe"
    )
else:
    GIT_BASH_PATH = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH", "/bin/bash")

# Claude session transcript locations (checked in order)
_home = Path.home()
CLAUDE_PROJECTS_DIRS = [
    _home / ".claude" / "projects",                    # native (Linux or Windows)
    Path("/mnt/c/Users") / _home.name / ".claude" / "projects",  # WSL -> Windows
]

# Directories
DAILY_DIR = SECONDBRAIN_ROOT / "daily"
WIKI_DIR = SECONDBRAIN_ROOT / "wiki"
STATE_DIR = SECONDBRAIN_ROOT / ".state"
TOOLS_DIR = SECONDBRAIN_ROOT / "tools"

# Key files
CLAUDE_MD_PATH = SECONDBRAIN_ROOT / "CLAUDE.md"
INDEX_FILE = WIKI_DIR / "index.md"
LOG_FILE = WIKI_DIR / "log.md"
OVERVIEW_FILE = WIKI_DIR / "overview.md"
STATE_FILE = STATE_DIR / "state.json"
LAST_FLUSH_FILE = STATE_DIR / "last-flush.json"

# Limits
MAX_CONTEXT_CHARS = 20_000
MAX_INDEX_CHARS = 8_000
MAX_DAILY_CHARS = 8_000
MAX_LOG_CHARS = 3_800
MAX_TRANSCRIPT_CHARS = 15_000
MAX_TRANSCRIPT_TURNS = 30
MIN_TURNS_SESSION_END = 1
MIN_TURNS_PRE_COMPACT = 5
FLUSH_DEDUP_SECONDS = 60
COMPILE_AFTER_HOUR = 18
LINT_AFTER_N_COMPILES = 3
LINT_STATE_FILE = STATE_DIR / "lint-state.json"
LINT_REPORT_FILE = STATE_DIR / "lint-report.md"

# Tier promotion thresholds
EPISODIC_PROMOTION_DAYS = 30       # Episodic pages older than this with 2+ sources → propose semantic
PROCEDURAL_MIN_CONTEXTS = 3        # Semantic pages referenced in 3+ different contexts → propose procedural
STALE_REVIEW_DAYS = 60             # Low-confidence pages with no reinforcement in this window → flag for review

# --- Prompts ---

FLUSH_PROMPT = """\
You are a knowledge extraction agent for a personal wiki (Second Brain).

You will receive an excerpt from a Claude Code conversation. Your job is to extract \
insights worth preserving. Be selective — only extract things with lasting value, \
not ephemeral troubleshooting steps.

Extract the following categories (skip any category with nothing worth noting):

## Decisions
Technical or architectural decisions made during this session. Include the reasoning.

## Patterns
Reusable patterns, techniques, or workflows discovered or applied.

## Insights
Non-obvious observations, lessons learned, or "aha" moments.

## Entities
Tools, libraries, services, people, or organizations encountered that are worth tracking. \
For each, give a one-line description.

## Concepts
Ideas, frameworks, or mental models discussed or applied.

## Questions
Open questions raised but not fully resolved, or questions that were answered in a \
non-obvious way worth preserving.

## Context
- **Project:** [project name/path if identifiable]
- **Topics:** [comma-separated topic tags]

Rules:
- Be concise. Each item should be 1-3 sentences.
- Use markdown formatting.
- If the conversation is trivial (simple file edits, routine git operations, basic \
  debugging with no novel insight), output exactly: NO_INSIGHTS and nothing else.
- Do NOT include: passwords, API keys, file paths that are just implementation details, \
  or content that only makes sense within the specific session context.
- DO include: transferable knowledge, decisions with rationale, patterns that could \
  apply to other projects.
"""

COMPILE_PREAMBLE = """\
You are the wiki compiler for the Second Brain. Your job is to process daily conversation \
logs and integrate their insights into the wiki, following the schema in CLAUDE.md exactly.

The daily logs contain conversation insights extracted from Claude Code sessions across \
various projects. Treat each daily log entry as a "source" analogous to an ingested document.

For each daily log you process:
1. Read the daily log entries.
2. For each substantive insight, decision, pattern, or entity:
   - Check if a relevant wiki page already exists (search index.md first, then grep).
   - If YES: update the existing page with the new information. Note the source as \
     "daily/YYYY-MM-DD.md" in the sources frontmatter list.
   - If NO: create a new page in the appropriate directory (concepts/, entities/, etc.).
3. Create a source summary in wiki/sources/ for the daily log itself, titled \
   "conversation-log-YYYY-MM-DD", type: source.
4. Update wiki/index.md with any new or modified pages.
5. Append an entry to wiki/log.md using the compile log format below.
6. Update wiki/overview.md only if the new material meaningfully changes the big picture.

Compile log entry format:
## [YYYY-MM-DD] compile | Daily conversation insights
- **Source:** `daily/YYYY-MM-DD.md`
- **Pages created:** [[page1]], [[page2]]
- **Pages updated:** [[page3]], [[page4]]
- **Key insight:** One-sentence summary of the most important takeaway.

CRYSTALLIZATION:
- If a daily log contains a completed research thread (question asked, evidence gathered, \
  conclusion reached), crystallize it into a standalone wiki page following the CRYSTALLIZE \
  operation in the schema. File in wiki/questions/ or wiki/concepts/ as appropriate.

IMPORTANT:
- Follow ALL frontmatter, naming, cross-referencing, and style rules from CLAUDE.md.
- Set the `confidence` frontmatter field per the Confidence Rules in the schema \
  (high: 3+ sources no contradictions, medium: 2 sources, low: 1 source or contradictions).
- Never modify files in raw/ or daily/.
- Use [[wikilinks]] for all cross-references.
- Flag contradictions with > [!warning] callouts.
- Keep pages focused. Split if too broad.
- Use sources: ["daily/YYYY-MM-DD.md"] in frontmatter for conversation-derived pages.
"""

LINT_PROMPT = """\
You are the wiki linter for the Second Brain. Your job is to audit the wiki for health \
issues and fix what you can, following the LINT operation in the schema (CLAUDE.md).

Check for:
1. Pages with missing or incorrect `confidence` scores — recalculate based on source count \
   and contradiction status.
2. Orphan pages with no inbound links from other wiki pages.
3. Missing cross-references between related pages.
4. Unresolved `[!warning] Contradiction` callouts — propose supersession if appropriate.
5. Pages with `superseded_by` set but confidence not lowered to `low`.
6. Important concepts mentioned in page bodies but lacking their own page.
7. Pages that have grown too long and should be split.
8. Broken [[wikilinks]] referencing non-existent pages.
9. Tier promotion candidates:
   - Episodic pages older than 30 days with 2+ sources → propose promotion to semantic.
   - Semantic pages describing repeatable processes used in 3+ contexts → propose promotion to procedural.
   - Low-confidence pages with no source reinforcement in 60+ days → flag for review.

For each issue found, either:
- Fix it directly (orphan links, confidence scores, broken links), OR
- Report it with a recommended action if it requires human judgment.

Output a summary report listing all issues found and actions taken.

After fixing, append a lint entry to wiki/log.md:
## [YYYY-MM-DD] lint
- **Issues found:** N
- **Issues resolved:** M
- **Summary:** Brief description of changes made.

IMPORTANT:
- Follow ALL rules from CLAUDE.md.
- Do NOT modify files in raw/ or daily/.
- Be conservative — only fix clear issues, don't reorganize.
"""
