"""AI code review for pull requests.

Posts one review per push. Requests changes (which the bridge forwards to Jules) at most
MAX_BLOCKING_ROUNDS times per PR; after that it only comments, so agents can't loop forever.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import requests

MARKER = "<!-- ai-review -->"
GH = "https://api.github.com"
REPO = os.environ["REPO"]
PR = os.environ["PR_NUMBER"]
MODEL = os.environ.get("REVIEW_MODEL", "claude-sonnet-5-5")
MAX_ROUNDS = int(os.environ.get("MAX_BLOCKING_ROUNDS", "2"))
MAX_DIFF_CHARS = 150_000

gh = requests.Session()
gh.headers.update({
    "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
})


def pr_info() -> dict:
    r = gh.get(f"{GH}/repos/{REPO}/pulls/{PR}")
    r.raise_for_status()
    return r.json()


def pr_diff() -> str:
    r = gh.get(f"{GH}/repos/{REPO}/pulls/{PR}", headers={"Accept": "application/vnd.github.v3.diff"})
    r.raise_for_status()
    diff = r.text
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n\n[diff truncated]"
    return diff


BLOCKING_MARKER = "<!-- ai-review:blocking -->"


def my_reviews() -> list[dict]:
    r = gh.get(f"{GH}/repos/{REPO}/pulls/{PR}/reviews", params={"per_page": 100})
    r.raise_for_status()
    return [rv for rv in r.json() if MARKER in (rv.get("body") or "")]


def prior_blocking_rounds(reviews: list[dict]) -> int:
    return sum(1 for rv in reviews if BLOCKING_MARKER in (rv.get("body") or ""))


def dismiss_stale_blocks(reviews: list[dict]) -> None:
    """Earlier 'changes requested' reviews would keep blocking the merge; clear them (best effort)."""
    for rv in reviews:
        if rv.get("state") != "CHANGES_REQUESTED":
            continue
        resp = gh.put(
            f"{GH}/repos/{REPO}/pulls/{PR}/reviews/{rv['id']}/dismissals",
            json={"message": "Superseded by a newer AI review.", "event": "DISMISS"},
        )
        if resp.status_code >= 400:
            print(f"Could not dismiss review {rv['id']}: {resp.status_code}")


def ask_claude(info: dict, diff: str) -> dict:
    rules = Path("AGENTS.md").read_text(encoding="utf-8") if Path("AGENTS.md").exists() else ""
    system = (
        "You are a senior reviewer for a Next.js + FastAPI + MySQL SaaS. Review only the diff. "
        "Flag real problems: bugs, security issues (injection, auth, secrets), data loss, broken migrations, "
        "missing tests for new behavior, and violations of the repo rules. Ignore style nits. "
        'Reply with JSON only: {"verdict": "approve" | "changes", "summary": str, '
        '"findings": [{"file": str, "severity": "blocking" | "suggestion", "comment": str}]}. '
        'Use "changes" only if at least one finding is blocking.'
    )
    user = (
        f"Repo rules (AGENTS.md):\n{rules}\n\n"
        f"PR title: {info.get('title')}\nPR description:\n{info.get('body') or ''}\n\nDiff:\n{diff}"
    )
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={"model": MODEL, "max_tokens": 4000, "system": system, "messages": [{"role": "user", "content": user}]},
        timeout=300,
    )
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return {"verdict": "approve", "summary": "Reviewer returned no structured output.", "findings": []}
    return json.loads(match.group(0))


def format_body(result: dict, capped: bool, blocking_event: bool) -> str:
    lines = [MARKER + (BLOCKING_MARKER if blocking_event else ""), f"**AI review:** {result.get('summary', '').strip()}"]
    findings = result.get("findings") or []
    blocking = [f for f in findings if f.get("severity") == "blocking"]
    suggestions = [f for f in findings if f.get("severity") != "blocking"]
    if blocking:
        lines.append("\n**Must fix**")
        lines += [f"- `{f.get('file', '?')}`: {f.get('comment', '')}" for f in blocking]
    if suggestions:
        lines.append("\n**Suggestions**")
        lines += [f"- `{f.get('file', '?')}`: {f.get('comment', '')}" for f in suggestions]
    if capped and blocking:
        lines.append(f"\n_Blocking-review limit ({MAX_ROUNDS}) reached; leaving this for the human reviewer._")
    return "\n".join(lines)


def main() -> int:
    info = pr_info()
    result = ask_claude(info, pr_diff())
    reviews = my_reviews()
    dismiss_stale_blocks(reviews)
    wants_changes = result.get("verdict") == "changes"
    capped = wants_changes and prior_blocking_rounds(reviews) >= MAX_ROUNDS
    event = "REQUEST_CHANGES" if wants_changes and not capped else "COMMENT"
    r = gh.post(
        f"{GH}/repos/{REPO}/pulls/{PR}/reviews",
        json={
            "body": format_body(result, capped, event == "REQUEST_CHANGES"),
            "event": event,
            "commit_id": info["head"]["sha"],
        },
    )
    r.raise_for_status()
    print(f"Posted {event} review")
    return 0


if __name__ == "__main__":
    sys.exit(main())
