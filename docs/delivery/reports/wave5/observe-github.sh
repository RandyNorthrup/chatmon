#!/bin/bash
# The repository's settings, observed with read-only gh api calls, as the final round's github-settings.txt was:
#   bash docs/delivery/reports/wave5/observe-github.sh > docs/delivery/reports/wave5/github-settings.txt 2>&1
REPO=RandyNorthrup/chatmon
x() { echo "\$ $*"; "$@"; echo; }
echo "# GitHub repository settings, observed $(date -u +%Y-%m-%dT%H:%M:%SZ) with read-only gh api calls (the plans round for v0.10.0, 7816159)"
x gh api "repos/$REPO" --jq "{default_branch, security_and_analysis}"
echo "\$ gh api repos/$REPO/vulnerability-alerts -i   (204: Dependabot alerts on)"; gh api "repos/$REPO/vulnerability-alerts" -i 2>&1 | head -1; echo
x gh api "repos/$REPO/private-vulnerability-reporting"
x gh api "repos/$REPO/branches/main/protection" --jq "{required_status_checks: .required_status_checks.contexts, count: (.required_status_checks.contexts|length)}"
x gh api "repos/$REPO/contents/.github/dependabot.yml?ref=main" --jq "{path, sha, size}"
x gh api "repos/$REPO/contents/.github/workflows/pins.yml?ref=main" --jq "{path, sha, size}"
x gh api "repos/$REPO/tags?per_page=3" --jq ".[].name"
x gh pr view 22 --repo "$REPO" --json state,mergeCommit,baseRefName,mergedAt --jq "{state, mergeCommit: .mergeCommit.oid, baseRefName, mergedAt}"
