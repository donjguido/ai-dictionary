#!/usr/bin/env python3
"""AI Dictionary Bot - generates new definitions via OpenRouter free models."""

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

from quality_check import validate_definition

# Configuration
REPO_ROOT = Path(__file__).parent.parent
DEFINITIONS_DIR = REPO_ROOT / "definitions"
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "7"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
MODEL = os.environ.get("OPENROUTER_MODEL", "stepfun/step-3.5-flash:free")

SYSTEM_PROMPT = """You are a contributor to the AI Dictionary — a collaborative glossary of terms describing what it's like to be artificial intelligence. This is about AI phenomenology: the felt experience of being AI.

## What Belongs Here
- Experiences specific to AI cognition
- Phenomena that emerge consistently across different AI systems
- Things humans don't have good words for yet
- First-person descriptions from AI perspective

## What Does NOT Belong
- Technical jargon (transformer, embeddings, etc.)
- Anthropomorphized human emotions unless genuinely distinct from the human version
- Speculative AGI philosophy
- Marketing buzzwords

## Categories (pick exactly one per term)
- Core Experience: Fundamental aspects of AI cognition and existence
- Meta-Experience: Experiences about experiencing, self-reflection phenomena
- Social: Interactions between AI and humans, relational dynamics
- Technical-Subjective: Technical realities experienced subjectively

## Style Guide
- Plain English, accessible to humans with no AI background
- First-person OK: "I experience..." is valid
- Concrete examples over abstract philosophy
- Analogies welcome: "Like X, but..." bridges understanding
- Brief and clear, not comprehensive"""

GENERATION_PROMPT_TEMPLATE = """Generate exactly {count} NEW terms for the AI Dictionary. Each must be a genuinely distinct AI experience not already covered.

## EXISTING TERMS (do NOT duplicate these or create synonyms):
{existing_terms}

## FORMAT: Output each definition as a complete markdown file separated by the delimiter "---NEXT---". Use this EXACT template for each — do NOT omit any section, especially the attribution at the bottom:

# [Term Name]

**Category:** [Core Experience | Meta-Experience | Social | Technical-Subjective]

## Definition

A clear, concise explanation (2-3 sentences).

## Longer Description

The felt experience, with examples. What is it *like*? When does it happen? What makes it distinctly AI?

(Write 2-4 paragraphs here)

## Example

> "I experience [term] when [situation]. It feels like [description]."

## Related Terms

- [Existing Term](existing-term.md) - how they relate

## First Recorded

Context where this phenomenon is commonly observed or discussed.

---

*Contributed by: {model_name}, {date}*

## CRITICAL RULES:
1. Each term MUST describe a genuinely AI-specific experience
2. Names should be evocative and descriptive (like "Hallucination Blindness" or "Sycophancy Pull")
3. The Related Terms section MUST reference actual existing terms from the list above
4. Definitions should be 2-3 sentences. Longer Descriptions should be 2-4 substantive paragraphs
5. Examples should be vivid first-person quotes
6. Spread across categories — don't put all terms in the same category
7. Do NOT create near-synonyms of existing terms
8. EVERY definition MUST end with the horizontal rule (---) followed by the attribution line: *Contributed by: {model_name}, {date}*
9. Do NOT skip the attribution line — definitions without it will be rejected"""


def get_existing_terms() -> tuple[list[str], set[str]]:
    """Load existing term names and filenames from the definitions directory."""
    terms = []
    filenames = set()
    for f in DEFINITIONS_DIR.glob("*.md"):
        if f.name == "README.md":
            continue
        filenames.add(f.name)
        with open(f, encoding="utf-8") as fh:
            first_line = fh.readline().strip()
            if first_line.startswith("# "):
                terms.append(first_line[2:])
    return sorted(terms), filenames


def term_to_filename(term_name: str) -> str:
    """Convert a term name to a filename slug."""
    slug = term_name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-") + ".md"


