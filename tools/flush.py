"""Flush pipeline: extract insights from conversation and append to daily log.

Runs as a detached background process spawned by session_end or pre_compact hooks.
Uses Claude Agent SDK to decide what's worth saving. No tools — text-only extraction.

Usage: python flush.py <temp_file_path> [session_id]
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path for imports
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Recursion guard — must be set before any SDK imports
os.environ["CLAUDE_INVOKED_BY"] = "secondbrain"

from tools.config import (
    COMPILE_AFTER_HOUR,
    DAILY_DIR,
    FLUSH_DEDUP_SECONDS,
    FLUSH_PROMPT,
    GIT_BASH_PATH,
    SECONDBRAIN_ROOT,
    STATE_DIR,
)

# Ensure Agent SDK can find git-bash on Windows
os.environ.setdefault("CLAUDE_CODE_GIT_BASH_PATH", GIT_BASH_PATH)
from tools.utils import (
    is_after_hour,
    load_last_flush,
    load_state,
    now_iso,
    save_last_flush,
    sha256_file,
    today_str,
)


def should_skip_flush(session_id: str) -> bool:
    """Check if this session was already flushed recently."""
    if not session_id:
        return False
    last = load_last_flush()
    if last.get("session_id") != session_id:
        return False
    try:
        last_time = datetime.fromisoformat(last["timestamp"])
        now = datetime.fromisoformat(now_iso())
        return (now - last_time).total_seconds() < FLUSH_DEDUP_SECONDS
    except Exception:
        return False


def flush_to_daily(insights: str, project: str = "") -> Path:
    """Append insights to today's daily log file."""
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    daily_file = DAILY_DIR / f"{today_str()}.md"

    now = datetime.now()
    timestamp = now.strftime("%H:%M")

    if not daily_file.exists():
        header = f"# {today_str()}\n\n"
    else:
        header = ""

    heading = f"## {timestamp} — {project}" if project else f"## {timestamp}"
    section = f"{header}{heading}\n\n{insights}\n\n---\n\n"

    with open(daily_file, "a", encoding="utf-8") as f:
        f.write(section)

    return daily_file


def maybe_trigger_compile(daily_file: Path):
    """If after compile hour and daily file changed since last compile, trigger compile."""
    if not is_after_hour(COMPILE_AFTER_HOUR):
        return

    state = load_state()
    current_hash = sha256_file(daily_file)
    last_hash = state.get("daily_hashes", {}).get(daily_file.stem, "")

    if current_hash == last_hash:
        return  # No changes since last compile

    if state.get("compile_in_progress", False):
        return  # Compile already running

    # Spawn compile.py as detached process
    compile_script = SECONDBRAIN_ROOT / "tools" / "compile.py"
    cmd = [
        "uv", "run", "--project", str(SECONDBRAIN_ROOT),
        "python", "-m", "tools.compile",
    ]
    env = {**os.environ, "CLAUDE_INVOKED_BY": "secondbrain"}

    if sys.platform == "win32":
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(
            cmd,
            creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            cwd=str(SECONDBRAIN_ROOT),
        )
    else:
        subprocess.Popen(
            cmd,
            start_new_session=True,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            cwd=str(SECONDBRAIN_ROOT),
        )


def main():
    if len(sys.argv) < 2:
        print("Usage: python flush.py <temp_file_path> [session_id] [project]", file=sys.stderr)
        sys.exit(1)

    temp_file = Path(sys.argv[1])
    session_id = sys.argv[2] if len(sys.argv) > 2 else ""
    project = sys.argv[3] if len(sys.argv) > 3 else ""

    # Dedup check
    if should_skip_flush(session_id):
        temp_file.unlink(missing_ok=True)
        sys.exit(0)

    # Read conversation excerpt
    if not temp_file.exists():
        sys.exit(1)
    conversation = temp_file.read_text(encoding="utf-8")
    temp_file.unlink(missing_ok=True)

    if not conversation.strip():
        sys.exit(0)

    # Use Agent SDK to extract insights
    try:
        import asyncio
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage

        prompt = f"{FLUSH_PROMPT}\n\n---\n\n## Conversation Excerpt\n\n{conversation}"

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
                    content = message.content if hasattr(message, "content") else ""
                    if isinstance(content, list):
                        for block in content:
                            if hasattr(block, "text"):
                                text_parts.append(block.text)
                    elif isinstance(content, str):
                        text_parts.append(content)
                elif isinstance(message, ResultMessage):
                    # Final result
                    pass
            return "\n".join(text_parts)

        response_text = asyncio.run(run_query()).strip()

    except Exception as e:
        # Log error but don't crash
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        log_file = STATE_DIR / "flush.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{now_iso()}] Flush error: {e}\n")
        sys.exit(1)

    # Check if Claude decided nothing is worth saving
    if not response_text or response_text.strip() == "NO_INSIGHTS":
        save_last_flush({
            "session_id": session_id,
            "timestamp": now_iso(),
            "result": "no_insights",
        })
        sys.exit(0)

    # Append to daily log
    daily_file = flush_to_daily(response_text, project=project)

    # Record flush
    save_last_flush({
        "session_id": session_id,
        "timestamp": now_iso(),
        "result": "flushed",
    })

    # Maybe trigger compile
    maybe_trigger_compile(daily_file)


if __name__ == "__main__":
    main()
