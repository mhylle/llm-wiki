"""Ingest a Claude Code session into the secondbrain daily log.

Auto-detects the current session transcript across Windows, Linux, and WSL.
Works from any Claude Code session via: /ingest
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

os.environ["CLAUDE_INVOKED_BY"] = "secondbrain"

from tools.config import GIT_BASH_PATH, CLAUDE_PROJECTS_DIRS, STATE_DIR

os.environ.setdefault("CLAUDE_CODE_GIT_BASH_PATH", GIT_BASH_PATH)

INGESTED_FILE = STATE_DIR / "ingested.json"


def load_ingested() -> set[str]:
    """Load set of already-ingested session IDs."""
    if not INGESTED_FILE.exists():
        return set()
    import json
    data = json.loads(INGESTED_FILE.read_text(encoding="utf-8"))
    return set(data.get("sessions", []))


def mark_ingested(session_id: str):
    """Mark a session as ingested."""
    import json
    ingested = load_ingested()
    ingested.add(session_id)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    INGESTED_FILE.write_text(
        json.dumps({"sessions": sorted(ingested)}, indent=2),
        encoding="utf-8",
    )


def cwd_to_slugs(cwd: str) -> list[str]:
    """Convert a working directory to possible Claude project folder slugs.

    Generates multiple candidates to handle Windows, Linux, and WSL paths.
    Examples:
      C:\\projects\\foo       -> ["C--projects-foo"]
      /home/user/projects/foo -> ["home-user-projects-foo", "-home-user-projects-foo"]
      /mnt/c/projects/foo     -> ["C--projects-foo", "mnt-c-projects-foo"]
    """
    slugs = []
    cwd = cwd.rstrip("/\\")

    # Windows-style path: C:\projects\foo -> C--projects-foo
    win_cwd = cwd.replace("/", "\\")
    if len(win_cwd) >= 2 and win_cwd[1] == ":":
        slugs.append(win_cwd[0] + "--" + win_cwd[3:].replace("\\", "-"))

    # WSL /mnt/c/ path -> Windows slug
    if cwd.startswith("/mnt/") and len(cwd) > 6:
        drive = cwd[5].upper()
        rest = cwd[7:] if len(cwd) > 7 else ""
        slugs.append(drive + "--" + rest.replace("/", "-"))

    # Linux-style: /home/user/foo -> -home-user-foo
    # Claude Code replaces / with - and _ with -, and keeps the leading -
    unix_cwd = cwd.replace("\\", "/")
    slug = unix_cwd.replace("/", "-").replace("_", "-")
    slugs.append(slug)
    # Also try without leading dash for older formats
    slugs.append(slug.lstrip("-"))

    return slugs


def _find_project_dir(slugs: list[str]) -> Path | None:
    """Search all Claude project directories for a matching project folder."""
    for projects_dir in CLAUDE_PROJECTS_DIRS:
        if not projects_dir.exists():
            continue
        for slug in slugs:
            # Exact match
            candidate = projects_dir / slug
            if candidate.exists():
                return candidate
            # Partial match (handles path suffix variations)
            for d in projects_dir.iterdir():
                if d.is_dir() and slug in d.name:
                    return d
    return None


def _get_project_transcripts(cwd: str = None) -> list[Path]:
    """Get all transcript files for a project, newest first."""
    if cwd is None:
        cwd = os.getcwd()

    slugs = cwd_to_slugs(cwd)
    project_dir = _find_project_dir(slugs)

    if not project_dir:
        return []

    return sorted(
        project_dir.glob("*.jsonl"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )


def find_transcript(cwd: str = None) -> Path | None:
    """Find the most recent transcript for the given or current working directory."""
    files = _get_project_transcripts(cwd)
    return files[0] if files else None


def find_all_transcripts(cwd: str = None) -> list[Path]:
    """Find all unprocessed transcripts for the given or current working directory."""
    ingested = load_ingested()
    return [f for f in _get_project_transcripts(cwd) if f.stem not in ingested]


def project_name_from_cwd(cwd: str) -> str:
    """Extract a short project name from a working directory path."""
    return Path(cwd).name


def run_flush(transcript_path: Path, project: str = ""):
    """Run the flush pipeline on a transcript."""
    from tools.hooks.session_end import extract_turns, count_turns
    from tools.config import STATE_DIR

    path_str = str(transcript_path)
    turn_count = count_turns(path_str)

    if turn_count < 3:
        print(f"  Skipping — only {turn_count} turns (minimum 3)")
        return False

    content = extract_turns(path_str)
    if not content.strip():
        print("  Skipping — no extractable content")
        return False

    print(f"  Extracted {turn_count} turns, {len(content)} chars")

    # Write temp file
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    import tempfile
    temp_fd, temp_path = tempfile.mkstemp(suffix=".md", prefix="flush-", dir=str(STATE_DIR))
    with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
        f.write(content)

    # Run flush inline (not as background process since we want to see output)
    from tools.flush import flush_to_daily, save_last_flush, should_skip_flush
    from tools.utils import now_iso
    from tools.config import FLUSH_PROMPT

    session_id = transcript_path.stem

    if should_skip_flush(session_id):
        Path(temp_path).unlink(missing_ok=True)
        print("  Skipping — already flushed recently")
        return False

    conversation = Path(temp_path).read_text(encoding="utf-8")
    Path(temp_path).unlink(missing_ok=True)

    # Call Agent SDK
    import asyncio
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage

    prompt = f"{FLUSH_PROMPT}\n\n---\n\n## Conversation Excerpt\n\n{conversation}"

    print(f"  Sending {len(prompt)} chars to Agent SDK...")

    async def run_query():
        text_parts = []
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=[],
                max_turns=2,
                permission_mode="bypassPermissions",
            ),
        ):
            if isinstance(message, AssistantMessage):
                msg_content = message.content if hasattr(message, "content") else ""
                if isinstance(msg_content, list):
                    for block in msg_content:
                        if hasattr(block, "text"):
                            text_parts.append(block.text)
                elif isinstance(msg_content, str):
                    text_parts.append(msg_content)
        return "\n".join(text_parts)

    try:
        response_text = asyncio.run(
            asyncio.wait_for(run_query(), timeout=120)
        ).strip()
    except asyncio.TimeoutError:
        print("  ERROR: Agent SDK timed out after 120s", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  ERROR: Agent SDK failed: {e}", file=sys.stderr)
        return False

    if not response_text or response_text.strip() == "NO_INSIGHTS":
        save_last_flush({"session_id": session_id, "timestamp": now_iso(), "result": "no_insights"})
        mark_ingested(session_id)
        print("  No insights worth saving")
        return False

    daily_file = flush_to_daily(response_text, project=project)
    save_last_flush({"session_id": session_id, "timestamp": now_iso(), "result": "flushed"})
    mark_ingested(session_id)
    print(f"  Flushed to {daily_file.name}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Ingest a Claude Code session into secondbrain")
    parser.add_argument("--transcript", type=str, help="Explicit transcript path")
    parser.add_argument("--cwd", type=str, help="Project working directory (auto-detects transcript)")
    parser.add_argument("--all", action="store_true", help="Ingest all unprocessed sessions for the project")
    args = parser.parse_args()

    cwd = args.cwd or os.getcwd()
    project = project_name_from_cwd(cwd)

    if args.transcript:
        transcript = Path(args.transcript)
        if not transcript.exists():
            print(f"Transcript not found: {transcript}", file=sys.stderr)
            sys.exit(1)
        print(f"Ingesting: {transcript.name} (project: {project})")
        run_flush(transcript, project=project)

    elif args.all:
        transcripts = find_all_transcripts(cwd)
        if not transcripts:
            print(f"No unprocessed sessions found for: {cwd}")
            return
        print(f"Found {len(transcripts)} unprocessed session(s) for {project}")
        for i, transcript in enumerate(transcripts, 1):
            print(f"\n[{i}/{len(transcripts)}] {transcript.name}")
            run_flush(transcript, project=project)
        print(f"\nDone — processed {len(transcripts)} session(s)")

    else:
        print(f"Finding transcript for: {cwd}")
        transcript = find_transcript(cwd)
        if not transcript:
            print(f"No transcript found for this project", file=sys.stderr)
            sys.exit(1)
        print(f"Ingesting: {transcript.name} (project: {project})")
        run_flush(transcript, project=project)


if __name__ == "__main__":
    main()