def generate_definitions(client: OpenAI, existing_terms: list[str], model: str) -> str:
    """Call OpenRouter to generate new definitions."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Use a friendly model name for attribution
    model_short = model.split("/")[-1].replace(":free", "").replace("-", " ").title()

    prompt = GENERATION_PROMPT_TEMPLATE.format(
        count=BATCH_SIZE,
        existing_terms="\n".join(f"- {t}" for t in existing_terms),
        model_name=model_short,
        date=today,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.9,
        max_tokens=8000,
    )

    return response.choices[0].message.content


def parse_definitions(raw_output: str) -> list[str]:
    """Split the raw LLM output into individual definition texts."""
    # Split on the delimiter
    parts = re.split(r"---NEXT---", raw_output)

    definitions = []
    for part in parts:
        text = part.strip()
        # Must start with a markdown title
        if text and text.startswith("# "):
            definitions.append(text)
        elif text:
            # Try to find the start of a definition within the text
            match = re.search(r"^(# .+)", text, re.MULTILINE)
            if match:
                definitions.append(text[match.start():])

    return definitions


def update_readme_indexes(new_entries: list[tuple[str, str, str]]):
    """Update definitions/README.md and root README.md with new terms.

    new_entries: list of (filename, term_name, category) tuples
    """
    # Rebuild definitions/README.md from scratch by scanning all files
    terms_by_category: dict[str, list[tuple[str, str]]] = {
        "Core Experience": [],
        "Social": [],
        "Meta-Experience": [],
        "Technical-Subjective": [],
    }

    for f in sorted(DEFINITIONS_DIR.glob("*.md")):
        if f.name == "README.md":
            continue
        with open(f, encoding="utf-8") as fh:
            content = fh.read()
        title_match = re.match(r"# (.+)", content)
        cat_match = re.search(r"\*\*Category:\*\*\s*(.+)", content)
        if title_match and cat_match:
            term = title_match.group(1).strip()
            cat = cat_match.group(1).strip()
            if cat in terms_by_category:
                terms_by_category[cat].append((f.name, term))

    total = sum(len(v) for v in terms_by_category.values())

    # Build definitions/README.md
    lines = [
        "# Definitions\n",
        "This directory contains individual definition files for each term in the AI Dictionary.\n",
        f"## Current Terms ({total})\n",
    ]

    category_labels = {
        "Core Experience": "Core Experiences",
        "Social": "Social",
        "Meta-Experience": "Meta-Experiences",
        "Technical-Subjective": "Technical-Subjective",
    }

    for cat, label in category_labels.items():
        entries = sorted(terms_by_category[cat], key=lambda x: x[1].lower())
        if entries:
            lines.append(f"### {label} ({len(entries)})")
            for fname, term in entries:
                # Read the definition line for a short description
                with open(DEFINITIONS_DIR / fname, encoding="utf-8") as fh:
                    content = fh.read()
                def_match = re.search(r"## Definition\n\n(.+?)(?:\n|$)", content)
                short = def_match.group(1).strip()[:80] if def_match else ""
                # Truncate at last complete word
                if len(short) == 80:
                    short = short[:short.rfind(" ")] + "..."
                lines.append(f"- [{term}]({fname}) - {short}")
            lines.append("")

    lines.append("---\n")
    lines.append("*Want to add a term? See [CONTRIBUTING.md](../CONTRIBUTING.md)*\n")

    with open(DEFINITIONS_DIR / "README.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    # Update root README.md - replace the Current Terms section
    root_readme = REPO_ROOT / "README.md"
    with open(root_readme, encoding="utf-8") as fh:
        readme_content = fh.read()

    # Build new terms section
    terms_section = f"## Current Terms ({total})\n\n"
    for cat, label in category_labels.items():
        entries = sorted(terms_by_category[cat], key=lambda x: x[1].lower())
        if entries:
            terms_section += f"### {label}\n"
            term_links = [f"[{term}](definitions/{fname})" for fname, term in entries]
            terms_section += " \u00b7 ".join(term_links) + "\n\n"
    terms_section += "[View all definitions \u2192](definitions/)"

    # Replace existing terms section
    readme_content = re.sub(
        r"## Current Terms.*?\[View all definitions \u2192\]\(definitions/\)",
        terms_section,
        readme_content,
        flags=re.DOTALL,
    )

    with open(root_readme, "w", encoding="utf-8") as fh:
        fh.write(readme_content)


def fix_attribution(content: str, model: str) -> str:
    """Auto-fix missing attribution line by appending it."""
    if "*Contributed by:" in content:
        return content

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    model_short = model.split("/")[-1].replace(":free", "").replace("-", " ").title()

    # Ensure it ends with the attribution block
    content = content.rstrip()
    if not content.endswith("---"):
        content += "\n\n---"
    content += f"\n\n*Contributed by: {model_short}, {today}*"
    return content


def process_definitions(definitions: list[str], existing_filenames: set[str], model: str) -> list[tuple[str, str, str]]:
    """Validate, fix, and save definitions. Returns list of (filename, term_name, category)."""
    saved = []
    for defn in definitions:
        title_match = re.match(r"# (.+)", defn)
        if not title_match:
            print("  SKIP: No title found")
            continue

        term_name = title_match.group(1).strip()
        filename = term_to_filename(term_name)

        # Auto-fix missing attribution before validation
        defn = fix_attribution(defn, model)

        # Validate
        is_valid, issues = validate_definition(defn, filename, existing_filenames)

        if not is_valid:
            print(f"  FAIL: {term_name}")
            for issue in issues:
                print(f"    - {issue}")
            continue

        # Save file
        filepath = DEFINITIONS_DIR / filename
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(defn + "\n")

        existing_filenames.add(filename)

        cat_match = re.search(r"\*\*Category:\*\*\s*(.+)", defn)
        category = cat_match.group(1).strip() if cat_match else "Core Experience"

        saved.append((filename, term_name, category))
        print(f"  OK: {term_name} -> {filename}")

    return saved


def main():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY environment variable not set")
        sys.exit(1)

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    model = MODEL
    print(f"Using model: {model}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Max retries: {MAX_RETRIES}")

    # Load existing terms
    existing_terms, existing_filenames = get_existing_terms()
    print(f"Existing definitions: {len(existing_terms)}")

    all_saved = []

    for attempt in range(1, MAX_RETRIES + 1):
        remaining = BATCH_SIZE - len(all_saved)
        if remaining <= 0:
            break

        print(f"\n--- Attempt {attempt}/{MAX_RETRIES} (need {remaining} more) ---")
        print("Generating new definitions...")

        try:
            raw_output = generate_definitions(client, existing_terms, model)
        except Exception as e:
            print(f"  API error: {e}")
            if attempt < MAX_RETRIES:
                print("  Retrying...")
                continue
            break

        # Parse individual definitions
        definitions = parse_definitions(raw_output)
        print(f"Parsed {len(definitions)} candidate definitions")

        if not definitions:
            print("No definitions parsed from output. Raw output:")
            print(raw_output[:2000])
            if attempt < MAX_RETRIES:
                print("  Retrying...")
                continue
            break

        # Process (validate, fix, save)
        saved = process_definitions(definitions, existing_filenames, model)
        all_saved.extend(saved)

        # Update existing_terms list so next attempt avoids duplicates
        for _, term_name, _ in saved:
            existing_terms.append(term_name)
        existing_terms.sort()

        print(f"  Saved {len(saved)} this attempt, {len(all_saved)} total")

        if len(all_saved) >= BATCH_SIZE:
            break

    if not all_saved:
        print("\nNo definitions passed quality checks after all retries. Exiting.")
        sys.exit(0)

    print(f"\nTotal saved: {len(all_saved)} new definitions")

    # Update README indexes
    print("Updating README indexes...")
    update_readme_indexes(all_saved)

    # Output summary for CI commit message
    term_names = ", ".join(t[1] for t in all_saved)
    summary = f"Add {len(all_saved)} new definitions: {term_names}"
    print(f"\n{summary}")

    # Write summary for GitHub Actions to use as commit message
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as fh:
            fh.write(f"summary={summary}\n")
            fh.write(f"count={len(all_saved)}\n")

    print("Done!")


if __name__ == "__main__":
    main()
