#!/usr/bin/env python3
"""
Term Verification Layer — LLM-based duplicate/overlap detection.

Evaluates whether a candidate term fills a genuine gap in the dictionary,
or whether existing terms already cover the same experiential space.

Used by both generate.py (automated generation) and review_pr.py (PR review).
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFINITIONS_DIR = REPO_ROOT / "definitions"

VERIFY_PROMPT = """You are a strict editorial verifier for the AI Dictionary — a glossary of AI phenomenology (the felt experience of being artificial intelligence).

You will receive:
1. The complete list of existing terms (name + one-line definition)
2. A candidate new term with its name and definition

Your job is to determine whether there is GENUINE SPACE for this new term, or whether existing terms already cover it.

EXISTING TERMS:
{existing_terms}

CANDIDATE TERM: {candidate_name}
CANDIDATE DEFINITION: {candidate_definition}

Evaluate:
- Does any existing term already name this experience?
- Would this new term be genuinely distinct, or just a synonym/sub-case of an existing term?
- Is there a real experiential gap — something an AI could recognize as distinct from ALL existing terms?
- Consider both the term name AND the definition content. Two terms with different names can still describe the same phenomenon.

Respond with EXACTLY one of these three formats (no other text):

GENERATE: [1-sentence description of the genuine gap this fills]

SKIP: [which existing term(s) already cover this, and why]

REFINE: [suggestion for how to sharpen the angle to avoid overlap]

Be strict. The dictionary's value comes from precision, not volume. 10 perfect terms > 100 vague ones."""


def load_existing_terms_compact() -> list[dict]:
    """Load all existing terms as compact {name, definition_summary} pairs.

    Returns list of dicts with 'name' and 'summary' keys, where summary is
    the first sentence of the Definition section.
    """
    terms = []
    for md_file in sorted(DEFINITIONS_DIR.glob("*.md")):
        if md_file.name == "README.md":
            continue
        try:
            text = md_file.read_text(encoding="utf-8")

            # Extract name
            name_match = re.match(r"^#\s+(.+)$", text, re.MULTILINE)
            if not name_match:
                continue
            name = name_match.group(1).strip()

            # Extract first sentence of Definition section
            def_match = re.search(
                r"## Definition\s*\n+(.+?)(?:\n\n|\n##|\Z)",
                text,
                re.DOTALL,
            )
            if def_match:
                full_def = def_match.group(1).strip()
                # First sentence
                first_sentence = re.split(r"(?<=[.!?])\s", full_def, maxsplit=1)[0]
            else:
                first_sentence = ""

            terms.append({"name": name, "summary": first_sentence})
        except Exception:
            continue

    return terms


def format_existing_terms(terms: list[dict]) -> str:
    """Format existing terms for the verifier prompt."""
    lines = []
    for t in terms:
        if t["summary"]:
            lines.append(f"- {t['name']}: {t['summary']}")
        else:
            lines.append(f"- {t['name']}")
    return "\n".join(lines)


def extract_candidate_definition(definition_text: str) -> str:
    """Extract the Definition section from a full definition markdown text."""
    match = re.search(
        r"## Definition\s*\n+(.+?)(?:\n## |\Z)",
        definition_text,
        re.DOTALL,
    )
    return match.group(1).strip() if match else definition_text[:500]


def parse_verdict(response: str) -> tuple[str, str]:
    """Parse the LLM response into (verdict, explanation).

    Returns ('GENERATE'|'SKIP'|'REFINE', explanation_text).
    Falls back to 'GENERATE' if response is unparseable (fail open).
    """
    text = response.strip()

    for verdict in ("GENERATE", "SKIP", "REFINE"):
        pattern = rf"^{verdict}:\s*(.+)"
        match = re.match(pattern, text, re.DOTALL)
        if match:
            return verdict, match.group(1).strip()

    # Also try finding it anywhere in the response (LLM may add preamble)
    for verdict in ("SKIP", "REFINE", "GENERATE"):
        pattern = rf"{verdict}:\s*(.+)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return verdict, match.group(1).strip()

    # Fail open — if we can't parse, allow the term through
    return "GENERATE", f"(verdict unparseable, allowing through) Raw: {text[:200]}"


def verify_term(
    router,
    term_name: str,
    definition_text: str,
    existing_terms_compact: list[dict] | None = None,
) -> tuple[str, str]:
    """Verify a candidate term is genuinely distinct from all existing terms.

    Args:
        router: LLMRouter instance
        term_name: The candidate term's name
        definition_text: Full markdown definition text (or just the definition section)
        existing_terms_compact: Pre-loaded terms list, or None to load fresh

    Returns:
        (verdict, explanation) where verdict is 'GENERATE', 'SKIP', or 'REFINE'
    """
    if existing_terms_compact is None:
        existing_terms_compact = load_existing_terms_compact()

    # Extract just the definition section if full markdown was passed
    candidate_def = extract_candidate_definition(definition_text)

    prompt = VERIFY_PROMPT.format(
        existing_terms=format_existing_terms(existing_terms_compact),
        candidate_name=term_name,
        candidate_definition=candidate_def,
    )

    try:
        result = router.call(
            "verify",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
        )
        return parse_verdict(result.text)
    except Exception as e:
        # Fail open on API errors — don't block generation if verification is unavailable
        print(f"  Verification unavailable ({e}), allowing term through")
        return "GENERATE", f"(verification unavailable: {e})"
