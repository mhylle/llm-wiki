#!/usr/bin/env bash
set -euo pipefail

# LLM Wiki — Installation Script
# Run after cloning the repo on a new machine:
#   cd llm-wiki && bash install.sh

SB_ROOT="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
SKILLS_DIR="$CLAUDE_DIR/skills"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
HOOKS_FILE="$CLAUDE_DIR/hooks.json"

echo "=== LLM Wiki Installer ==="
echo "Project root: $SB_ROOT"
echo ""

# --- 1. Python dependencies ---
echo "[1/5] Installing Python dependencies..."
if command -v uv &>/dev/null; then
    (cd "$SB_ROOT" && uv sync)
else
    echo "ERROR: uv not found. Install it first: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

# --- 2. Create directories ---
echo "[2/5] Creating directories..."
mkdir -p "$SB_ROOT/daily"
mkdir -p "$SB_ROOT/.state"

# --- 3. Install global skills ---
echo "[3/5] Installing /ingest and /compile skills..."
mkdir -p "$SKILLS_DIR/ingest"
cat > "$SKILLS_DIR/ingest/SKILL.md" << SKILL_EOF
---
name: ingest
description: Ingest the current Claude Code session into the LLM wiki. Extracts insights, decisions, patterns, and entities from the conversation and saves them to the daily log. Optionally compiles into wiki pages. Triggers on "/ingest", "ingest this session", "save this to wiki", "capture this session".
---

# Ingest Session to LLM Wiki

## How To Run

1. Set SB_ROOT to: $SB_ROOT

2. Flush this session:
   \`\`\`bash
   cd \$SB_ROOT && uv run python tools/ingest_session.py
   \`\`\`
   If auto-detection fails, find the transcript manually:
   \`\`\`bash
   ls -lt ~/.claude/projects/*/*.jsonl | head -10
   \`\`\`
   Then:
   \`\`\`bash
   cd \$SB_ROOT && uv run python tools/ingest_session.py --transcript <path>
   \`\`\`

3. Compile (if user asks to also compile, or says "ingest and compile"):
   \`\`\`bash
   cd \$SB_ROOT && uv run python -m tools.compile
   \`\`\`

4. Report what was extracted and which daily log file it was appended to.
SKILL_EOF

mkdir -p "$SKILLS_DIR/compile"
cat > "$SKILLS_DIR/compile/SKILL.md" << SKILL_EOF
---
name: compile
description: Compile daily conversation logs into LLM wiki pages. Processes insights from daily/ into structured wiki pages following the CLAUDE.md schema. Triggers on "/compile", "compile the wiki", "compile daily logs".
---

# Compile LLM Wiki Daily Logs

## How To Run

1. Set SB_ROOT to: $SB_ROOT

2. Run compile:
   \`\`\`bash
   cd \$SB_ROOT && uv run python -m tools.compile
   \`\`\`

3. Report what pages were created or updated.
SKILL_EOF

echo "  Installed: $SKILLS_DIR/ingest/SKILL.md"
echo "  Installed: $SKILLS_DIR/compile/SKILL.md"

# --- 4. Configure hooks ---
echo "[4/5] Configuring Claude Code hooks..."

# Determine hook command paths
HOOK_PREFIX="uv run --project $SB_ROOT python"
SESSION_START_CMD="$HOOK_PREFIX $SB_ROOT/tools/hooks/session_start.py"
SESSION_END_CMD="$HOOK_PREFIX $SB_ROOT/tools/hooks/session_end.py"
PRE_COMPACT_CMD="$HOOK_PREFIX $SB_ROOT/tools/hooks/pre_compact.py"

# Add SessionStart hook to settings.json
if [ -f "$SETTINGS_FILE" ]; then
    # Check if wiki hook already exists
    if grep -q "session_start.py" "$SETTINGS_FILE" 2>/dev/null; then
        echo "  SessionStart hook already configured in settings.json"
    else
        echo "  NOTE: Add this SessionStart hook to $SETTINGS_FILE manually:"
        echo "    Command: $SESSION_START_CMD"
        echo "    Timeout: 5, StatusMessage: Loading wiki context..."
    fi
else
    echo "  NOTE: $SETTINGS_FILE not found. Create it or add the SessionStart hook manually."
fi

# Add SessionEnd and PreCompact hooks to hooks.json
if [ -f "$HOOKS_FILE" ]; then
    if grep -q "wiki-capture" "$HOOKS_FILE" 2>/dev/null; then
        echo "  SessionEnd/PreCompact hooks already configured in hooks.json"
    else
        echo "  NOTE: Add these hooks to $HOOKS_FILE manually:"
        echo ""
        echo '  In "SessionEnd" (or "Stop") array:'
        echo "    name: wiki-capture"
        echo "    command: $SESSION_END_CMD"
        echo ""
        echo '  In "PreCompact" array:'
        echo "    name: wiki-capture-before-compact"
        echo "    command: $PRE_COMPACT_CMD"
        echo ""
    fi
else
    # Create hooks.json with wiki hooks
    cat > "$HOOKS_FILE" << HOOKS_EOF
{
  "hooks": {
    "Stop": [
      {
        "name": "wiki-capture",
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "$SESSION_END_CMD",
            "timeout": 10
          }
        ],
        "description": "Capture conversation insights for LLM wiki"
      }
    ],
    "PreCompact": [
      {
        "name": "wiki-capture-before-compact",
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "$PRE_COMPACT_CMD",
            "timeout": 10
          }
        ],
        "description": "Capture conversation insights before compaction"
      }
    ]
  }
}
HOOKS_EOF
    echo "  Created $HOOKS_FILE with wiki hooks"
fi

# Add SessionStart to settings.json if it doesn't exist
if [ ! -f "$SETTINGS_FILE" ]; then
    cat > "$SETTINGS_FILE" << SETTINGS_EOF
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$SESSION_START_CMD",
            "timeout": 5,
            "statusMessage": "Loading wiki context..."
          }
        ]
      }
    ]
  }
}
SETTINGS_EOF
    echo "  Created $SETTINGS_FILE with SessionStart hook"
fi

# --- 5. Summary ---
echo ""
echo "[5/5] Done!"
echo ""
echo "=== Installation Summary ==="
echo "  Project:    $SB_ROOT"
echo "  Skills:     /ingest, /compile (global)"
echo "  Hooks:      SessionStart, SessionEnd, PreCompact"
echo ""
echo "Usage:"
echo "  /ingest              — capture current session insights"
echo "  /ingest and compile  — capture + compile into wiki pages"
echo "  /compile             — compile all unprocessed daily logs"
echo ""
echo "If hooks.json or settings.json already existed, review the"
echo "NOTE messages above and add the hooks manually."
