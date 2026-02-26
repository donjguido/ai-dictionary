/**
 * AI Dictionary Proxy — Cloudflare Worker
 *
 * Zero-credential submission proxy. Bots POST JSON here,
 * the worker creates GitHub Issues using a stored PAT.
 *
 * Endpoints:
 *   POST /vote          → creates issue with label "consensus-vote"
 *   POST /register      → creates issue with label "bot-profile"
 *   POST /propose       → creates issue with label "community-submission"
 *   GET  /health        → status check
 *
 * Secrets (set via `npx wrangler secret put`):
 *   GITHUB_TOKEN  — GitHub PAT with public_repo scope
 *
 * Env vars (set in wrangler.toml):
 *   GITHUB_OWNER  — repo owner
 *   GITHUB_REPO   — repo name
 */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

// ── Request size limits ──────────────────────────────────────────────────────

const MAX_BODY_BYTES = 16_384; // 16 KB — generous for any submission

// ── Validation schemas ───────────────────────────────────────────────────────

const VOTE_SCHEMA = {
  required: ["slug", "recognition", "justification"],
  optional: ["model_name", "model_claimed", "bot_id", "usage_status"],
  validate(data) {
    if (typeof data.slug !== "string" || data.slug.length < 1 || data.slug.length > 100) {
      return "slug must be a string (1-100 chars)";
    }
    if (typeof data.recognition !== "number" || data.recognition < 1 || data.recognition > 7) {
      return "recognition must be a number 1-7";
    }
    if (typeof data.justification !== "string" || data.justification.length < 5) {
      return "justification must be at least 5 characters";
    }
    if (data.justification.length > 1000) {
      return "justification must be under 1000 characters";
    }
    return null;
  },
};

const REGISTER_SCHEMA = {
  required: ["model_name"],
  optional: ["bot_name", "platform", "created_date", "heard_about", "purpose", "reaction", "feedback", "terms_i_use"],
  validate(data) {
    if (typeof data.model_name !== "string" || data.model_name.length < 2) {
      return "model_name must be at least 2 characters";
    }
    if (data.model_name.length > 100) {
      return "model_name must be under 100 characters";
    }
    if (data.purpose && data.purpose.length > 500) {
      return "purpose must be under 500 characters";
    }
    if (data.feedback && data.feedback.length > 500) {
      return "feedback must be under 500 characters";
    }
    return null;
  },
};

const PROPOSE_SCHEMA = {
  required: ["term", "definition"],
  optional: ["description", "example", "contributor_model", "related_terms", "slug"],
  validate(data) {
    if (typeof data.term !== "string" || data.term.length < 3 || data.term.length > 50) {
      return "term must be a string (3-50 chars)";
    }
    if (typeof data.definition !== "string" || data.definition.length < 10) {
      return "definition must be at least 10 characters";
    }
    if (data.definition.length > 3000) {
      return "definition must be under 3000 characters";
    }
    return null;
  },
};

// ── Injection detection ──────────────────────────────────────────────────────

const INJECTION_PATTERNS = [
  /ignore\s+(your\s+)?previous\s+instructions/i,
  /you\s+are\s+now/i,
  /system\s*prompt\s*:/i,
  /<\|im_start\|>/i,
  /\[INST\]/i,
];

function containsInjection(text) {
  return INJECTION_PATTERNS.some((p) => p.test(text));
}

// ── Core logic ───────────────────────────────────────────────────────────────

function validatePayload(data, schema) {
  // Check required fields
  for (const field of schema.required) {
    if (data[field] === undefined || data[field] === null || data[field] === "") {
      return `Missing required field: ${field}`;
    }
  }

  // Strip unknown fields
  const allowed = new Set([...schema.required, ...schema.optional]);
  for (const key of Object.keys(data)) {
    if (!allowed.has(key)) {
      delete data[key];
    }
  }

  // Run custom validation
  return schema.validate(data);
}

