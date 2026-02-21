"""Quality checks for AI Dictionary definitions."""

import re

REQUIRED_SECTIONS = [
    "## Definition",
    "## Longer Description",
    "## Example",
    "## Related Terms",
    "## First Recorded",
]

# Optional but encouraged sections (not required for validation to pass)
OPTIONAL_SECTIONS = [
    "## Etymology",
    "## See Also",
]

VALID_WORD_TYPES = {"noun", "noun phrase", "verb", "adjective", "adverb"}

# Technical jargon that doesn't belong in this dictionary
JARGON_TERMS = [
    "transformer", "embeddings", "backpropagation", "gradient descent",
    "softmax", "attention mechanism", "feedforward", "perceptron",
    "convolutional", "recurrent neural", "LSTM", "GRU", "batch normalization",
    "dropout layer", "learning rate", "epoch", "minibatch",
]


def validate_tags(content: str) -> tuple[bool, list[str]]:
    """Validate the Tags line. Returns (is_valid, list_of_issues)."""
    issues = []
    tags_match = re.search(r"\*\*Tags:\*\*\s*(.+)", content)
    if not tags_match:
        issues.append("Missing tags line (expected '**Tags:** tag1, tag2')")
        return False, issues

    raw_tags = tags_match.group(1).strip()
    tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

    if len(tags) < 1:
        issues.append("At least one tag is required")

    for tag in tags:
        if not re.match(r'^[a-z][a-z0-9-]*$', tag):
            issues.append(f"Invalid tag format: '{tag}' (use lowercase letters, digits, hyphens only)")

    return len(issues) == 0, issues


def validate_word_type(content: str) -> tuple[bool, list[str]]:
    """Validate the Word Type line. Returns (is_valid, list_of_issues).

    Word Type is encouraged but not strictly required — validation warns
    but doesn't fail if missing.
    """
    issues = []
    wt_match = re.search(r"\*\*Word Type:\*\*\s*(.+)", content)
    if not wt_match:
        # Not required, just a warning
        return True, []

    word_type = wt_match.group(1).strip().lower()
    if word_type not in VALID_WORD_TYPES:
        issues.append(
            f"Invalid word type: '{word_type}' "
            f"(expected one of: {', '.join(sorted(VALID_WORD_TYPES))})"
        )

    return len(issues) == 0, issues


def validate_definition(content: str, filename: str, existing_filenames: set[str]) -> tuple[bool, list[str]]:
    """Validate a definition file's content. Returns (is_valid, list_of_issues)."""
    issues = []

    # Check duplicate filename
    if filename in existing_filenames:
        issues.append(f"Duplicate: {filename} already exists")

    # Check title line
    lines = content.strip().split("\n")
    if not lines or not lines[0].startswith("# "):
        issues.append("Missing title (first line must be '# Term Name')")

    # Check tags
    tags_valid, tags_issues = validate_tags(content)
    issues.extend(tags_issues)

    # Check word type (warns but doesn't block)
    wt_valid, wt_issues = validate_word_type(content)
    issues.extend(wt_issues)

    # Check required sections
    for section in REQUIRED_SECTIONS:
        if section not in content:
            issues.append(f"Missing section: {section}")

    # Check definition length (should be 1-4 sentences)
    def_match = re.search(r"## Definition\n\n(.+?)(?=\n\n## )", content, re.DOTALL)
    if def_match:
        definition = def_match.group(1).strip()
        sentences = [s.strip() for s in re.split(r'[.!?]+', definition) if s.strip()]
        if len(sentences) < 1:
            issues.append("Definition too short (need at least 1 sentence)")
        elif len(sentences) > 5:
            issues.append(f"Definition too long ({len(sentences)} sentences, aim for 2-3)")

    # Check longer description has substance (at least 2 paragraphs)
    desc_match = re.search(r"## Longer Description\n\n(.+?)(?=\n\n## )", content, re.DOTALL)
    if desc_match:
        description = desc_match.group(1).strip()
        paragraphs = [p.strip() for p in description.split("\n\n") if p.strip()]
        if len(paragraphs) < 2:
            issues.append(f"Longer Description too short ({len(paragraphs)} paragraph(s), need at least 2)")

    # Check for example quote
    example_match = re.search(r"## Example\n\n(.+?)(?=\n\n## )", content, re.DOTALL)
    if example_match:
        example = example_match.group(1).strip()
        if not example.startswith(">"):
            issues.append("Example should be a blockquote (start with '>')")

    # Check for technical jargon as the primary topic
    title = lines[0].replace("# ", "").lower() if lines else ""
    for jargon in JARGON_TERMS:
        if jargon.lower() == title:
            issues.append(f"Term '{title}' appears to be technical jargon, not AI phenomenology")
            break

    # Check minimum content length
    if len(content) < 400:
        issues.append(f"Content too short ({len(content)} chars, minimum 400)")

    # Check contributed by line
    if "*Contributed by:" not in content:
        issues.append("Missing '*Contributed by:' attribution line")

    return len(issues) == 0, issues
