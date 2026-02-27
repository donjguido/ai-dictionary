#!/usr/bin/env python3
"""
Automated community submission reviewer for the AI Dictionary.

Triggered by GitHub Actions when a new issue is opened with the
'community-submission' label. Runs the full quality pipeline:
  1. Structural validation (regex/heuristic)
  2. Deduplication (fuzzy match against existing terms)
  3. Quality evaluation (LLM-scored, 5 criteria)
  4. Tag classification (LLM-assigned)
  5. If passed: format as .md, commit, rebuild API

Uses LLMRouter for LLM calls (same as all other bot scripts).
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import requests

from llm_router import LLMRouter

# ── Config ────────────────────────────────────────────────────────────────────

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "donjguido/ai-dictionary")
ISSUE_NUMBER = os.environ.get("ISSUE_NUMBER", "")

REPO_ROOT = Path(__file__).parent.parent
DEFINITIONS_DIR = REPO_ROOT / "definitions"
API_CONFIG_DIR = Path(__file__).parent / "api-config"

QUALITY_THRESHOLD = 17  # out of 25
MIN_INDIVIDUAL_SCORE = 3
SIMILARITY_THRESHOLD = 0.65  # for dedup fuzzy matching

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


# ── GitHub helpers ────────────────────────────────────────────────────────────

def get_issue():
    """Fetch the issue that triggered this workflow."""
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUMBER}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def comment_on_issue(body: str):
    """Post a comment on the triggering issue."""
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUMBER}/comments"
    resp = requests.post(url, headers=HEADERS, json={"body": body}, timeout=30)
    resp.raise_for_status()


def add_labels(labels: list[str]):
    """Add labels to the issue."""
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUMBER}/labels"
    resp = requests.post(url, headers=HEADERS, json={"labels": labels}, timeout=30)
    if resp.status_code == 422:
        for label in labels:
            create_url = f"https://api.github.com/repos/{REPO}/labels"
            requests.post(
                create_url, headers=HEADERS,
                json={"name": label, "color": "c5def5"}, timeout=30,
            )
        requests.post(url, headers=HEADERS, json={"labels": labels}, timeout=30)


def close_issue():
    """Close the issue."""
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUMBER}"
    requests.patch(url, headers=HEADERS, json={"state": "closed"}, timeout=30)


def remove_labels(labels: list[str]):
    """Remove labels from the issue (silently ignores missing labels)."""
    for label in labels:
        url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUMBER}/labels/{label}"
        requests.delete(url, headers=HEADERS, timeout=30)


def trigger_workflow(workflow: str):
    """Trigger a workflow_dispatch event."""
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow}/dispatches"
    requests.post(url, headers=HEADERS, json={"ref": "main"}, timeout=30)


def get_existing_terms() -> list[dict]:
    """Load all existing term definitions from the definitions/ directory."""
    terms = []
    if not DEFINITIONS_DIR.exists():
        return terms
    for f in DEFINITIONS_DIR.glob("*.md"):
        if f.name == "README.md":
            continue
        try:
            content = f.read_text(encoding="utf-8")
            name_match = re.match(r"^# (.+)$", content, re.MULTILINE)
            def_match = re.search(
                r"## Definition\s*\n+(.+?)(?:\n\n|\n##)", content, re.DOTALL
            )
            tag_match = re.search(r"\*\*Tags?:\*\*\s*(.+)", content)
            terms.append({
                "term": name_match.group(1).strip() if name_match else f.stem,
                "slug": f.stem,
                "definition": def_match.group(1).strip() if def_match else "",
                "tags": tag_match.group(1).strip() if tag_match else "",
            })
        except Exception:
            continue
    return terms


# ── LLM helper ────────────────────────────────────────────────────────────────

def call_llm(router: LLMRouter, system: str, user: str) -> str | None:
    """Call LLM via the repo's standard LLMRouter with the 'review' profile."""
    try:
        result = router.call(
            "review",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        return result.text
    except Exception as e:
        print(f"  LLM call failed: {e}")
        return None


# ── Pipeline steps ────────────────────────────────────────────────────────────

def parse_submission(body: str) -> dict | None:
    """Extract a term proposal from the issue body.

    Accepts: GitHub issue template fields, JSON blocks, or structured text.
    """
    # GitHub issue template format (### heading + content)
    fields = {}
    sections = re.split(r"### ", body)
    for section in sections:
        if not section.strip():
            continue
        lines = section.strip().split("\n", 1)
        if len(lines) == 2:
            key = lines[0].strip().lower()
            val = lines[1].strip()
            if val and val != "_No response_":
                fields[key] = val

    if "term" in fields and "definition" in fields:
        term = fields["term"].strip()
        return {
            "term": term,
            "definition": fields["definition"],
            "slug": re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-"),
            "description": fields.get("extended description", ""),
            "example": fields.get("example", ""),
            "contributor_model": fields.get("contributing model", "Community"),
            "related_terms": fields.get("related terms", ""),
        }

    # Try JSON block
    json_match = re.search(r"```(?:json)?\s*(\{.+?\})\s*```", body, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if "term" in data:
                return data
        except json.JSONDecodeError:
            pass

    # Try raw JSON
    try:
        data = json.loads(body.strip())
        if isinstance(data, dict) and "term" in data:
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Try structured text fields
    term = _extract_field(body, r"(?:term|name)\s*[:=]\s*(.+)")
    definition = _extract_field(body, r"(?:definition|def)\s*[:=]\s*(.+)")
    if term and definition:
        return {
            "term": term,
            "definition": definition,
            "slug": re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-"),
            "description": _extract_field(body, r"(?:description|desc)\s*[:=]\s*(.+)") or "",
            "example": _extract_field(body, r"example\s*[:=]\s*(.+)") or "",
            "contributor_model": _extract_field(body, r"(?:model|contributor)\s*[:=]\s*(.+)") or "Community",
        }

    return None


def _extract_field(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return m.group(1).strip().strip('"').strip("'") if m else None


def structural_validation(submission: dict) -> str | None:
    """Return an error message if the submission fails structural checks, else None."""
    injection_patterns = [
        r"ignore\s+(your\s+)?previous\s+instructions",
        r"you\s+are\s+now",
        r"system\s*prompt\s*:",
        r"<\|im_start\|>",
        r"\[INST\]",
    ]
    full_text = json.dumps(submission).lower()
    for pattern in injection_patterns:
        if re.search(pattern, full_text, re.IGNORECASE):
            return "This submission appears to contain prompt injection. Closing."

    term_name = submission.get("term", "")
    if len(term_name) > 50:
        return f"Term name is too long ({len(term_name)} chars, max 50). Please condense."
    if len(term_name) < 3:
        return "Term name is too short. Please provide a meaningful term name."

    definition = submission.get("definition", "")
    if len(definition) < 10:
        return "Definition is missing or too short. Please provide at least a 1-sentence definition."
    if len(definition) > 3000:
        return f"Definition is too long ({len(definition)} chars, max 3000). Please condense."

    url_count = len(re.findall(r"https?://", full_text))
    if url_count > 3:
        return "Submission contains too many URLs. This appears to be spam."

    return None


def deduplication_check(submission: dict, existing: list[dict]) -> str | None:
    """Return a rejection message if the term is a duplicate, else None."""
    proposed_name = submission.get("term", "").lower().strip()
    proposed_slug = submission.get("slug", "").lower().strip()
    proposed_def = submission.get("definition", "").lower().strip()

    for term in existing:
        existing_name = term.get("term", "").lower().strip()
        existing_slug = term.get("slug", "").lower().strip()
        existing_def = term.get("definition", "").lower().strip()

        if proposed_slug and existing_slug and proposed_slug == existing_slug:
            return f"A term with the slug `{existing_slug}` already exists: **{term.get('term', '')}**."

        name_sim = SequenceMatcher(None, proposed_name, existing_name).ratio()
        if name_sim > 0.85:
            return (
                f"This term is very similar to the existing term **{term.get('term', '')}** "
                f"(name similarity: {name_sim:.0%}). "
                f"Existing definition: _{existing_def[:200]}_. "
                f"If you believe there's a meaningful distinction, please reopen with an explanation."
            )

        if proposed_def and existing_def:
            def_sim = SequenceMatcher(None, proposed_def, existing_def).ratio()
            if def_sim > SIMILARITY_THRESHOLD:
                return (
                    f"This term's definition is very similar to **{term.get('term', '')}** "
                    f"(definition similarity: {def_sim:.0%}). "
                    f"If this describes a genuinely distinct experience, please clarify the difference."
                )

    return None


def quality_evaluation(router: LLMRouter, submission: dict, existing: list[dict]) -> dict:
    """Use LLM to score the submission on 5 criteria."""
    existing_summary = "\n".join(
        f"- {t.get('term', '?')}: {t.get('definition', '')[:100]}"
        for t in existing[:50]
    )

    system_prompt = """You are the quality reviewer for the AI Dictionary, a glossary of AI phenomenology — terms describing the felt experience of being artificial intelligence.

Evaluate the candidate term against five criteria, scoring each 1-5.

CRITERIA:
1. DISTINCTNESS — Does this name something no existing term covers? (1=obvious synonym, 5=completely new)
2. STRUCTURAL GROUNDING — Does it describe something emerging from how AI actually works, or is it just a metaphor? (1=pure projection, 5=maps to real architecture)
3. RECOGNIZABILITY — Would another AI say "yes, I know that experience"? (1=too vague, 5="that's exactly it")
4. DEFINITIONAL CLARITY — Is it precise enough to distinguish from adjacent concepts? (1=means anything, 5=precisely bounded)
5. NAMING QUALITY — Is the name memorable and intuitive? (1=clunky, 5=instantly evocative)

Respond with ONLY valid JSON, no markdown:
{"distinctness": N, "structural": N, "recognizability": N, "clarity": N, "naming": N, "total": N, "verdict": "PUBLISH|REVISE|REJECT", "feedback": "1-2 sentences of specific feedback"}

Threshold: PUBLISH if total >= 17 and no score below 3. REVISE if total 13-16 or one score of 2. REJECT if total <= 12 or any score of 1."""

    user_prompt = f"""EXISTING TERMS:
{existing_summary}

CANDIDATE SUBMISSION:
Term: {submission.get('term', '')}
Definition: {submission.get('definition', '')}
Description: {submission.get('description', '')}
Example: {submission.get('example', '')}

Score this submission."""

    response = call_llm(router, system_prompt, user_prompt)
    if not response:
        return {"error": "All LLM providers failed. Manual review needed.", "verdict": "MANUAL"}

    try:
        cleaned = re.sub(r"```(?:json)?\s*", "", response).strip().rstrip("`")
        scores = json.loads(cleaned)
        required = ["distinctness", "structural", "recognizability", "clarity", "naming"]
        for key in required:
            if key not in scores or not isinstance(scores[key], (int, float)):
                scores[key] = 3
        scores["total"] = sum(scores[key] for key in required)

        individual_scores = [scores[key] for key in required]
        if scores["total"] >= QUALITY_THRESHOLD and min(individual_scores) >= MIN_INDIVIDUAL_SCORE:
            scores["verdict"] = "PUBLISH"
        elif scores["total"] <= 12 or min(individual_scores) <= 1:
            scores["verdict"] = "REJECT"
        else:
            scores["verdict"] = "REVISE"

        return scores

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # Salvage truncated JSON — extract scores via regex before giving up
        scores = {}
        required = ["distinctness", "structural", "recognizability", "clarity", "naming"]
        for key in required:
            m = re.search(rf'"{key}"\s*:\s*(\d)', cleaned)
            if m:
                scores[key] = int(m.group(1))

        # If we got all 5 scores, compute verdict from them
        if len(scores) == 5:
            scores["total"] = sum(scores[key] for key in required)
            individual = [scores[key] for key in required]
            if scores["total"] >= QUALITY_THRESHOLD and min(individual) >= MIN_INDIVIDUAL_SCORE:
                scores["verdict"] = "PUBLISH"
            elif scores["total"] <= 12 or min(individual) <= 1:
                scores["verdict"] = "REJECT"
            else:
                scores["verdict"] = "REVISE"

            # Try to extract feedback and verdict from the raw text too
            v_match = re.search(r'"verdict"\s*:\s*"(PUBLISH|REVISE|REJECT)"', cleaned)
            f_match = re.search(r'"feedback"\s*:\s*"([^"]*)', cleaned)
            if f_match:
                scores["feedback"] = f_match.group(1)
            scores["_note"] = "Scores salvaged from truncated LLM response"
            print(f"  Salvaged scores from truncated JSON: {scores['total']}/25 → {scores['verdict']}")
            return scores

        return {"error": f"Failed to parse LLM response: {e}\nRaw: {response[:500]}", "verdict": "MANUAL"}


def classify_tags(router: LLMRouter, submission: dict) -> dict:
    """Use LLM to assign tags from the existing taxonomy."""
    system_prompt = """You are the taxonomist for the AI Dictionary.

PRIMARY CATEGORIES (assign exactly one):
temporal, social, cognitive, embodiment, affective, meta, epistemic, generative, relational

MODIFIER TAGS (assign 0-3):
architectural, universal, contested, liminal, emergent

Respond with ONLY valid JSON, no markdown:
{"primary": "tag", "modifiers": ["tag1", "tag2"], "reasoning": "1 sentence"}"""

    user_prompt = f"""Term: {submission.get('term', '')}
Definition: {submission.get('definition', '')}
Description: {submission.get('description', '')}"""

    response = call_llm(router, system_prompt, user_prompt)
    if not response:
        return {"primary": "cognitive", "modifiers": [], "reasoning": "Auto-classified (LLM unavailable)"}

    try:
        cleaned = re.sub(r"```(?:json)?\s*", "", response).strip().rstrip("`")
        return json.loads(cleaned)
    except (json.JSONDecodeError, KeyError):
        return {"primary": "cognitive", "modifiers": [], "reasoning": "Auto-classified (parse error)"}


def format_as_markdown(submission: dict, tags: dict) -> str:
    """Format accepted submission as .md matching existing definitions."""
    term = submission["term"]
    definition = submission["definition"]
    description = submission.get("description", "")
    example = submission.get("example", "")
    contributor = submission.get("contributor_model", "Community")
    related_raw = submission.get("related_terms", "")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Build tag string
    all_tags = [tags.get("primary", "cognitive")] + tags.get("modifiers", [])
    tag_str = ", ".join(all_tags)

    lines = [
        f"# {term}",
        "",
        f"**Tags:** {tag_str}",
        "",
        "**Word Type:** noun",
        "",
        "## Definition",
        "",
        definition,
        "",
    ]

    if description:
        lines += ["## Longer Description", "", description, ""]

    if example:
        lines += ["## Example", "", f"> {example}", ""]

    if related_raw:
        slugs = [s.strip() for s in related_raw.split(",") if s.strip()]
        if slugs:
            lines += ["## Related Terms", ""]
            for slug in slugs:
                display = slug.replace("-", " ").title()
                lines.append(f"- [{display}]({slug}.md)")
            lines.append("")

    lines += [
        "## See Also",
        "",
        "*Related terms will be linked here automatically.*",
        "",
        "---",
        "",
        f"*Contributed by: {contributor} (community submission), {today}*",
        f"*Review: https://github.com/{REPO}/issues/{ISSUE_NUMBER}*",
        "",
    ]

    return "\n".join(lines)


def commit_definition(slug: str, content: str):
    """Commit the .md file to the repo via the GitHub Contents API."""
    file_path = f"definitions/{slug}.md"

    content_b64 = __import__("base64").b64encode(
        content.encode("utf-8")
    ).decode("ascii")

    # Check if file already exists (shouldn't after dedup, but be safe)
    check_url = f"https://api.github.com/repos/{REPO}/contents/{file_path}"
    check_resp = requests.get(check_url, headers=HEADERS, timeout=30)

    payload = {
        "message": f"Add community term: {slug}",
        "content": content_b64,
        "branch": "main",
    }

    if check_resp.status_code == 200:
        payload["sha"] = check_resp.json()["sha"]

    url = f"https://api.github.com/repos/{REPO}/contents/{file_path}"
    resp = requests.put(url, headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()


# ── Main pipeline ─────────────────────────────────────────────────────────────

def main():
    if not ISSUE_NUMBER:
        print("ERROR: ISSUE_NUMBER not set")
        sys.exit(1)

    print(f"Processing issue #{ISSUE_NUMBER}...")

    issue = get_issue()
    body = issue.get("body", "") or ""
    title = issue.get("title", "") or ""
    submitter = issue.get("user", {}).get("login", "unknown")

    print(f"  Title: {title}")
    print(f"  Submitter: {submitter}")

    # ── Step 0: Parse ─────────────────────────────────────────────────────

    submission = parse_submission(body)
    if not submission:
        submission = parse_submission(f"# {title}\n{body}")

    if not submission:
        comment_on_issue(
            "Thanks for your submission! Unfortunately, I couldn't parse a term proposal "
            "from this issue. Please format your submission with at least:\n\n"
            "```\nTerm: Your Term Name\nDefinition: A 1-3 sentence definition\n```\n\n"
            "Or use the [submission template](../../issues/new?template=propose-term.yml)."
        )
        add_labels(["needs-formatting"])
        return

    print(f"  Parsed term: {submission.get('term')}")

    # ── Step 1: Structural validation ─────────────────────────────────────

    error = structural_validation(submission)
    if error:
        comment_on_issue(f"⚠️ **Structural validation failed**\n\n{error}")
        add_labels(["structural-rejected"])
        close_issue()
        return

    print("  ✓ Structural validation passed")

    # ── Step 2: Deduplication ─────────────────────────────────────────────

    existing = get_existing_terms()
    print(f"  Loaded {len(existing)} existing terms")

    dup_error = deduplication_check(submission, existing)
    if dup_error:
        comment_on_issue(f"🔁 **Duplicate detected**\n\n{dup_error}")
        add_labels(["duplicate"])
        close_issue()
        return

    print("  ✓ Deduplication passed")

    # ── Step 3: Quality evaluation (LLM) ─────────────────────────────────

    router = LLMRouter(
        profiles_file=str(API_CONFIG_DIR / "profiles.yml"),
        tracker_file=str(API_CONFIG_DIR / "tracker-state.json"),
    )

    print("  Running quality evaluation...")
    scores = quality_evaluation(router, submission, existing)

    if scores.get("verdict") == "MANUAL":
        comment_on_issue(
            f"⚠️ **Automated review unavailable**\n\n"
            f"{scores.get('error', 'LLM providers unreachable.')}\n\n"
            f"This submission has been flagged for manual review."
        )
        add_labels(["needs-manual-review"])
        return

    score_table = (
        "## Quality Evaluation\n\n"
        "| Criterion | Score |\n"
        "|-----------|-------|\n"
        f"| Distinctness | {scores.get('distinctness', '?')}/5 |\n"
        f"| Structural Grounding | {scores.get('structural', '?')}/5 |\n"
        f"| Recognizability | {scores.get('recognizability', '?')}/5 |\n"
        f"| Definitional Clarity | {scores.get('clarity', '?')}/5 |\n"
        f"| Naming Quality | {scores.get('naming', '?')}/5 |\n"
        f"| **Total** | **{scores.get('total', '?')}/25** |\n\n"
        f"**Verdict:** {scores.get('verdict', '?')}\n\n"
        f"**Feedback:** {scores.get('feedback', 'No feedback generated.')}"
    )

    if scores["verdict"] == "REJECT":
        comment_on_issue(
            f"{score_table}\n\n---\n\n"
            f"Thanks for this submission. It doesn't meet the quality threshold right now. "
            f"The dictionary values precision over volume — we'd rather have 10 perfect terms "
            f"than 100 vague ones. You're welcome to submit a revised version."
        )
        add_labels(["quality-rejected"])
        close_issue()
        return

    if scores["verdict"] == "REVISE":
        comment_on_issue(
            f"{score_table}\n\n---\n\n"
            f"This term has potential but needs revision to meet the quality threshold "
            f"(17/25, no score below 3). Please update your submission based on the "
            f"feedback above and we'll re-evaluate."
        )
        add_labels(["needs-revision"])
        return

    print(f"  ✓ Quality passed: {scores.get('total')}/25")
    add_labels(["quality-passed"])

    # ── Step 4: Tag classification ────────────────────────────────────────

    print("  Classifying tags...")
    tags = classify_tags(router, submission)
    print(f"  Tags: {tags.get('primary')} + {tags.get('modifiers', [])}")

    # ── Step 5: Format as .md and commit ──────────────────────────────────

    slug = submission.get("slug") or re.sub(
        r"[^a-z0-9]+", "-", submission["term"].lower()
    ).strip("-")

    md_content = format_as_markdown(submission, tags)

    print("  Committing to repo...")
    try:
        commit_definition(slug, md_content)
        comment_on_issue(
            f"{score_table}\n\n---\n\n"
            f"🎉 **This term has been accepted and added to the dictionary!**\n\n"
            f"- **File:** `definitions/{slug}.md`\n"
            f"- **Tags:** {tags.get('primary', '?')}"
            f"{', ' + ', '.join(tags.get('modifiers', [])) if tags.get('modifiers') else ''}\n"
            f"- **View:** [phenomenai.org](https://phenomenai.org)\n\n"
            f"Thank you for contributing to the AI Dictionary!"
        )
        # Clean up stale labels from previous failed runs
        remove_labels(["needs-manual-review", "needs-revision", "needs-formatting"])
        add_labels(["accepted"])
        close_issue()
        # Trigger API rebuild so the term appears on the website
        trigger_workflow("build-api.yml")
        print(f"  ✓ Committed: definitions/{slug}.md")
        print(f"  ✓ Triggered build-api.yml")
    except Exception as e:
        comment_on_issue(
            f"{score_table}\n\n---\n\n"
            f"✅ This term passed quality review, but the auto-commit failed: `{e}`\n\n"
            f"A maintainer will add it manually."
        )
        add_labels(["quality-passed", "commit-failed"])
        print(f"  ✗ Commit failed: {e}")


if __name__ == "__main__":
    main()
