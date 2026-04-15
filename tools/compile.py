"""Compile pipeline: process daily logs into wiki pages following CLAUDE.md schema.

Uses Claude Agent SDK with file tools to create/update wiki pages.
Incremental: only processes daily logs that changed since last compile (SHA-256 tracking).

Usage:
  python -m tools.compile           # compile changed daily logs
  python -m tools.compile --all     # recompile all daily logs
  python -m tools.compile --file daily/2026-04-07.md  # compile specific file
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path for imports
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Also ensure we can be invoked as `python -m tools.compile` from any directory
if os.getcwd() != _PROJECT_ROOT:
    os.chdir(_PROJECT_ROOT)

# Recursion guard
os.environ["CLAUDE_INVOKED_BY"] = "secondbrain"

# Ensure stdout/stderr can handle unicode (Agent SDK may emit emojis)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from tools.config import (
    CLAUDE_MD_PATH,
    COMPILE_PREAMBLE,
    DAILY_DIR,
    GIT_BASH_PATH,
    INDEX_FILE,
    LINT_AFTER_N_COMPILES,
    SECONDBRAIN_ROOT,
    STATE_DIR,
)

# Ensure Agent SDK can find git-bash on Windows
os.environ.setdefault("CLAUDE_CODE_GIT_BASH_PATH", GIT_BASH_PATH)
from tools.utils import load_state, now_iso, save_state, sha256_file


def get_changed_daily_files(state: dict) -> list[Path]:
    """Find daily log files that have changed since last compilation."""
    if not DAILY_DIR.exists():
        return []

    changed = []
    hashes = state.get("daily_hashes", {})

    for f in sorted(DAILY_DIR.glob("*.md")):
        if f.name == ".gitkeep":
            continue
        current_hash = sha256_file(f)
        if hashes.get(f.stem) != current_hash:
            changed.append(f)

    return changed


def build_compile_prompt(daily_files: list[Path]) -> str:
    """Build the full prompt for the compile agent."""
    # Read CLAUDE.md schema
    schema = ""
    if CLAUDE_MD_PATH.exists():
        schema = CLAUDE_MD_PATH.read_text(encoding="utf-8")

    # Read current index for context
    index = ""
    if INDEX_FILE.exists():
        index = INDEX_FILE.read_text(encoding="utf-8")

    # Read daily log contents
    daily_contents = []
    for f in daily_files:
        content = f.read_text(encoding="utf-8")
        daily_contents.append(f"### {f.name}\n\n{content}")

    daily_text = "\n\n---\n\n".join(daily_contents)

    prompt = f"""{COMPILE_PREAMBLE}

---

## Wiki Schema (CLAUDE.md)

{schema}

---

## Current Wiki Index

{index}

---

## Daily Logs to Compile

{daily_text}

---

Now process these daily logs. Create/update wiki pages following the schema exactly. \
Start by reading the daily logs above, then check existing wiki pages for overlap, \
and proceed with creating or updating pages as needed."""

    return prompt


def compile(daily_files: list[Path]):
    """Run the compile agent on the given daily files."""
    if not daily_files:
        print("No daily logs to compile.")
        return

    state = load_state()
    state["compile_in_progress"] = True
    save_state(state)

    print(f"Compiling {len(daily_files)} daily log(s)...")
    for f in daily_files:
        print(f"  - {f.name}")

    prompt = build_compile_prompt(daily_files)

    try:
        import asyncio
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage

        async def run_compile():
            async for message in query(
                prompt=prompt,
                options=ClaudeAgentOptions(
                    allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
                    permission_mode="acceptEdits",
                    max_turns=30,
                    cwd=str(SECONDBRAIN_ROOT),
                ),
            ):
                if isinstance(message, AssistantMessage):
                    content = message.content if hasattr(message, "content") else ""
                    if isinstance(content, list):
                        for block in content:
                            if hasattr(block, "text") and block.text.strip():
                                print(f"  [compile] {block.text[:200]}")

        asyncio.run(run_compile())

        # Update state with new hashes
        state = load_state()
        for f in daily_files:
            state.setdefault("daily_hashes", {})[f.stem] = sha256_file(f)
        state["last_compile"] = now_iso()
        state["compile_in_progress"] = False
        save_state(state)

        print("Compile complete.")

        # Rebuild search index
        from tools.search_index import build_search_index
        import json as _json
        idx = build_search_index()
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / "search-index.json").write_text(_json.dumps(idx), encoding="utf-8")
        print(f"Search index rebuilt: {len(idx)} pages")

        # Rebuild knowledge graph
        from tools.graph import build_graph
        graph = build_graph()
        (STATE_DIR / "graph.json").write_text(_json.dumps(graph), encoding="utf-8")
        print(f"Knowledge graph rebuilt: {graph['nodeCount']} nodes, {graph['edgeCount']} edges")

        # Auto-lint check
        from tools.lint import increment_compile_count, should_auto_lint, run_lint
        count = increment_compile_count()
        if should_auto_lint(LINT_AFTER_N_COMPILES):
            print(f"Auto-lint triggered (after {count} compiles)...")
            run_lint()

    except Exception as e:
        state = load_state()
        state["compile_in_progress"] = False
        save_state(state)

        # Log error
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        log_file = STATE_DIR / "compile.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{now_iso()}] Compile error: {e}\n")
        print(f"Compile error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Compile daily logs into wiki pages")
    parser.add_argument("--all", action="store_true", help="Recompile all daily logs")
    parser.add_argument("--file", type=str, help="Compile a specific daily log file")
    parser.add_argument("--lint", action="store_true", help="Run lint after compile")
    args = parser.parse_args()

    if args.file:
        path = Path(args.file)
        if not path.is_absolute():
            path = SECONDBRAIN_ROOT / path
        if not path.exists():
            print(f"File not found: {path}", file=sys.stderr)
            sys.exit(1)
        compile([path])
    elif args.all:
        all_files = sorted(DAILY_DIR.glob("*.md"))
        all_files = [f for f in all_files if f.name != ".gitkeep"]
        compile(all_files)
    else:
        state = load_state()
        changed = get_changed_daily_files(state)
        compile(changed)

    if args.lint:
        from tools.lint import run_lint
        print("Running post-compile lint...")
        run_lint()


if __name__ == "__main__":
    main()
