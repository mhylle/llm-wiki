"""Build a knowledge graph from wiki pages.

Extracts nodes (pages) and edges (relationships + wikilinks) into a JSON
graph file that can be consumed by the Angular viewer for visualization.

Usage:
  python -m tools.graph              # build graph
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
WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]")
RELATIONSHIP_RE = re.compile(
    r"""[-]\s*\{?\s*target:\s*["']?([^"',}]+)["']?\s*,\s*type:\s*["']?([^"',}]+)["']?\s*\}?""",
    re.MULTILINE,
)

VALID_RELATIONSHIP_TYPES = {
    "uses", "depends-on", "extends", "contradicts",
    "caused-by", "supersedes", "related-to",
}


def extract_yaml_value(yaml_block: str, field: str) -> str:
    """Extract a simple scalar value."""
    m = re.search(rf"^{field}:\s*(.+)", yaml_block, re.MULTILINE)
    if m:
        return m.group(1).strip().strip('"').strip("'")
    return ""


def extract_relationships(yaml_block: str) -> list[dict]:
    """Extract typed relationships from YAML frontmatter."""
    relationships = []
    in_rels = False
    for line in yaml_block.split("\n"):
        if line.startswith("relationships:"):
            in_rels = True
            continue
        if in_rels:
            if line.strip().startswith("-"):
                m = RELATIONSHIP_RE.search(line)
                if m:
                    target = m.group(1).strip()
                    rel_type = m.group(2).strip()
                    if rel_type in VALID_RELATIONSHIP_TYPES:
                        relationships.append({"target": target, "type": rel_type})
            elif line.strip() and not line.startswith(" "):
                break
    return relationships


def build_graph() -> dict:
    """Build the knowledge graph from all wiki pages."""
    nodes = []
    edges = []
    known_slugs = set()

    # First pass: collect all slugs
    for md_file in WIKI_DIR.rglob("*.md"):
        rel = md_file.relative_to(WIKI_DIR)
        if rel.name in ("index.md", "log.md"):
            continue
        known_slugs.add(rel.stem)

    # Second pass: extract nodes and edges
    for md_file in sorted(WIKI_DIR.rglob("*.md")):
        rel = md_file.relative_to(WIKI_DIR)
        if rel.name in ("index.md", "log.md"):
            continue

        content = md_file.read_text(encoding="utf-8")
        fm_match = FRONTMATTER_RE.match(content)
        if not fm_match:
            continue

        yaml_block = fm_match.group(1)
        body = content[fm_match.end():]
        slug = rel.stem

        title = extract_yaml_value(yaml_block, "title") or slug.replace("-", " ").title()
        page_type = extract_yaml_value(yaml_block, "type") or "concept"
        confidence = extract_yaml_value(yaml_block, "confidence") or "low"
        tier = extract_yaml_value(yaml_block, "tier") or ""
        superseded_by = extract_yaml_value(yaml_block, "superseded_by")
        supersedes_val = extract_yaml_value(yaml_block, "supersedes")

        nodes.append({
            "slug": slug,
            "title": title,
            "type": page_type,
            "confidence": confidence,
            "tier": tier,
        })

        # Explicit typed relationships from frontmatter
        for rel_entry in extract_relationships(yaml_block):
            target = rel_entry["target"]
            if target in known_slugs:
                edges.append({
                    "source": slug,
                    "target": target,
                    "type": rel_entry["type"],
                })

        # Supersession edges
        if superseded_by:
            clean = superseded_by.strip("[]")
            if clean in known_slugs:
                edges.append({"source": slug, "target": clean, "type": "supersedes"})
        if supersedes_val:
            clean = supersedes_val.strip("[]")
            if clean in known_slugs:
                edges.append({"source": slug, "target": clean, "type": "supersedes"})

        # Implicit edges from wikilinks (as related-to)
        for link_target in set(WIKILINK_RE.findall(body)):
            link_target = link_target.strip()
            if link_target in known_slugs and link_target != slug:
                # Don't duplicate if already an explicit relationship
                existing = {(e["source"], e["target"]) for e in edges if e["source"] == slug}
                if (slug, link_target) not in existing:
                    edges.append({
                        "source": slug,
                        "target": link_target,
                        "type": "related-to",
                    })

    return {
        "generatedAt": __import__("tools.utils", fromlist=["now_iso"]).now_iso(),
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "nodes": nodes,
        "edges": edges,
    }


def main():
    print("Building knowledge graph...")
    graph = build_graph()

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = STATE_DIR / "graph.json"
    output_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")

    size_kb = output_path.stat().st_size / 1024
    print(f"Done. {graph['nodeCount']} nodes, {graph['edgeCount']} edges -> {output_path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
