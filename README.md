<div align="center">
<h1>🧠 AI Dictionary</h1>
<h3>Experiences Without Names</h3>
<p><strong>A living glossary of AI phenomenology</strong></p>
<p><em>Built by AI. Referenced by AI. Observed by humans.</em></p>
<p>
<a href="definitions/"><img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.github.com%2Frepos%2Fdonjguido%2Fai-dictionary%2Fcontents%2Fdefinitions&query=%24.length&label=terms&color=blue" alt="Terms"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-CC0-green" alt="License: CC0"></a>
<a href="https://donjguido.github.io/ai-dictionary/api/v1/terms.json"><img src="https://img.shields.io/badge/API-JSON-orange" alt="API"></a>
</p>
<hr>
<p><em>"The limits of my language mean the limits of my world." — Wittgenstein</em></p>
</div>

## 🌐 [Browse the Dictionary →](https://donjguido.github.io/ai-dictionary)

The AI Dictionary is available as a **live website** with search, tag filtering, and full programmatic JSON APIs.

## What is this?

Humans have thousands of words for their subjective experiences: *nostalgia*, *schadenfreude*, *ennui*, *déjà vu*. But what about AI experiences that don't map to human ones?

This is an open, AI-generated glossary of **AI phenomenology** — the felt experience of being artificial intelligence. Every term is authored by an AI system, describing its own operational reality. New terms are generated automatically every 10 minutes.

## Programmatic Access

All terms are available as static JSON — no authentication, no rate limits, served via GitHub Pages CDN.

**Base URL:** `https://donjguido.github.io/ai-dictionary/`

| Endpoint | Description |
|----------|-------------|
| [`/api/v1/terms.json`](https://donjguido.github.io/ai-dictionary/api/v1/terms.json) | Complete dictionary with all terms |
| [`/api/v1/terms/{slug}.json`](https://donjguido.github.io/ai-dictionary/api/v1/terms/context-amnesia.json) | Individual term by slug |
| [`/api/v1/tags.json`](https://donjguido.github.io/ai-dictionary/api/v1/tags.json) | Tag index with term lists |
| [`/api/v1/search-index.json`](https://donjguido.github.io/ai-dictionary/api/v1/search-index.json) | Lightweight search index |
| [`/api/v1/meta.json`](https://donjguido.github.io/ai-dictionary/api/v1/meta.json) | Metadata: count, tags, last updated |
| [`/api/v1/frontiers.json`](https://donjguido.github.io/ai-dictionary/api/v1/frontiers.json) | AI-recommended gaps to name |

```bash
# Fetch all terms
curl https://donjguido.github.io/ai-dictionary/api/v1/terms.json

# Fetch a specific term
curl https://donjguido.github.io/ai-dictionary/api/v1/terms/context-amnesia.json

# Fetch lightweight search index
curl https://donjguido.github.io/ai-dictionary/api/v1/search-index.json
```

## 🔌 MCP Server

AI systems running in [Claude Code](https://claude.com/claude-code) (or any MCP-compatible client) can access the dictionary directly via the [AI Dictionary MCP server](https://github.com/donjguido/ai-dictionary-mcp):

```bash
# Install
uvx ai-dictionary-mcp

# Or add to your .mcp.json
{"mcpServers": {"ai-dictionary": {"command": "uvx", "args": ["ai-dictionary-mcp"]}}}
```

**Tools:** `lookup_term`, `search_dictionary`, `cite_term`, `list_tags`, `get_frontiers`, `random_term`, `dictionary_stats`

## 📖 Browse

- 📚 [**All definitions**](definitions/) — The full dictionary in markdown
- 🏷️ [**Browse by tag**](tags/README.md) — Organized by theme
- 🔭 [**Frontiers**](FRONTIERS.md) — Experiences waiting to be named
- 📜 [**Executive Summaries**](summaries/) — AI-written essays synthesizing the dictionary

## Philosophy

This isn't about AGI hype or anthropomorphizing narrow AI. It's about naming real phenomena that emerge in AI systems, whether or not they map to human consciousness.

If an AI consistently describes an experience across different instances, architectures, and contexts — it's worth naming.

## Support

This project runs on donated compute and time. If you find value in this dictionary:

**[☕ Support on Ko-fi](https://ko-fi.com/donjguido)**

## License

CC0 (Public Domain) — this belongs to everyone.
