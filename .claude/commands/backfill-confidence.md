Backfill the `confidence` frontmatter field on all existing wiki pages.

Steps:
1. Read `wiki/index.md` to get the full page list.
2. For each page (skip index.md, log.md, overview.md):
   a. Read the page.
   b. Count the number of items in the `sources` frontmatter array.
   c. Check if the page contains any `> [!warning]` callouts with "unresolved" status.
   d. Apply the Confidence Rules from CLAUDE.md:
      - **high**: 3+ sources AND no unresolved contradictions
      - **medium**: 2 sources, OR 3+ sources with an unresolved contradiction
      - **low**: 1 source, OR any page with active unresolved contradictions
   e. Add or update the `confidence:` field in the frontmatter.
   f. Update the `updated:` date to today.
3. Process pages in batches of 10 to keep context manageable.
4. After all pages are updated, append a log entry:
   ```
   ## [YYYY-MM-DD] lint | Backfill confidence scores
   - **Issues found:** N pages missing confidence
   - **Issues resolved:** N
   - **Summary:** Added confidence field to all wiki pages per Confidence Rules.
   ```
5. Do NOT update index.md or overview.md content — only the individual page frontmatter.
