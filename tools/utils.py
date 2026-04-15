"""Shared utilities for the secondbrain memory pipeline."""

import hashlib
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from tools.config import LAST_FLUSH_FILE, STATE_DIR, STATE_FILE


def local_now() -> datetime:
    """Current local time, timezone-aware."""
    try:
        tz = ZoneInfo("localtime")
    except Exception:
        tz = timezone.utc
    return datetime.now(tz)


def today_str() -> str:
    """Today's date as YYYY-MM-DD in local time."""
    return local_now().strftime("%Y-%m-%d")


def now_iso() -> str:
    """Current local time as ISO 8601 string."""
    return local_now().isoformat()


def is_after_hour(hour: int) -> bool:
    """Check if local time is past the given hour (24h)."""
    return local_now().hour >= hour


def sha256_file(path: Path) -> str:
    """SHA-256 hash of a file, first 16 hex chars."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def truncate_to_chars(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, adding indicator if truncated."""
    if len(text) <= max_chars:
        return text
    lines = text[:max_chars].rsplit("\n", 1)[0]
    remaining = text[len(lines):].count("\n")
    return lines + f"\n\n... (truncated, {remaining} more lines)"


def read_last_n_lines(path: Path, n: int) -> str:
    """Read the last n lines of a file."""
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[-n:])


# --- State management ---

def _ensure_state_dir():
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> dict:
    """Load .state/state.json, returning empty dict if missing."""
    if not STATE_FILE.exists():
        return {"daily_hashes": {}, "last_compile": None, "compile_in_progress": False}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict):
    """Write .state/state.json."""
    _ensure_state_dir()
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_last_flush() -> dict:
    """Load .state/last-flush.json."""
    if not LAST_FLUSH_FILE.exists():
        return {}
    return json.loads(LAST_FLUSH_FILE.read_text(encoding="utf-8"))


def save_last_flush(data: dict):
    """Write .state/last-flush.json."""
    _ensure_state_dir()
    LAST_FLUSH_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def is_windows() -> bool:
    return platform.system() == "Windows"


def extract_transcript_turns(transcript_path: str, max_turns: int, max_chars: int) -> str:
    """Extract the last N human/assistant turns from a JSONL transcript file.

    Returns a markdown-formatted conversation excerpt.
    """
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

                # Extract text content from message object
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

    # Take last N turns
    recent = turns[-max_turns:]
    result = "\n\n".join(recent)

    return truncate_to_chars(result, max_chars)
