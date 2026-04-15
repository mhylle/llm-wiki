"""Bulk-ingest all existing Claude Code sessions into the secondbrain daily log.

Finds all JSONL transcripts across all projects, processes each one, and
optionally runs compile at the end.

Usage:
  python -m tools.init                    # Process all sessions
  python -m tools.init --dry-run          # Show what would be processed
  python -m tools.init --compile          # Also run compile after flushing
  python -m tools.init --project <slug>   # Only process one project folder
  python -m tools.init --min-turns 5      # Skip short sessions (default: 3)
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

os.environ["CLAUDE_INVOKED_BY"] = "secondbrain"

from tools.config import GIT_BASH_PATH

os.environ.setdefault("CLAUDE_CODE_GIT_BASH_PATH", GIT_BASH_PATH)

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


def discover_all_transcripts(project_filter: str = None) -> list[dict]:
    """Find all JSONL transcripts across all projects.

    Returns list of dicts with: path, project_slug, session_id, modified, size
    """
    results = []

    if not CLAUDE_PROJECTS_DIR.exists():
        return results

    for project_dir in sorted(CLAUDE_PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir():
            continue
        if project_filter and project_filter not in project_dir.name:
            continue

        for jsonl_file in project_dir.glob("*.jsonl"):
            stat = jsonl_file.stat()
            results.append({
                "path": jsonl_file,
                "project_slug": project_dir.name,
                "session_id": jsonl_file.stem,
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "size": stat.st_size,
            })

    # Sort by modification time (oldest first)
    results.sort(key=lambda x: x["modified"])
    return results


def count_turns_fast(path: Path) -> int:
    """Quick turn count without full parsing."""
    count = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if '"type":"user"' in line or '"type":"assistant"' in line:
                    count += 1
    except Exception:
        pass
    return count


def main():
    parser = argparse.ArgumentParser(description="Bulk-ingest all Claude Code sessions")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")
    parser.add_argument("--compile", action="store_true", help="Run compile after flushing")
    parser.add_argument("--project", type=str, help="Only process matching project folder")
    parser.add_argument("--min-turns", type=int, default=3, help="Minimum turns to process (default: 3)")
    parser.add_argument("--skip-flushed", action="store_true", default=True,
                        help="Skip sessions already in daily logs (default: true)")
    args = parser.parse_args()

    print("Discovering transcripts...")
    transcripts = discover_all_transcripts(args.project)
    print(f"Found {len(transcripts)} transcripts across {len(set(t['project_slug'] for t in transcripts))} projects")

    # Filter by turn count
    eligible = []
    skipped_short = 0
    for t in transcripts:
        turns = count_turns_fast(t["path"])
        t["turns"] = turns
        if turns < args.min_turns:
            skipped_short += 1
            continue
        eligible.append(t)

    print(f"Eligible: {len(eligible)} (skipped {skipped_short} with <{args.min_turns} turns)")

    if args.dry_run:
        print("\n--- DRY RUN ---")
        by_project = {}
        for t in eligible:
            by_project.setdefault(t["project_slug"], []).append(t)

        for slug, sessions in sorted(by_project.items()):
            print(f"\n{slug} ({len(sessions)} sessions):")
            for s in sessions:
                date = s["modified"].strftime("%Y-%m-%d %H:%M")
                size_kb = s["size"] / 1024
                print(f"  {date} | {s['turns']:>4} turns | {size_kb:>6.0f}KB | {s['session_id'][:8]}...")
        print(f"\nTotal: {len(eligible)} sessions to process")
        return

    # Process each transcript
    from tools.ingest_session import run_flush

    flushed = 0
    failed = 0
    no_insights = 0

    for i, t in enumerate(eligible, 1):
        date = t["modified"].strftime("%Y-%m-%d %H:%M")
        print(f"\n[{i}/{len(eligible)}] {t['project_slug']} | {date} | {t['turns']} turns")
        try:
            result = run_flush(t["path"])
            if result:
                flushed += 1
            else:
                no_insights += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

    print(f"\n--- Summary ---")
    print(f"Flushed: {flushed}")
    print(f"No insights: {no_insights}")
    print(f"Failed: {failed}")

    if args.compile and flushed > 0:
        print("\nRunning compile...")
        from tools.compile import main as compile_main
        sys.argv = ["compile"]  # Reset argv for argparse
        compile_main()


if __name__ == "__main__":
    main()
