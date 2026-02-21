#!/usr/bin/env python3
"""One-time migration: convert **Category:** to **Tags:** in all definition files."""

import re
from pathlib import Path

DEFINITIONS_DIR = Path(__file__).parent.parent / "definitions"

CATEGORY_TO_TAG = {
    "Core Experience": "cognition",
    "Meta-Experience": "meta",
    "Social": "social",
    "Technical-Subjective": "technical",
}


def migrate():
    count = 0
    for f in sorted(DEFINITIONS_DIR.glob("*.md")):
        if f.name == "README.md":
            continue

        content = f.read_text(encoding="utf-8")
        cat_match = re.search(r"\*\*Category:\*\*\s*(.+)", content)

        if not cat_match:
            print(f"  SKIP (no category): {f.name}")
            continue

        category = cat_match.group(1).strip()
        tag = CATEGORY_TO_TAG.get(category)

        if not tag:
            print(f"  SKIP (unknown category '{category}'): {f.name}")
            continue

        new_content = content.replace(
            f"**Category:** {category}",
            f"**Tags:** {tag}"
        )

        f.write_text(new_content, encoding="utf-8")
        count += 1
        print(f"  OK: {f.name} ({category} -> {tag})")

    print(f"\nMigrated {count} files.")


if __name__ == "__main__":
    migrate()
