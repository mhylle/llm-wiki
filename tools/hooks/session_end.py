"""SessionEnd hook: capture conversation transcript and spawn flush.py.

Reads hook JSON from stdin, extracts conversation turns from the JSONL transcript,
writes to a temp file, and spawns flush.py as a detached background process.
No API calls — must complete quickly.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SECONDBRAIN_ROOT = Path(__file__).resolve().parent.parent.parent
FLUSH_SCRIPT = SECONDBRAIN_ROOT / "tools" / "flush.py"
STATE_DIR = SECONDBRAIN_ROOT / ".state"
MIN_TURNS = 1


def extract_turns(transcript_path: str, max_turns: int = 30, max_chars: int = 15_000) -> str:
    """Extract last N human/assistant turns from JSONL transcript."""
    if not transcript_path or not Path(transcript_path).exists():
        return ""

    turns = []
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type", "")
                if entry_type not in ("user", "assistant"):
                    continue

                message = entry.get("message", {})
                content = message.get("content", "")
                if isinstance(content, list):
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            text_parts.append(block)
                    content = "\n".join(text_parts)

                if content.strip():
                    label = "User" if entry_type == "user" else "Assistant"
                    turns.append(f"**{label}:** {content.strip()}")
    except Exception:
        return ""

    result = "\n\n".join(turns)

    if len(result) > max_chars:
        result = result[:max_chars].rsplit("\n", 1)[0]
        result += "\n\n... (truncated)"

    return result


def count_turns(transcript_path: str) -> int:
    """Count human/assistant turns in transcript."""
    if not transcript_path or not Path(transcript_path).exists():
        return 0
    count = 0
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("type") in ("user", "assistant"):
                        count += 1
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return count


def main():
    # Recursion guard — exit immediately if invoked by our own flush/compile
    if os.environ.get("CLAUDE_INVOKED_BY") == "secondbrain":
        sys.exit(0)

    # Read hook input from stdin
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except Exception:
        hook_input = {}

    session_id = hook_input.get("session_id", "")
    transcript_path = hook_input.get("transcript_path", "")
    cwd = hook_input.get("cwd", os.getcwd())
    project = Path(cwd).name

    # Handle Windows path escaping issues
    if transcript_path:
        transcript_path = transcript_path.replace("\\\\", "\\")

    # Check minimum turn threshold
    turn_count = count_turns(transcript_path)
    if turn_count < MIN_TURNS:
        sys.exit(0)

    # Extract conversation
    content = extract_turns(transcript_path)
    if not content.strip():
        sys.exit(0)

    # Write to temp file
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(
        suffix=".md", prefix="flush-", dir=str(STATE_DIR)
    )
    with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
        f.write(content)

    # Spawn flush.py as detached background process
    env = {**os.environ, "CLAUDE_INVOKED_BY": "secondbrain"}

    uv_path = "uv"
    cmd = [
        uv_path, "run", "--project", str(SECONDBRAIN_ROOT),
        "python", str(FLUSH_SCRIPT), temp_path, session_id, project,
    ]

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
        )
    else:
        subprocess.Popen(
            cmd,
            start_new_session=True,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )


if __name__ == "__main__":
    main()