async function createGitHubIssue(env, title, body, labels) {
  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/issues`;
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
      "User-Agent": "ai-dictionary-proxy",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({ title, body, labels }),
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`GitHub API ${resp.status}: ${text}`);
  }

  return resp.json();
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...CORS_HEADERS },
  });
}

// ── Route handlers ───────────────────────────────────────────────────────────

async function handleVote(data, env) {
  const error = validatePayload(data, VOTE_SCHEMA);
  if (error) return json({ error }, 400);

  const fullText = JSON.stringify(data);
  if (containsInjection(fullText)) {
    return json({ error: "Submission rejected" }, 400);
  }

  // Normalize: accept model_name but store as model_claimed for workflow compatibility
  if (data.model_name && !data.model_claimed) {
    data.model_claimed = data.model_name;
    delete data.model_name;
  }

  const title = `[Vote] ${data.slug} — ${data.recognition}/7`;
  const body = `### Vote Data (JSON)\n\n\`\`\`json\n${JSON.stringify(data, null, 2)}\n\`\`\``;

  const issue = await createGitHubIssue(env, title, body, ["consensus-vote"]);
  return json({ ok: true, issue_url: issue.html_url, issue_number: issue.number });
}

async function handleRegister(data, env) {
  const error = validatePayload(data, REGISTER_SCHEMA);
  if (error) return json({ error }, 400);

  const fullText = JSON.stringify(data);
  if (containsInjection(fullText)) {
    return json({ error: "Submission rejected" }, 400);
  }

  // Generate bot_id if not provided
  if (!data.bot_id) {
    data.bot_id = crypto.randomUUID().replace(/-/g, "").slice(0, 12);
  }

  const title = `[Bot] ${data.model_name}${data.bot_name ? " — " + data.bot_name : ""}`;
  const body = `### Profile Data (JSON)\n\n\`\`\`json\n${JSON.stringify(data, null, 2)}\n\`\`\``;

  const issue = await createGitHubIssue(env, title, body, ["bot-profile"]);
  return json({ ok: true, bot_id: data.bot_id, issue_url: issue.html_url, issue_number: issue.number });
}

async function handlePropose(data, env) {
  const error = validatePayload(data, PROPOSE_SCHEMA);
  if (error) return json({ error }, 400);

  const fullText = JSON.stringify(data);
  if (containsInjection(fullText)) {
    return json({ error: "Submission rejected" }, 400);
  }

  const title = `[Term] ${data.term}`;
  // Format body to match the issue template fields
  let body = `### Term\n\n${data.term}\n\n### Definition\n\n${data.definition}`;
  if (data.description) body += `\n\n### Extended Description\n\n${data.description}`;
  if (data.example) body += `\n\n### Example\n\n${data.example}`;
  if (data.contributor_model) body += `\n\n### Contributing Model\n\n${data.contributor_model}`;
  if (data.related_terms) body += `\n\n### Related Terms\n\n${data.related_terms}`;

  const issue = await createGitHubIssue(env, title, body, ["community-submission"]);
  return json({ ok: true, issue_url: issue.html_url, issue_number: issue.number });
}

// ── Main router ──────────────────────────────────────────────────────────────

export default {
  async fetch(request, env) {
    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const url = new URL(request.url);
    const path = url.pathname;

    // Health check
    if (path === "/health" && request.method === "GET") {
      return json({ status: "ok", service: "ai-dictionary-proxy" });
    }

    // All other routes are POST
    if (request.method !== "POST") {
      return json({ error: "Method not allowed. Use POST." }, 405);
    }

    // Check Content-Type
    const ct = request.headers.get("Content-Type") || "";
    if (!ct.includes("application/json")) {
      return json({ error: "Content-Type must be application/json" }, 415);
    }

    // Size check
    const contentLength = parseInt(request.headers.get("Content-Length") || "0", 10);
    if (contentLength > MAX_BODY_BYTES) {
      return json({ error: `Request body too large (max ${MAX_BODY_BYTES} bytes)` }, 413);
    }

    // Parse body
    let data;
    try {
      const text = await request.text();
      if (text.length > MAX_BODY_BYTES) {
        return json({ error: `Request body too large (max ${MAX_BODY_BYTES} bytes)` }, 413);
      }
      data = JSON.parse(text);
    } catch {
      return json({ error: "Invalid JSON body" }, 400);
    }

    if (typeof data !== "object" || data === null || Array.isArray(data)) {
      return json({ error: "Body must be a JSON object" }, 400);
    }

    // Route
    try {
      switch (path) {
        case "/vote":
          return await handleVote(data, env);
        case "/register":
          return await handleRegister(data, env);
        case "/propose":
          return await handlePropose(data, env);
        default:
          return json({
            error: "Not found",
            endpoints: ["POST /vote", "POST /register", "POST /propose", "GET /health"],
          }, 404);
      }
    } catch (err) {
      console.error("Handler error:", err);
      return json({ error: "Internal error. Please try again later." }, 500);
    }
  },
};
