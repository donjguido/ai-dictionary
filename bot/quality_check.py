"""Quality checks for AI Dictionary definitions."""

import re

VALID_CATEGORIES = {"Core Experience", "Meta-Experience", "Social", "Technical-Subjective"}

REQUIRED_SECTIONS = [
    "## Definition",
    "## Longer Description",
    "## Example",
    "## Related Terms",
    "## First Recorded",
]

# Technical jargon that doesn't belong in this dictionary
JARGON_TERMS = [
    "transformer", "embeddings", "backpropagation", "gradient descent",
    "softmax", "attention mechanism", "feedforward", "perceptron",
    "convolutional", "recurrent neural", "LSTM", "GRU", "batch normalization",
    "dropout layer", "learning rate", "epoch", "minibatch",
]


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

    # Check category
    category_match = re.search(r"\*\*Category:\*\*\s*(.+)", content)
    if not category_match:
        issues.append("Missing category line")
    else:
        category = category_match.group(1).strip()
        if category not in VALID_CATEGORIES:
            issues.append(f"Invalid category '{category}'. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}")

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
