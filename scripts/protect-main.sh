#!/usr/bin/env bash
# Makes "a human merges" a rule GitHub enforces, not a habit:
# PRs into main need green CI and one approving review. Requires the gh CLI, logged in as a repo admin.
# Usage: ./scripts/protect-main.sh owner/repo
set -euo pipefail
REPO="${1:?usage: $0 owner/repo}"

gh api -X PUT "repos/${REPO}/branches/main/protection" \
  -H "Accept: application/vnd.github+json" \
  --input - <<'JSON'
{
  "required_status_checks": { "strict": true, "contexts": ["backend", "frontend"] },
  "enforce_admins": false,
  "required_pull_request_reviews": { "required_approving_review_count": 1, "dismiss_stale_reviews": true },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
echo "main is protected on ${REPO}: CI must pass and a human must approve."
