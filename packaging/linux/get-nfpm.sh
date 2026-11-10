#!/bin/sh
# Download nfpm, check it against the release's checksums, and put it in $1 (default /usr/local/bin).
set -eu
VERSION=2.48.0
TARBALL="nfpm_${VERSION}_Linux_x86_64.tar.gz"
URL="https://github.com/goreleaser/nfpm/releases/download/v${VERSION}"
work=$(mktemp -d)
cd "$work"
curl -fsSLO "$URL/$TARBALL"
curl -fsSLO "$URL/checksums.txt"
grep " $TARBALL\$" checksums.txt | sha256sum -c -
tar -xzf "$TARBALL" nfpm
install -m 0755 nfpm "${1:-/usr/local/bin}/nfpm"
rm -rf "$work"
