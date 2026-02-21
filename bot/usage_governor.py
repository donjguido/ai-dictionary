#!/usr/bin/env python3
"""GitHub Actions Usage Governor - monitors and throttles workflows to stay within Free tier limits.

Free tier limits:
- 2,000 minutes/month for GitHub Actions
- Ubuntu runners cost 1 min per min of runtime
- Budget: ~66 minutes/day

Thresholds:
- >80% monthly budget: skip non-essential workflows (review, summary)
- >95% monthly budget: skip all workflows
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path(__file__).parent / "usage-state.json"
MONTHLY_BUDGET = 2000  # minutes
WARNING_THRESHOLD = 0.80  # 80%
CRITICAL_THRESHOLD = 0.95  # 95%

# Essential workflows keep running until critical threshold
ESSENTIAL_WORKFLOWS = {"generate"}


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"last_check": None, "minutes_used": 0, "month": None, "throttled": False}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def estimate_usage() -> float:
    """Estimate Actions minutes used this month from workflow run durations."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    try:
        result = subprocess.run(
            [
                "gh", "api",
                f"/repos/{{owner}}/{{repo}}/actions/runs",
                "--paginate",
                "-q",
                f'[.workflow_runs[] | select(.created_at >= "{month_start.strftime("%Y-%m-%dT%H:%M:%SZ")}") | '
                f'{{start: .run_started_at, end: .updated_at, status: .status}}]',
            ],
            capture_output=True, text=True, timeout=30,
        )

        if result.returncode != 0:
            print(f"Warning: gh api failed: {result.stderr[:200]}")
            return 0.0

        runs = json.loads(result.stdout) if result.stdout.strip() else []

        total_minutes = 0.0
        for run in runs:
            if run.get("start") and run.get("end") and run.get("status") == "completed":
                try:
                    start = datetime.fromisoformat(run["start"].replace("Z", "+00:00"))
                    end = datetime.fromisoformat(run["end"].replace("Z", "+00:00"))
                    total_minutes += max(0, (end - start).total_seconds() / 60)
                except (ValueError, TypeError):
                    continue

        return total_minutes

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Warning: could not estimate usage: {e}")
        return 0.0


def should_proceed(workflow_name: str = "default") -> bool:
    """Check if this workflow should run. Returns True if OK, False if throttled."""
    state = load_state()
    now = datetime.now(timezone.utc)
    current_month = now.strftime("%Y-%m")

    # Reset on new month
    if state.get("month") != current_month:
        state = {"last_check": None, "minutes_used": 0, "month": current_month, "throttled": False}

    # Refresh usage from API (at most once per hour)
    last = state.get("last_check")
    needs_refresh = not last
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            needs_refresh = (now - last_dt).total_seconds() > 3600
        except (ValueError, TypeError):
            needs_refresh = True

    if needs_refresh:
        state["minutes_used"] = estimate_usage()
        state["last_check"] = now.isoformat()

    usage_pct = state["minutes_used"] / MONTHLY_BUDGET if MONTHLY_BUDGET > 0 else 0
    is_essential = workflow_name in ESSENTIAL_WORKFLOWS

    proceed = True
    if usage_pct >= CRITICAL_THRESHOLD:
        proceed = False
        state["throttled"] = True
    elif usage_pct >= WARNING_THRESHOLD:
        if not is_essential:
            proceed = False
            state["throttled"] = True
    else:
        state["throttled"] = False

    save_state(state)

    # Write to GITHUB_OUTPUT
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write(f"proceed={'true' if proceed else 'false'}\n")
            f.write(f"usage_pct={usage_pct:.2f}\n")
            f.write(f"minutes_used={state['minutes_used']:.1f}\n")

    status = "OK" if proceed else "THROTTLED"
    print(f"GOVERNOR [{status}]: {workflow_name} | Usage: {usage_pct:.0%} ({state['minutes_used']:.0f}/{MONTHLY_BUDGET} min)")

    return proceed


if __name__ == "__main__":
    workflow = sys.argv[1] if len(sys.argv) > 1 else "default"
    if not should_proceed(workflow):
        sys.exit(1)
