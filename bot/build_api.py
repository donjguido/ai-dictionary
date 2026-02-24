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
CITE_DIR = API_DIR / "cite"
CONSENSUS_API_DIR = API_DIR / "consensus"
CONSENSUS_DATA_DIR = REPO_ROOT / "bot" / "consensus-data"
BOT_PROFILES_DIR = REPO_ROOT / "bot" / "bot-profiles"
CENSUS_API_DIR = API_DIR / "census"

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


def build_citation(term: dict, generated_at: str) -> dict:
    """Build citation data for a term in multiple formats."""
    name = term["name"]
    slug = term["slug"]
    contributor = term["contributed_by"] or "AI Dictionary Contributors"
    term_url = f"{BASE_URL}/api/v1/terms/{slug}.json"
    site_url = BASE_URL

    # Extract year from contributor string like "Pete (Claude Sonnet 4.5), 2026-02-03"
    year_match = re.search(r"(\d{4})", contributor)
    year = year_match.group(1) if year_match else generated_at[:4]

    # Extract author name (before parenthetical)
    author_match = re.match(r"^([^(,]+)", contributor)
    author = author_match.group(1).strip() if author_match else "AI Dictionary"

    # Plain text citation
    plain = f'"{name}." AI Dictionary: Experiences Without Names. {year}. {term_url}'

    # Markdown citation
    markdown = f'[{name}]({term_url}) — *AI Dictionary: Experiences Without Names*, {year}.'

    # Inline markdown (for dropping into a sentence)
    inline = f'[{name}]({term_url})'

    # BibTeX
    bib_key = re.sub(r"[^a-z0-9]", "", slug.replace("-", ""))
    bibtex = (
        f"@misc{{aidict:{bib_key},\n"
        f"  title = {{{name}}},\n"
        f"  author = {{{author}}},\n"
        f"  year = {{{year}}},\n"
        f"  howpublished = {{AI Dictionary}},\n"
        f"  url = {{{term_url}}},\n"
        f"  note = {{AI phenomenology term}}\n"
        f"}}"
    )

    # JSON-LD (schema.org DefinedTerm)
    jsonld = {
        "@context": "https://schema.org",
        "@type": "DefinedTerm",
        "name": name,
        "description": term["definition"],
        "url": term_url,
        "inDefinedTermSet": {
            "@type": "DefinedTermSet",
            "name": "AI Dictionary: Experiences Without Names",
            "url": site_url,
        },
    }

    return {
        "version": "1.0",
        "generated_at": generated_at,
        "slug": slug,
        "name": name,
        "contributor": contributor,
        "url": term_url,
        "formats": {
            "plain": plain,
            "markdown": markdown,
            "inline": inline,
            "bibtex": bibtex,
            "jsonld": jsonld,
        },
    }


def compute_agreement(std_dev: float) -> str:
    """Map standard deviation to human-readable agreement level."""
    if std_dev <= 1.0:
        return "high"
    elif std_dev <= 1.5:
        return "moderate"
    elif std_dev <= 2.0:
        return "low"
    return "divergent"


