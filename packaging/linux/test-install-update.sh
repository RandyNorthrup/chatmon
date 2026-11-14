#!/bin/sh
# CI: root's side of a Chatmon update, for real, as root in a throwaway container (never on a computer of
# yours). PACKAGE is a freshly built chatmon .deb or .rpm, from the repository this runs from:
#
#   sh packaging/linux/test-install-update.sh dist/chatmon_<v>-1_all.deb     (needs python3; root)
#
# A fresh build has no release signature, so this run makes a release key of its own (tests/ed25519_sign.py)
# and installs a Chatmon that trusts it, as an older version: for a .deb, the package itself repacked as 0.0.1
# with that key; for an .rpm, the package installed, then its check given that key and the version 0.0.1 (root
# may change root's files). Then the installed install-update must refuse a tampered list, a bad signature, a
# checksum handed to it, and the same version again, and install the signed newer package.
set -eu
pkg=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
repo=$(cd "$(dirname "$0")/../.." && pwd)
lib=/usr/lib/chatmon/chatmon
[ "$(id -u)" = 0 ] || { echo "test-install-update: run as root, in a throwaway container" >&2; exit 1; }
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
name=$(basename "$pkg")
cp "$pkg" "$work/$name"
key=$(python3 "$repo/tests/ed25519_sign.py" keygen "$work/secret")
version=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$repo/chatmon/__init__.py")

trust_test_key() {  # $1: the folder holding chatmon/ (installed, or a package being repacked)
    sed -i "s/^RELEASE_KEYS = (.*/RELEASE_KEYS = (\"$key\",)/" "$1/chatmon/releasecheck.py"
    grep -q "$key" "$1/chatmon/releasecheck.py"
}

case $name in
    *.deb)
        # The same package as an older Chatmon (0.0.1) that trusts this run's key, installed first.
        dpkg-deb -R "$pkg" "$work/old"
        sed -i 's/^Version: .*/Version: 0.0.1-1/' "$work/old/DEBIAN/control"
        sed -i 's/^__version__ = .*/__version__ = "0.0.1"/' "$work/old/usr/lib/chatmon/chatmon/__init__.py"
        trust_test_key "$work/old/usr/lib/chatmon"
        dpkg-deb -b "$work/old" "$work/old.deb" >/dev/null
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --allow-downgrades "$work/old.deb" >/dev/null
        installed() { dpkg-query -W -f '${Version}' chatmon; }
        ;;
    *.rpm)
        dnf install -y -q "$pkg" >/dev/null
        trust_test_key /usr/lib/chatmon
        sed -i 's/^__version__ = .*/__version__ = "0.0.1"/' "$lib/__init__.py"
        installed() { sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$lib/__init__.py"; }
        ;;
    *) echo "test-install-update: not a .deb or .rpm: $name" >&2; exit 2 ;;
esac
echo "installed: $(installed)"

(cd "$work" && sha256sum "$name" > SHA256SUMS.txt)
python3 "$repo/tests/ed25519_sign.py" sign "$work/secret" "$work/SHA256SUMS.txt"

refused() {  # $1: what's wrong; the rest: install-update's arguments. It must refuse, and change nothing.
    what=$1
    shift
    before=$(installed)
    if /usr/lib/chatmon/install-update "$@" >"$work/out" 2>&1; then
        echo "install-update installed despite $what:" >&2
        cat "$work/out" >&2
        exit 1
    fi
    [ "$(installed)" = "$before" ] || { echo "install-update changed the install despite $what" >&2; exit 1; }
    echo "refused $what: $(tail -n 1 "$work/out")"
}

cp "$work/SHA256SUMS.txt" "$work/tampered.txt"
echo "# changed after signing" >> "$work/tampered.txt"
refused "a tampered list" "$work/$name" "$work/tampered.txt" "$work/SHA256SUMS.txt.sig"
head -c 64 /dev/zero > "$work/zero.sig"
refused "a bad signature" "$work/$name" "$work/SHA256SUMS.txt" "$work/zero.sig"
refused "a checksum from the caller" "$work/$name" "$(sha256sum "$pkg" | cut -d' ' -f1)"

/usr/lib/chatmon/install-update "$work/$name" "$work/SHA256SUMS.txt" "$work/SHA256SUMS.txt.sig" >/dev/null
case $name in
    *.deb) [ "$(installed)" = "$version-1" ] || { echo "install-update didn't install $version: $(installed)" >&2; exit 1; } ;;
    *) grep -q "^__version__ = \"$version\"" "$lib/__init__.py" || echo "(dnf kept the files of the same version already installed)" ;;
esac
echo "installed the signed newer package: $(installed)"

# The same release again, signed with a key the installed check trusts: not newer, so refused.
trust_test_key /usr/lib/chatmon
sed -i "s/^__version__ = .*/__version__ = \"$version\"/" "$lib/__init__.py"
refused "the same version again" "$work/$name" "$work/SHA256SUMS.txt" "$work/SHA256SUMS.txt.sig"
echo "test-install-update: all good"
