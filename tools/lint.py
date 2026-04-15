"""Automated wiki lint: health-check and fix wiki issues.

Uses Claude Agent SDK to read wiki pages, detect issues, and apply fixes
following the LINT operation defined in CLAUDE.md.

Usage:
  python -m tools.lint              # run lint
  python -m tools.lint --report     # generate report only (no fixes)
"""

import argparse
import json
import os
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

if os.getcwd() != _PROJECT_ROOT:
    os.chdir(_PROJECT_ROOT)

os.environ["CLAUDE_INVOKED_BY"] = "secondbrain"

# Ensure stdout/stderr can handle unicode (Agent SDK may emit emojis)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from tools.config import (
    CLAUDE_MD_PATH,
    GIT_BASH_PATH,
    INDEX_FILE,
    LINT_PROMPT,
    LINT_REPORT_FILE,
    LINT_STATE_FILE,
    LOG_FILE,
    SECONDBRAIN_ROOT,
    STATE_DIR,
)

os.environ.setdefault("CLAUDE_CODE_GIT_BASH_PATH", GIT_BASH_PATH)
from tools.utils import now_iso


def load_lint_state() -> dict:
    """Load lint state from disk."""
    if not LINT_STATE_FILE.exists():
        return {"compile_count_since_lint": 0, "last_lint": None}
    return json.loads(LINT_STATE_FILE.read_text(encoding="utf-8"))


def save_lint_state(state: dict):
    """Save lint state to disk."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LINT_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def increment_compile_count():
    """Increment the compile counter (called from compile.py after each compile)."""
    state = load_lint_state()
    state["compile_count_since_lint"] = state.get("compile_count_since_lint", 0) + 1
    save_lint_state(state)
    return state["compile_count_since_lint"]


def should_auto_lint(threshold: int) -> bool:
    """Check if lint should auto-trigger based on compile count."""
    state = load_lint_state()
    return state.get("compile_count_since_lint", 0) >= threshold


def build_lint_prompt(report_only: bool = False) -> str:
    """Build the full prompt for the lint agent."""
    schema = ""
    if CLAUDE_MD_PATH.exists():
        schema = CLAUDE_MD_PATH.read_text(encoding="utf-8")

    index = ""
    if INDEX_FILE.exists():
        index = INDEX_FILE.read_text(encoding="utf-8")

    mode = "Report issues only — do NOT make any changes." if report_only else \
           "Fix issues where possible. Report issues requiring human judgment."

    return f"""{LINT_PROMPT}

Mode: {mode}

---

## Wiki Schema (CLAUDE.md)

{schema}

---

## Current Wiki Index

{index}

---

Now audit the wiki. Start by reading the index, then check pages for the issues listed above. \
Use Glob and Grep to find all wiki pages, then Read pages to check their frontmatter and content."""


def run_lint(report_only: bool = False):
    """Run the lint agent."""
    print("Running wiki lint...")
    prompt = build_lint_prompt(report_only)

    try:
        import asyncio
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage

        report_lines: list[str] = []

        async def do_lint():
            tools = ["Read", "Glob", "Grep"]
            if not report_only:
                tools.extend(["Write", "Edit"])

            async for message in query(
                prompt=prompt,
                options=ClaudeAgentOptions(
                    allowed_tools=tools,
                    permission_mode="acceptEdits",
                    max_turns=40,
                    cwd=str(SECONDBRAIN_ROOT),
                ),
            ):
                if isinstance(message, AssistantMessage):
                    content = message.content if hasattr(message, "content") else ""
                    if isinstance(content, list):
                        for block in content:
                            if hasattr(block, "text") and block.text.strip():
                                report_lines.append(block.text)
                                print(f"  [lint] {block.text[:200]}")

        asyncio.run(do_lint())

        # Save report
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        report = "\n\n".join(report_lines)
        LINT_REPORT_FILE.write_text(
            f"# Lint Report — {now_iso()}\n\n{report}",
            encoding="utf-8",
        )
        print(f"Report saved to {LINT_REPORT_FILE}")

        # Reset compile counter
        state = load_lint_state()
        state["compile_count_since_lint"] = 0
        state["last_lint"] = now_iso()
        save_lint_state(state)

        print("Lint complete.")

    except Exception as e:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        log_file = STATE_DIR / "lint.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{now_iso()}] Lint error: {e}\n")
        print(f"Lint error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Automated wiki lint")
    parser.add_argument(
        "--report", action="store_true",
        help="Generate report only, don't fix issues",
    )
    args = parser.parse_args()
    run_lint(report_only=args.report)


if __name__ == "__main__":
    main()
