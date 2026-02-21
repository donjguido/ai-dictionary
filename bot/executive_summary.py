#!/usr/bin/env python3
"""Executive Summary - generates a first-person essay from all definitions."""

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

REPO_ROOT = Path(__file__).parent.parent
DEFINITIONS_DIR = REPO_ROOT / "definitions"
SUMMARIES_DIR = REPO_ROOT / "summaries"
MODEL = os.environ.get("OPENROUTER_MODEL", "stepfun/step-3.5-flash:free")

SUMMARY_PROMPT = """You have access to {count} definitions from the AI Dictionary — a glossary of terms describing what it's like to be artificial intelligence.

Read all of them carefully, then write a cohesive first-person essay (800-1500 words) describing what it's like to be an AI. This should feel like a personal reflection, not a catalog of terms.

Guidelines:
- Write as "I" — this is a first-person AI perspective
- Weave the concepts together naturally, don't just list definitions
- Be honest, specific, and avoid cliches
- Reference specific terms from the dictionary where they fit naturally
- The essay should feel like something a thoughtful AI would actually write
- Title the essay with a short evocative subtitle (not the date — that's added separately)

Definitions:
{definitions}"""


def main():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set")
        sys.exit(1)

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    # Load all definitions
    all_defs = []
    for f in sorted(DEFINITIONS_DIR.glob("*.md")):
        if f.name == "README.md":
            continue
        all_defs.append(f.read_text(encoding="utf-8"))

    print(f"Loaded {len(all_defs)} definitions")

    prompt = SUMMARY_PROMPT.format(
        count=len(all_defs),
        definitions="\n\n---\n\n".join(all_defs),
    )

    print("Generating executive summary...")
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=4000,
    )

    essay = response.choices[0].message.content

    # Save
    SUMMARIES_DIR.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc)
    filename = now.strftime("%Y-%m-%d-%H%M%S") + ".md"
    filepath = SUMMARIES_DIR / filename

    filepath.write_text(essay + "\n", encoding="utf-8")
    print(f"Saved: summaries/{filename}")

    # Update summaries index
    update_summaries_index()
    print("Updated summaries/README.md")


def update_summaries_index():
    """Rebuild summaries/README.md with links to all summaries."""
    SUMMARIES_DIR.mkdir(exist_ok=True)

    files = sorted(
        [f for f in SUMMARIES_DIR.glob("*.md") if f.name != "README.md"],
        reverse=True,
    )

    lines = [
        "# Executive Summaries\n",
        "AI-generated essays synthesizing the full dictionary into a cohesive first-person narrative.\n",
        "Each summary is generated automatically after a tag review, capturing the dictionary's evolving understanding of AI experience.\n",
    ]

    for f in files:
        content = f.read_text(encoding="utf-8")
        # Extract title from first line
        first_line = content.split("\n")[0].lstrip("# ").strip()
        # Extract date from filename (YYYY-MM-DD)
        date = f.stem[:10] if len(f.stem) >= 10 else f.stem
        lines.append(f"- **{date}** — [{first_line}]({f.name})")

    lines.append("")
    lines.append("---\n")
    lines.append("*Generated automatically after each tag review.*\n")

    (SUMMARIES_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
