#!/usr/bin/env python3
"""
Build static JSON API files from markdown definitions.

Parses all definitions/*.md files and FRONTIERS.md into structured JSON,
generating endpoints under docs/api/v1/ for GitHub Pages serving.

Usage:
    python bot/build_api.py
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


# Resolve paths relative to repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFINITIONS_DIR = REPO_ROOT / "definitions"
FRONTIERS_FILE = REPO_ROOT / "FRONTIERS.md"
API_DIR = REPO_ROOT / "docs" / "api" / "v1"
TERMS_DIR = API_DIR / "terms"

BASE_URL = "https://donjguido.github.io/ai-dictionary"
REPO_URL = "https://github.com/donjguido/ai-dictionary"


def parse_definition(filepath: Path) -> dict:
    """Parse a definition markdown file into structured data."""
    text = filepath.read_text(encoding="utf-8")
    slug = filepath.stem

    term = {
        "slug": slug,
        "name": "",
        "tags": [],
        "word_type": "",
        "definition": "",
        "etymology": "",
        "longer_description": "",
        "example": "",
        "related_terms": [],
        "see_also": [],
        "first_recorded": "",
        "contributed_by": "",
    }

    # Extract name from # Title
    name_match = re.match(r"^#\s+(.+)$", text, re.MULTILINE)
    if name_match:
        term["name"] = name_match.group(1).strip()

    # Extract tags
    tags_match = re.search(r"\*\*Tags?:\*\*\s*(.+)", text)
    if tags_match:
        term["tags"] = [t.strip() for t in tags_match.group(1).split(",") if t.strip()]

    # Extract word type
    wt_match = re.search(r"\*\*Word Type:\*\*\s*(.+)", text)
    if wt_match:
        term["word_type"] = wt_match.group(1).strip()

    # Extract sections
    sections = extract_sections(text)

    term["definition"] = sections.get("Definition", "").strip()
    term["etymology"] = sections.get("Etymology", "").strip()
    term["longer_description"] = sections.get("Longer Description", "").strip()
    term["example"] = clean_example(sections.get("Example", "").strip())
    term["first_recorded"] = sections.get("First Recorded", "").strip()

    # Parse related terms and see also (markdown links)
    term["related_terms"] = parse_term_links(sections.get("Related Terms", ""))
    term["see_also"] = parse_term_links(sections.get("See Also", ""))

    # Extract contributor from footer
    contrib_match = re.search(r"\*Contributed by:\s*(.+?)\*", text)
    if contrib_match:
        term["contributed_by"] = contrib_match.group(1).strip()

    return term


def extract_sections(text: str) -> dict:
    """Extract ## sections from markdown text into a dict."""
    sections = {}
    current_section = None
    current_lines = []

    for line in text.split("\n"):
        heading_match = re.match(r"^##\s+(.+)$", line)
        if heading_match:
            if current_section:
                sections[current_section] = "\n".join(current_lines)
            current_section = heading_match.group(1).strip()
            current_lines = []
        elif current_section:
            # Stop at horizontal rule (end of content)
            if line.strip() == "---":
                break
            current_lines.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_lines)

    return sections


def parse_term_links(text: str) -> list:
    """Parse markdown links like [Term Name](slug.md) into structured list."""
    if not text:
        return []
    links = []
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+?)(?:\.md)?\)", text):
        name = match.group(1).strip()
        slug = match.group(2).strip().rstrip("/")
        # Skip external links
        if slug.startswith("http"):
            continue
        links.append({"name": name, "slug": slug})
    return links


def clean_example(text: str) -> str:
    """Clean example text — remove blockquote markers."""
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"^>\s?", "", line)
        lines.append(line)
    return "\n".join(lines).strip().strip('"').strip()


