"""Build a JSON search index from wiki pages.

Generates .state/search-index.json containing structured metadata for each
wiki page: slug, title, type, confidence, tags, headings, first paragraph,
and outgoing wikilinks. This index is consumed by the Angular viewer's
MiniSearch for enhanced client-side search.

Usage:
  python -m tools.search_index       # build index
"""

import json
import os
import re
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tools.config import STATE_DIR, WIKI_DIR

FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)
YAML_FIELD_RE = re.compile(r"^(\w[\w_-]*):\s*(.*)", re.MULTILINE)
YAML_LIST_RE = re.compile(r"^\s*-\s+(.+)", re.MULTILINE)
HEADING_RE = re.compile(r"^#+\s+(.+)", re.MULTILINE)
WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]")
SOURCES_RE = re.compile(r"sources:\s*\[(.*?)\]", re.DOTALL)


def extract_yaml_value(yaml_block: str, field: str) -> str:
    """Extract a simple scalar value from a YAML block."""
    for m in YAML_FIELD_RE.finditer(yaml_block):
        if m.group(1) == field:
            val = m.group(2).strip().strip('"').strip("'")
            return val
    return ""


def extract_yaml_list(yaml_block: str, field: str) -> list[str]:
    """Extract a YAML list field (inline [...] or multi-line - items)."""
    # Try inline format first: field: [a, b, c]
    pattern = re.compile(rf"^{field}:\s*\[(.*?)\]", re.MULTILINE | re.DOTALL)
    m = pattern.search(yaml_block)
    if m:
        items = m.group(1)
        return [s.strip().strip('"').strip("'") for s in items.split(",") if s.strip()]
    # Try multi-line format
    in_field = False
    results = []
    for line in yaml_block.split("\n"):
        if line.startswith(f"{field}:"):
            in_field = True
            continue
        if in_field:
            lm = re.match(r"^\s+-\s+(.*)", line)
            if lm:
                results.append(lm.group(1).strip().strip('"').strip("'"))
            elif line.strip() and not line.startswith(" "):
                break
    return results


def build_search_index() -> list[dict]:
    """Build search index from all wiki markdown files."""
    index = []

    for md_file in sorted(WIKI_DIR.rglob("*.md")):
        rel = md_file.relative_to(WIKI_DIR)
        if rel.name in ("index.md", "log.md"):
            continue

        content = md_file.read_text(encoding="utf-8")
        fm_match = FRONTMATTER_RE.match(content)
        if not fm_match:
            continue

        yaml_block = fm_match.group(1)
        body = content[fm_match.end():].strip()

        # Extract slug from path
        slug = rel.stem
        title = extract_yaml_value(yaml_block, "title") or slug.replace("-", " ").title()
        page_type = extract_yaml_value(yaml_block, "type") or "concept"
        confidence = extract_yaml_value(yaml_block, "confidence") or ""
        tags = extract_yaml_list(yaml_block, "tags")

        # Extract headings
        headings = HEADING_RE.findall(body)

        # Extract first meaningful paragraph
        first_para = ""
        for line in body.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith(">") and not stripped.startswith("-") and not stripped.startswith("|"):
                first_para = stripped
                break

        # Extract outgoing wikilinks
        links = list(set(WIKILINK_RE.findall(body)))

        # Extract source count
        sm = SOURCES_RE.search(yaml_block)
        source_count = 0
        if sm and sm.group(1).strip():
            source_count = len([s for s in sm.group(1).split(",") if s.strip()])

        # Body text for full-text search (strip markdown formatting)
        body_text = re.sub(r"[#*_`\[\]|>]", " ", body)
        body_text = re.sub(r"\s+", " ", body_text).strip()[:2000]

        index.append({
            "slug": slug,
            "path": str(rel).replace("\\", "/"),
            "title": title,
            "type": page_type,
            "confidence": confidence,
            "tags": tags,
            "headings": headings[:10],
            "summary": first_para[:300],
            "links": links,
            "sourceCount": source_count,
            "bodyText": body_text,
        })

    return index


def main():
    print("Building search index...")
    index = build_search_index()

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = STATE_DIR / "search-index.json"
    output_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    size_kb = output_path.stat().st_size / 1024
    print(f"Done. {len(index)} pages indexed -> {output_path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
