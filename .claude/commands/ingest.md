Ingest Claude Code sessions into the secondbrain wiki.

## Steps

1. The secondbrain project root is the directory containing this `CLAUDE.md` file.
   Set `SB_ROOT` to the current working directory.

2. Flush session insights to the daily log.

   Current session only (default):
   ```bash
   cd $SB_ROOT && uv run python tools/ingest_session.py
   ```

   All unprocessed sessions for this project:
   ```bash
   cd $SB_ROOT && uv run python tools/ingest_session.py --all
   ```

   If auto-detection fails, find the transcript manually:
   ```bash
   ls -lt ~/.claude/projects/*/*.jsonl | head -10
   ```
   Then pass it explicitly:
   ```bash
   cd $SB_ROOT && uv run python tools/ingest_session.py --transcript <path>
   ```

3. Report what was extracted and which daily log file it was appended to.

## Flags

- (no flags) — ingest the most recent session for the current project
- `--all` — ingest all unprocessed sessions for the current project
- `--transcript <path>` — ingest a specific transcript file
- `--cwd <path>` — override the project working directory