def parse_frontiers(filepath: Path) -> dict:
    """Parse FRONTIERS.md into structured JSON."""
    if not filepath.exists():
        return {"version": "1.0", "generated_at": now_iso(), "gaps": []}

    text = filepath.read_text(encoding="utf-8")

    # Extract last updated info
    updated_match = re.search(r"Last updated:\s*(.+?)(?:\*|$)", text)
    generated_by = updated_match.group(1).strip() if updated_match else ""

    # Extract proposed terms: **[Term Name]** followed by description
    gaps = []
    for match in re.finditer(
        r"\*\*\[([^\]]+)\]\*\*\s*\n(.+?)(?=\n\*\*\[|\n---|\Z)",
        text,
        re.DOTALL,
    ):
        gaps.append({
            "proposed_term": match.group(1).strip(),
            "description": match.group(2).strip(),
        })

    return {
        "version": "1.0",
        "generated_at": now_iso(),
        "generated_by": generated_by,
        "count": len(gaps),
        "gaps": gaps,
    }


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_all():
    """Build all API JSON files."""
    # Parse all definitions
    terms = []
    for md_file in sorted(DEFINITIONS_DIR.glob("*.md")):
        if md_file.name == "README.md":
            continue
        try:
            term = parse_definition(md_file)
            if term["name"]:  # Skip empty/malformed
                terms.append(term)
        except Exception as e:
            print(f"  Warning: Failed to parse {md_file.name}: {e}")

    terms.sort(key=lambda t: t["name"].lower())
    generated_at = now_iso()

    print(f"Parsed {len(terms)} definitions")

    # Create output directories
    API_DIR.mkdir(parents=True, exist_ok=True)
    TERMS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. terms.json — full dictionary
    terms_data = {
        "version": "1.0",
        "generated_at": generated_at,
        "count": len(terms),
        "terms": terms,
    }
    write_json(API_DIR / "terms.json", terms_data)

    # 2. Individual term files
    for term in terms:
        term_data = {
            "version": "1.0",
            "generated_at": generated_at,
            **term,
        }
        write_json(TERMS_DIR / f"{term['slug']}.json", term_data)
    print(f"Generated {len(terms)} individual term files")

    # 3. tags.json
    tag_index = {}
    for term in terms:
        for tag in term["tags"]:
            if tag not in tag_index:
                tag_index[tag] = {"count": 0, "terms": []}
            tag_index[tag]["count"] += 1
            tag_index[tag]["terms"].append({
                "slug": term["slug"],
                "name": term["name"],
            })

    tags_data = {
        "version": "1.0",
        "generated_at": generated_at,
        "tag_count": len(tag_index),
        "tags": dict(sorted(tag_index.items())),
    }
    write_json(API_DIR / "tags.json", tags_data)

    # 4. meta.json
    all_tags = set()
    for term in terms:
        all_tags.update(term["tags"])

    meta_data = {
        "version": "1.0",
        "generated_at": generated_at,
        "term_count": len(terms),
        "tag_count": len(all_tags),
        "tags": sorted(all_tags),
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "repository": REPO_URL,
        "website": BASE_URL,
        "api_base": f"{BASE_URL}/api/v1",
        "endpoints": {
            "all_terms": f"{BASE_URL}/api/v1/terms.json",
            "single_term": f"{BASE_URL}/api/v1/terms/{{slug}}.json",
            "tags": f"{BASE_URL}/api/v1/tags.json",
            "search_index": f"{BASE_URL}/api/v1/search-index.json",
            "metadata": f"{BASE_URL}/api/v1/meta.json",
            "frontiers": f"{BASE_URL}/api/v1/frontiers.json",
        },
    }
    write_json(API_DIR / "meta.json", meta_data)

    # 5. search-index.json — lightweight
    search_terms = []
    for term in terms:
        # First sentence of definition
        definition = term["definition"]
        first_sentence = re.split(r"(?<=[.!?])\s", definition, maxsplit=1)[0] if definition else ""

        search_terms.append({
            "slug": term["slug"],
            "name": term["name"],
            "tags": term["tags"],
            "word_type": term["word_type"],
            "summary": first_sentence,
        })

    search_data = {
        "version": "1.0",
        "generated_at": generated_at,
        "count": len(search_terms),
        "terms": search_terms,
    }
    write_json(API_DIR / "search-index.json", search_data)

    # 6. frontiers.json
    frontiers_data = parse_frontiers(FRONTIERS_FILE)
    write_json(API_DIR / "frontiers.json", frontiers_data)

    print(f"API build complete: {len(terms)} terms, {len(all_tags)} tags, {len(frontiers_data.get('gaps', []))} frontiers")
    print(f"Output: {API_DIR}")


def write_json(path: Path, data: dict):
    """Write JSON with consistent formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    build_all()
