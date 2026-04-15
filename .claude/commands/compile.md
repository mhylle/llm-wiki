Compile daily conversation logs into secondbrain wiki pages.

## Steps

1. The secondbrain project root is the directory containing this `CLAUDE.md` file.
   Set `SB_ROOT` to the current working directory.

2. Run the compile pipeline:
   ```bash
   cd $SB_ROOT && uv run python -m tools.compile
   ```

3. Report what pages were created or updated.
