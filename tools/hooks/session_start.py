"""SessionStart hook: inject wiki context into Claude Code sessions.

Pure local I/O — no API calls. Must complete in under 1 second.
Outputs JSON to stdout with additionalContext for Claude Code to inject.
"""

import json
import sys
from pathlib import Path

# Auto-detect project root from this file's location
SECONDBRAIN_ROOT = Path(__file__).resolve().parent.parent.parent
INDEX_FILE = SECONDBRAIN_ROOT / "wiki" / "index.md"
LOG_FILE = SECONDBRAIN_ROOT / "wiki" / "log.md"
DAILY_DIR = SECONDBRAIN_ROOT / "daily"

MAX_TOTAL = 20_000
MAX_INDEX = 8_000
MAX_DAILY = 8_000
MAX_LOG = 3_800


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit("\n", 1)[0]
    remaining = text[len(cut):].count("\n")
    return cut + f"\n\n... (truncated, {remaining} more lines)"


def read_file(path: Path, limit: int) -> str:
    if not path.exists():
        return ""
    try:
        return truncate(path.read_text(encoding="utf-8"), limit)
    except Exception:
        return ""


def most_recent_daily() -> str:
    """Read the most recent daily log file."""
    if not DAILY_DIR.exists():
        return ""
    files = sorted(DAILY_DIR.glob("*.md"), reverse=True)
    for f in files[:2]:  # today or yesterday
        content = read_file(f, MAX_DAILY)
        if content.strip():
            return f"### Recent Conversations ({f.stem})\n\n{content}"
    return ""


def recent_log_entries() -> str:
    """Read the last few wiki log entries."""
    if not LOG_FILE.exists():
        return ""
    try:
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
        # Find the last 5 operation headers (## [date] verb | desc)
        headers = [i for i, l in enumerate(lines) if l.startswith("## [")]
        if not headers:
            return ""
        start = headers[max(0, len(headers) - 5)]
        content = "\n".join(lines[start:])
        return truncate(content, MAX_LOG)
    except Exception:
        return ""


def main():
    # Read stdin (hook input) — we don't need it but must consume it
    try:
        sys.stdin.read()
    except Exception:
        pass

    index = read_file(INDEX_FILE, MAX_INDEX)
    daily = most_recent_daily()
    log = recent_log_entries()

    parts = ["## Secondbrain Wiki Context\n"]
    if index:
        parts.append(f"### Wiki Index\n\n{index}")
    if daily:
        parts.append(daily)
    if log:
        parts.append(f"### Recent Operations\n\n{log}")

    context = "\n\n".join(parts)
    context = truncate(context, MAX_TOTAL)

    output = {"hookSpecificOutput": {"additionalContext": context}}
    print(json.dumps(output))


if __name__ == "__main__":
    main()
