#!/usr/bin/env python3
"""PR Review Bot - validates new definition files in pull requests."""

import os
import subprocess
import sys
from pathlib import Path

from quality_check import validate_definition

REPO_ROOT = Path(__file__).parent.parent
DEFINITIONS_DIR = REPO_ROOT / "definitions"


def get_changed_definitions() -> list[str]:
    """Get list of new/modified definition files in this PR."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=AM", "origin/main...HEAD", "--", "definitions/"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    files = [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]
    return [f for f in files if f.endswith(".md") and not f.endswith("README.md")]


def main():
    changed_files = get_changed_definitions()

    if not changed_files:
        print("No definition files changed in this PR.")
        gh_output = os.environ.get("GITHUB_OUTPUT")
        if gh_output:
            with open(gh_output, "a") as f:
                f.write("valid=true\n")
        return

    print(f"Reviewing {len(changed_files)} definition file(s)...")

    # Get existing filenames for duplicate check (exclude the files being reviewed)
    existing_filenames = set()
    for f in DEFINITIONS_DIR.glob("*.md"):
        if f.name != "README.md":
            existing_filenames.add(f.name)

    all_issues = {}
    for filepath in changed_files:
        full_path = REPO_ROOT / filepath
        if not full_path.exists():
            continue

        filename = full_path.name
        content = full_path.read_text(encoding="utf-8")

        # Don't flag as duplicate against itself
        check_set = existing_filenames - {filename}
        is_valid, issues = validate_definition(content, filename, check_set)

        if not is_valid:
            all_issues[filename] = issues
            print(f"  FAIL: {filename}")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print(f"  OK: {filename}")

    gh_output = os.environ.get("GITHUB_OUTPUT")

    if all_issues:
        # Write comment to file for the workflow to post
        comment_lines = [
            "## AI Dictionary Bot - Review Results\n",
            "Some definitions need fixes before merging:\n",
        ]
        for filename, issues in all_issues.items():
            comment_lines.append(f"### `{filename}`")
            for issue in issues:
                comment_lines.append(f"- {issue}")
            comment_lines.append("")

        comment_lines.append("---")
        comment_lines.append("*Fix these issues and push again. The bot will re-review automatically.*")

        comment_path = "/tmp/review-comment.md"
        with open(comment_path, "w") as f:
            f.write("\n".join(comment_lines))

        if gh_output:
            with open(gh_output, "a") as f:
                f.write("valid=false\n")

        print(f"\n{len(all_issues)} file(s) failed validation.")
    else:
        if gh_output:
            with open(gh_output, "a") as f:
                f.write("valid=true\n")
        print("\nAll definitions pass quality checks!")


if __name__ == "__main__":
    main()