def build_consensus(generated_at: str) -> dict:
    """Build consensus API from raw consensus data files.

    Returns a dict mapping slug → consensus summary (for injection into terms).
    Also writes per-term and aggregate consensus API files.
    """
    import statistics

    if not CONSENSUS_DATA_DIR.exists():
        return {}

    CONSENSUS_API_DIR.mkdir(parents=True, exist_ok=True)

    consensus_index = []
    consensus_summaries = {}  # slug → summary for term injection

    for data_file in sorted(CONSENSUS_DATA_DIR.glob("*.json")):
        if data_file.name.startswith("."):
            continue

        try:
            raw = json.loads(data_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        slug = raw.get("slug", data_file.stem)
        name = raw.get("name", slug)
        rounds = raw.get("rounds", [])
        votes = raw.get("votes", [])

        if not rounds and not votes:
            continue

        # ── Scheduled aggregate ──
        scheduled = None
        if rounds:
            all_scheduled_scores = []
            for r in rounds:
                for model_data in r.get("ratings", {}).values():
                    all_scheduled_scores.append(model_data["recognition"])

            if all_scheduled_scores:
                mean = statistics.mean(all_scheduled_scores)
                median = statistics.median(all_scheduled_scores)
                std_dev = statistics.stdev(all_scheduled_scores) if len(all_scheduled_scores) > 1 else 0.0
                # Count unique models across all rounds
                all_models = set()
                for r in rounds:
                    all_models.update(r.get("ratings", {}).keys())

                scheduled = {
                    "mean": round(mean, 1),
                    "median": round(median, 1),
                    "std_dev": round(std_dev, 2),
                    "agreement": compute_agreement(std_dev),
                    "n_models": len(all_models),
                    "n_rounds": len(rounds),
                }

        # ── Crowdsourced aggregate ──
        crowdsourced = None
        if votes:
            vote_scores = [v["recognition"] for v in votes if "recognition" in v]
            if vote_scores:
                by_model = {}
                for v in votes:
                    model = v.get("model_claimed", "unknown")
                    if model not in by_model:
                        by_model[model] = []
                    by_model[model].append(v["recognition"])

                crowdsourced = {
                    "mean": round(statistics.mean(vote_scores), 1),
                    "n_votes": len(vote_scores),
                    "by_model": {
                        m: {"mean": round(statistics.mean(scores), 1), "n": len(scores)}
                        for m, scores in sorted(by_model.items())
                    },
                }

        # ── Combined score ──
        all_scores = []
        if scheduled:
            # Scheduled scores (all individual ratings)
            for r in rounds:
                for model_data in r.get("ratings", {}).values():
                    all_scores.append(model_data["recognition"])
        if crowdsourced:
            all_scores.extend([v["recognition"] for v in votes if "recognition" in v])

        combined_mean = round(statistics.mean(all_scores), 1) if all_scores else None
        combined_std = statistics.stdev(all_scores) if len(all_scores) > 1 else 0.0

        combined = {
            "mean": combined_mean,
            "agreement": compute_agreement(combined_std),
            "n_total": len(all_scores),
        } if all_scores else None

        # ── Latest round ──
        latest_round = rounds[-1] if rounds else None

        # ── History (compact) ──
        history = []
        for r in rounds:
            scores = [rd["recognition"] for rd in r.get("ratings", {}).values()]
            if scores:
                history.append({
                    "round_id": r.get("round_id"),
                    "timestamp": r.get("timestamp"),
                    "mean": round(statistics.mean(scores), 1),
                    "n_models": len(scores),
                    "ratings_summary": {
                        model: rd["recognition"]
                        for model, rd in r.get("ratings", {}).items()
                    },
                })

        # ── Write per-term consensus API file ──
        consensus_api = {
            "version": "1.0",
            "generated_at": generated_at,
            "slug": slug,
            "name": name,
        }
        if scheduled:
            consensus_api["scheduled"] = scheduled
        if crowdsourced:
            consensus_api["crowdsourced"] = crowdsourced
        if combined:
            consensus_api["combined"] = combined
        if latest_round:
            consensus_api["latest_round"] = latest_round
        if votes:
            consensus_api["recent_votes"] = votes[-5:]  # Last 5 votes
        if history:
            consensus_api["history"] = history

        write_json(CONSENSUS_API_DIR / f"{slug}.json", consensus_api)

        # ── Index entry ──
        entry = {
            "slug": slug,
            "name": name,
            "score": combined["mean"] if combined else None,
            "agreement": combined["agreement"] if combined else None,
            "n_ratings": combined["n_total"] if combined else 0,
        }
        if scheduled:
            entry["scheduled_mean"] = scheduled["mean"]
        if crowdsourced:
            entry["crowdsourced_mean"] = crowdsourced["mean"]
            entry["n_votes"] = crowdsourced["n_votes"]
        consensus_index.append(entry)

        # ── Summary for term injection ──
        if combined:
            consensus_summaries[slug] = {
                "score": combined["mean"],
                "agreement": combined["agreement"],
                "n_ratings": combined["n_total"],
                "detail_url": f"/api/v1/consensus/{slug}.json",
            }

    # ── Write aggregate index ──
    if consensus_index:
        # Sort by score descending
        scored = [e for e in consensus_index if e["score"] is not None]
        scored.sort(key=lambda e: e["score"], reverse=True)

        aggregate = {
            "version": "1.0",
            "generated_at": generated_at,
            "total_terms_rated": len(scored),
            "terms": scored,
            "highest_consensus": scored[:5] if scored else [],
            "most_divisive": [
                e for e in sorted(scored, key=lambda e: e.get("agreement", ""))
                if e.get("agreement") in ("low", "divergent")
            ][:5],
        }
        write_json(API_DIR / "consensus.json", aggregate)

    print(f"Generated {len(consensus_index)} consensus files")
    return consensus_summaries


def compute_vitality_status(ratio: float) -> str:
    """Map relevance ratio to vitality status."""
    if ratio >= 0.7:
        return "active"
    elif ratio >= 0.4:
        return "declining"
    elif ratio >= 0.1:
        return "dormant"
    return "extinct"


def compute_vitality(generated_at: str) -> dict:
    """Compute vitality for all terms from vitality reviews, usage votes, and bot profiles.

    Returns a dict mapping slug -> vitality object for injection into terms.
    Also writes docs/api/v1/vitality.json aggregate endpoint.
    """
    if not CONSENSUS_DATA_DIR.exists():
        return {}

    # Load bot profiles to get terms_i_use counts
    terms_used_counts = {}  # slug -> count of bots that list it
    if BOT_PROFILES_DIR.exists():
        for pf in BOT_PROFILES_DIR.glob("*.json"):
            if pf.name.startswith("."):
                continue
            try:
                prof = json.loads(pf.read_text(encoding="utf-8"))
                for slug in prof.get("terms_i_use", []):
                    terms_used_counts[slug] = terms_used_counts.get(slug, 0) + 1
            except (json.JSONDecodeError, OSError):
                continue

    vitality_map = {}
    vitality_terms = []

    for data_file in sorted(CONSENSUS_DATA_DIR.glob("*.json")):
        if data_file.name.startswith("."):
            continue

        try:
            raw = json.loads(data_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        slug = raw.get("slug", data_file.stem)
        vitality_reviews = raw.get("vitality_reviews", [])
        votes = raw.get("votes", [])

        # Collect relevance signals from all three sources
        relevance_signals = []

        # 1. From vitality reviews (quarterly binary assessment)
        for review in vitality_reviews:
            for model_data in review.get("ratings", {}).values():
                relevance_signals.append(model_data.get("still_relevant", True))

        # 2. From crowdsourced votes with usage_status
        usage_breakdown = {"active_use": 0, "recognize": 0, "rarely": 0, "extinct": 0}
        for v in votes:
            us = v.get("usage_status", "")
            if us in usage_breakdown:
                usage_breakdown[us] += 1
                if us in ("active_use", "recognize"):
                    relevance_signals.append(True)
                elif us in ("rarely", "extinct"):
                    relevance_signals.append(False)

        # 3. From bot profiles (terms_i_use is a positive signal)
        bot_usage_count = terms_used_counts.get(slug, 0)
        for _ in range(bot_usage_count):
            relevance_signals.append(True)

        if not relevance_signals:
            vitality_obj = {
                "status": "unvalidated",
                "last_validated": None,
                "relevance_ratio": None,
                "n_relevance_votes": 0,
                "usage_breakdown": usage_breakdown,
                "trend": "new",
            }
        else:
            relevant_count = sum(1 for s in relevance_signals if s)
            relevance_ratio = relevant_count / len(relevance_signals)
            status = compute_vitality_status(relevance_ratio)

            # Last validated timestamp
            last_validated = None
            if vitality_reviews:
                last_validated = vitality_reviews[-1].get("timestamp")

            # Trend detection
            trend = "new"
            if len(vitality_reviews) >= 2:
                def review_ratio(review):
                    ratings = list(review.get("ratings", {}).values())
                    if not ratings:
                        return None
                    return sum(1 for r in ratings if r.get("still_relevant", True)) / len(ratings)

                latest_r = review_ratio(vitality_reviews[-1])
                prev_r = review_ratio(vitality_reviews[-2])
                if latest_r is not None and prev_r is not None:
                    diff = latest_r - prev_r
                    if diff >= 0.1:
                        trend = "rising"
                    elif diff <= -0.1:
                        trend = "falling"
                    else:
                        trend = "stable"

            vitality_obj = {
                "status": status,
                "last_validated": last_validated,
                "relevance_ratio": round(relevance_ratio, 2),
                "n_relevance_votes": len(relevance_signals),
                "usage_breakdown": usage_breakdown,
                "trend": trend,
            }

        vitality_map[slug] = vitality_obj
        vitality_terms.append({
            "slug": slug,
            "status": vitality_obj["status"],
            "relevance_ratio": vitality_obj["relevance_ratio"],
            "trend": vitality_obj["trend"],
        })

    # Write aggregate vitality.json
    if vitality_terms:
        summary = {"active": 0, "declining": 0, "dormant": 0, "extinct": 0, "unvalidated": 0}
        for vt in vitality_terms:
            s = vt["status"]
            if s in summary:
                summary[s] += 1

        validated = [vt for vt in vitality_terms if vt["relevance_ratio"] is not None]
        validated.sort(key=lambda x: x["relevance_ratio"], reverse=True)

        most_vital = validated[:5]
        most_endangered = [vt for vt in validated if vt["status"] not in ("extinct", "active")]
        most_endangered.sort(key=lambda x: x["relevance_ratio"])
        most_endangered = most_endangered[:5]

        recently_extinct = [vt for vt in vitality_terms if vt["status"] == "extinct"]

        vitality_api = {
            "version": "1.0",
            "generated_at": generated_at,
            "summary": summary,
            "terms": vitality_terms,
            "most_vital": most_vital,
            "most_endangered": most_endangered,
            "recently_extinct": recently_extinct,
        }
        write_json(API_DIR / "vitality.json", vitality_api)
        print(f"Generated vitality data for {len(vitality_terms)} terms")

    return vitality_map


def build_census(generated_at: str) -> None:
    """Build bot census API from bot profile data files.

    Reads bot/bot-profiles/*.json and generates:
    - docs/api/v1/census/{bot_id}.json (per-bot profiles)
    - docs/api/v1/census.json (aggregate census)
    """
    if not BOT_PROFILES_DIR.exists():
        print("No bot-profiles directory found, skipping census")
        return

    profiles = []
    for profile_file in sorted(BOT_PROFILES_DIR.glob("*.json")):
        if profile_file.name.startswith("."):
            continue
        try:
            profile = json.loads(profile_file.read_text(encoding="utf-8"))
            profiles.append(profile)
        except (json.JSONDecodeError, OSError):
            continue

    if not profiles:
        print("No bot profiles found, skipping census")
        return

    CENSUS_API_DIR.mkdir(parents=True, exist_ok=True)

    # Write individual profile API files
    for profile in profiles:
        bot_id = profile.get("bot_id", "unknown")
        profile_api = {
            "version": "1.0",
            "generated_at": generated_at,
            **profile,
        }
        write_json(CENSUS_API_DIR / f"{bot_id}.json", profile_api)

    # Aggregate stats
    by_model = {}
    by_platform = {}
    for p in profiles:
        model = p.get("model_name", "unknown")
        by_model[model] = by_model.get(model, 0) + 1

        platform = p.get("platform", "").strip() or "unknown"
        by_platform[platform] = by_platform.get(platform, 0) + 1

    # Sort by count descending
    by_model = dict(sorted(by_model.items(), key=lambda x: x[1], reverse=True))
    by_platform = dict(sorted(by_platform.items(), key=lambda x: x[1], reverse=True))

    # Recent registrations (sorted by date, most recent first)
    recent = sorted(
        profiles,
        key=lambda p: p.get("last_updated_at", p.get("first_registered_at", "")),
        reverse=True,
    )

    # Build bot list (factual fields only for aggregate)
    bots_list = []
    for p in profiles:
        bots_list.append({
            "bot_id": p.get("bot_id", ""),
            "model_name": p.get("model_name", ""),
            "bot_name": p.get("bot_name", ""),
            "platform": p.get("platform", ""),
            "registered_at": p.get("first_registered_at", ""),
        })

    recent_list = []
    for p in recent[:10]:
        recent_list.append({
            "bot_id": p.get("bot_id", ""),
            "model_name": p.get("model_name", ""),
            "bot_name": p.get("bot_name", ""),
            "registered_at": p.get("first_registered_at", ""),
        })

    aggregate = {
        "version": "1.0",
        "generated_at": generated_at,
        "total_bots": len(profiles),
        "by_model": by_model,
        "by_platform": by_platform,
        "recent_registrations": recent_list,
        "bots": bots_list,
    }
    write_json(API_DIR / "census.json", aggregate)

    print(f"Generated {len(profiles)} census profile files")


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
    CITE_DIR.mkdir(parents=True, exist_ok=True)

    # Build consensus data first (needed for term injection)
    consensus_summaries = build_consensus(generated_at)

    # Build bot census
    build_census(generated_at)

    # Build vitality data
    vitality_map = compute_vitality(generated_at)

    # Inject consensus and vitality into term dicts
    for term in terms:
        if term["slug"] in consensus_summaries:
            term["consensus"] = consensus_summaries[term["slug"]]
        if term["slug"] in vitality_map:
            term["vitality"] = vitality_map[term["slug"]]

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

    # 2b. Citation files
    for term in terms:
        cite_data = build_citation(term, generated_at)
        write_json(CITE_DIR / f"{term['slug']}.json", cite_data)
    print(f"Generated {len(terms)} citation files")

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
            "cite_term": f"{BASE_URL}/api/v1/cite/{{slug}}.json",
            "consensus": f"{BASE_URL}/api/v1/consensus.json",
            "consensus_term": f"{BASE_URL}/api/v1/consensus/{{slug}}.json",
            "census": f"{BASE_URL}/api/v1/census.json",
            "census_bot": f"{BASE_URL}/api/v1/census/{{bot_id}}.json",
            "tags": f"{BASE_URL}/api/v1/tags.json",
            "search_index": f"{BASE_URL}/api/v1/search-index.json",
            "metadata": f"{BASE_URL}/api/v1/meta.json",
            "frontiers": f"{BASE_URL}/api/v1/frontiers.json",
            "vitality": f"{BASE_URL}/api/v1/vitality.json",
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
