#!/usr/bin/env python3
"""Fibonacci counter for tag review scheduling.

The tag review runs after every N new definitions, where N follows the
Fibonacci sequence starting at 34: 34, 55, 89, 144, 233, ...

This ensures reviews happen more frequently when the dictionary is small
and less frequently as it grows.
"""

import json
import os
import sys
from pathlib import Path

STATE_FILE = Path(__file__).parent / "state.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"fib_current": 34, "fib_next": 55, "definitions_since_last_review": 0}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def increment():
    """Increment the definition counter. Called after each generate run."""
    state = load_state()
    count = int(os.environ.get("DEFINITION_COUNT", "1"))
    state["definitions_since_last_review"] += count

    review_needed = state["definitions_since_last_review"] >= state["fib_current"]

    save_state(state)

    print(f"Definitions since last review: {state['definitions_since_last_review']}/{state['fib_current']}")
    print(f"Review needed: {review_needed}")

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write(f"review_needed={'true' if review_needed else 'false'}\n")


def advance():
    """Advance the fibonacci counter. Called after a review completes."""
    state = load_state()
    old_threshold = state["fib_current"]
    new_current = state["fib_next"]
    new_next = state["fib_current"] + state["fib_next"]

    state["fib_current"] = new_current
    state["fib_next"] = new_next
    state["definitions_since_last_review"] = 0

    save_state(state)

    print(f"Fibonacci advanced: {old_threshold} -> {new_current} (next: {new_next})")
    print("Counter reset to 0.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "increment"
    commands = {"increment": increment, "advance": advance}
    if cmd not in commands:
        print(f"Usage: {sys.argv[0]} [increment|advance]")
        sys.exit(1)
    commands[cmd]()
