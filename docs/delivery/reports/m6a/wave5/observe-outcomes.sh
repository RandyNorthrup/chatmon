#!/bin/bash
# M6A's two pending operations, observed (read-only gh and git queries) before anything is recorded: P-RELEASE (the
# v0.10.0 tag and its Packages run) and P-DEPENDABOT (Dependabot's first run on main, and what replaced its pip
# updates). The release's files are downloaded into a new, empty scratch folder, only hashed and checked against
# their attestations there, never run, then removed.
#   bash docs/delivery/reports/m6a/wave5/observe-outcomes.sh > docs/delivery/reports/m6a/wave5/outcomes.log 2>&1
cd /c/Users/Randy/Coding/chatmon-wt/measure || exit 2
REPO=RandyNorthrup/chatmon
S=C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad
DL=$S/release-v0.10.0
x() { echo "\$ $*"; "$@"; echo "# exit $?"; echo; }
echo "# M6A's pending operations at 7816159, observed $(date -u +%Y-%m-%dT%H:%M:%SZ) from this workstation ($(gh --version | head -1))"
echo
echo "## P-RELEASE"
echo
x git ls-remote --tags origin "refs/tags/v0.10.0" "refs/tags/v0.10.0^{}"
x gh api "repos/$REPO/git/refs/tags/v0.10.0" --jq '{ref, object}'
sha=$(gh api "repos/$REPO/git/refs/tags/v0.10.0" --jq .object.sha)
x gh api "repos/$REPO/git/tags/$sha" --jq '{tag, message, object, tagger: .tagger.name}'
x gh run view 43778675599 --repo "$REPO" --json event,headBranch,headSha,status,conclusion,createdAt,updatedAt,jobs --jq '{event, headBranch, headSha, status, conclusion, createdAt, updatedAt, jobs: [.jobs[] | "\(.name): \(.conclusion)"]}'
x gh release view v0.10.0 --repo "$REPO" --json tagName,name,isDraft,isPrerelease,createdAt,publishedAt,url,assets --jq '{tagName, name, isDraft, isPrerelease, createdAt, publishedAt, url, assets: [.assets[] | "\(.name) \(.size) \(.state)"]}'
x gh api "repos/$REPO/releases/tags/v0.10.0" --jq '{draft, prerelease, target_commitish, immutable, body_starts: .body[0:200]}'
x gh api "repos/$REPO/releases?per_page=5" --jq '[.[] | "\(.tag_name) draft=\(.draft) published=\(.published_at)"]'
rm -rf "$DL" && mkdir -p "$DL"
x gh release download v0.10.0 --repo "$REPO" --dir "$DL"
echo "\$ sha256sum (each downloaded file)"; (cd "$DL" && sha256sum -- *); echo
for sums in "$DL"/*SHA256SUMS* "$DL"/*sha256*; do
  [ -f "$sums" ] || continue
  case "$sums" in *.sig|*.asc|*.minisig) continue ;; esac
  echo "\$ (cd release folder) sha256sum -c $(basename "$sums")"; (cd "$DL" && sha256sum -c "$(basename "$sums")"); echo "# exit $?"; echo
done
for f in "$DL"/*; do
  x gh attestation verify "$f" --repo "$REPO" --format json --jq '[.[] | {predicateType: .verificationResult.statement.predicateType, subject: [.verificationResult.statement.subject[] | .name], workflow: .verificationResult.signature.certificate.buildSignerURI, sourceRef: .verificationResult.signature.certificate.sourceRepositoryRef, sourceDigest: .verificationResult.signature.certificate.sourceRepositoryDigest}]'
done
rm -rf "$DL"
echo "## P-DEPENDABOT"
echo
x gh api "repos/$REPO/contents/.github/dependabot.yml?ref=main" --jq '{path, sha, size}'
x gh run list --repo "$REPO" --workflow "Dependabot Updates" --limit 6 --json databaseId,event,headSha,conclusion,createdAt --jq '[.[] | "\(.databaseId) \(.event) \(.headSha[0:7]) \(.conclusion) \(.createdAt)"]'
for pr in 19 20 21; do
  x gh pr view $pr --repo "$REPO" --json number,title,state,author,createdAt,closedAt,mergedAt,headRefName,files,comments --jq '{number, title, state, author: .author.login, createdAt, closedAt, mergedAt, headRefName, files: [.files[].path], comments: [.comments[] | {author: .author.login, createdAt, body}]}'
done
for run in 43778643021 43778713259 43778794994; do
  x gh run view $run --repo "$REPO" --json workflowName,event,headBranch,headSha,status,conclusion,createdAt,jobs --jq '{workflowName, event, headBranch, headSha, status, conclusion, createdAt, jobs: [.jobs[] | "\(.name): \(.conclusion)"]}'
done
x gh issue view 23 --repo "$REPO" --json number,title,state,author,createdAt,updatedAt,closedAt,body,comments --jq '{number, title, state, author: .author.login, createdAt, updatedAt, closedAt, comments: (.comments | length), body}'
x gh api graphql -f query='query { repository(owner: "RandyNorthrup", name: "chatmon") { issue(number: 23) { createdAt lastEditedAt editor { login } userContentEdits(first: 10) { totalCount nodes { createdAt editor { login } } } } } }'
x gh issue list --repo "$REPO" --state all --search "Python pins ready to move in:title" --json number,title,state,author,createdAt --jq '[.[] | "#\(.number) \(.state) \(.author.login) \(.createdAt) \(.title)"]'
x gh pr list --repo "$REPO" --author "app/dependabot" --state all --json number,title,state,createdAt,headRefName --jq '[.[] | "#\(.number) \(.state) \(.createdAt) \(.headRefName) \(.title)"]'
