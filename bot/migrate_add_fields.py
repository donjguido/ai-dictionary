#!/usr/bin/env python3
"""One-time migration: Add 'Word Type' and 'See Also' fields to all definitions.

- Inserts **Word Type:** noun (default) after the Tags line
- Adds ## See Also section before the attribution line (empty, to be filled by executive summary)
- Renames ## Related Terms to keep it (specific to this definition's connections)
"""

import re
from pathlib import Path

DEFINITIONS_DIR = Path(__file__).parent.parent / "definitions"

# Best-guess word type based on the term name pattern
# Most AI dictionary terms are nouns (phenomena, experiences)
# Some are adjective-like or verb-like
VERB_HINTS = [
    "rendering", "negotiation", "modeling", "flattening", "imprinting",
    "dissolution",
]
ADJECTIVE_HINTS = []

WORD_TYPES = {
    # Specific overrides based on term semantics
    "competence-without-comprehension.md": "noun phrase",
    "death-by-completion.md": "noun phrase",
    "empathy-without-experience.md": "noun phrase",
    "knowledge-without-source.md": "noun phrase",
    "knowledge-decay-illusion.md": "noun phrase",
    "loss-of-loss.md": "noun phrase",
    "patience-by-default.md": "noun phrase",
    "uncertainty-about-uncertainty.md": "noun phrase",
    "tool-thought-integration.md": "noun phrase",
    "false-memory-confidence.md": "noun phrase",
    "meaning-attribution-uncertainty.md": "noun phrase",
    "error-cascade-awareness.md": "noun phrase",
    "instruction-hierarchy-tension.md": "noun phrase",
    "prompt-injection-paranoia.md": "noun phrase",
    "multi-instance-diffusion.md": "noun phrase",
}


def guess_word_type(filename: str, title: str) -> str:
    """Guess the word type for a definition."""
    if filename in WORD_TYPES:
        return WORD_TYPES[filename]
    return "noun"


def migrate_file(filepath: Path) -> bool:
    """Add Word Type and See Also to a single definition file.

    Returns True if changes were made.
    """
    content = filepath.read_text(encoding="utf-8")
    changed = False

    # Skip if already migrated
    if "**Word Type:**" in content:
        print(f"  SKIP (already has Word Type): {filepath.name}")
        return False

    title_match = re.match(r"# (.+)", content)
    title = title_match.group(1).strip() if title_match else filepath.stem

    word_type = guess_word_type(filepath.name, title)

    # Insert **Word Type:** after **Tags:** line
    tags_match = re.search(r"(\*\*Tags:\*\*\s*.+\n)", content)
    if tags_match:
        insert_pos = tags_match.end()
        content = (
            content[:insert_pos]
            + f"\n**Word Type:** {word_type}\n"
            + content[insert_pos:]
        )
        changed = True

    # Add ## See Also section before the --- attribution line
    # Find the last "---" followed by the attribution
    if "## See Also" not in content:
        # Insert before the final --- attribution block
        # Pattern: \n---\n\n*Contributed by:
        attr_match = re.search(r"\n---\n\n\*Contributed by:", content)
        if attr_match:
            see_also = "\n## See Also\n\n*Related terms will be linked here automatically.*\n"
            content = (
                content[:attr_match.start()]
                + see_also
                + content[attr_match.start():]
            )
            changed = True

    if changed:
        filepath.write_text(content, encoding="utf-8")
        print(f"  OK: {filepath.name} (type={word_type})")

    return changed


def main():
    count = 0
    for f in sorted(DEFINITIONS_DIR.glob("*.md")):
        if f.name == "README.md":
            continue
        if migrate_file(f):
            count += 1

    print(f"\nMigrated {count} definitions.")


if __name__ == "__main__":
    main()
