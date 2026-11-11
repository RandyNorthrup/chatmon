#!/bin/sh
# Download nfpm, check it against the SHA-256 pinned here (the release's own checksums.txt says the same,
# but a pin also catches a release that was changed after the fact), and put it in $1 (default /usr/local/bin).
set -eu
VERSION=2.48.0
SHA256=6d7f9a28b2f397934403950fcbba83f598b08d02edbe79a0815b3b4897341750
TARBALL="nfpm_${VERSION}_Linux_x86_64.tar.gz"
URL="https://github.com/goreleaser/nfpm/releases/download/v${VERSION}"
work=$(mktemp -d)
cd "$work"
curl -fsSLO "$URL/$TARBALL"
echo "$SHA256  $TARBALL" | sha256sum -c -
tar -xzf "$TARBALL" nfpm
install -m 0755 nfpm "${1:-/usr/local/bin}/nfpm"
rm -rf "$work"
