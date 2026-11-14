"""Ed25519 signing for the tests alone (RFC 8032, section 5.1.6). Chatmon itself only verifies
(chatmon/ed25519.py) and the standard library can't sign, so a test that needs a release key of its own makes
a throwaway one here. Never for anything real: it isn't constant-time, and it keeps nothing.

    python tests/ed25519_sign.py keygen SECRET_FILE     writes a new secret, prints its public key (hex)
    python tests/ed25519_sign.py sign SECRET_FILE FILE  writes FILE.sig, FILE's 64-byte signature

The command line is for packaging/linux/test-install-update.sh, which signs a fresh build's checksums with a key
of its run's own inside a throwaway container.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

if __name__ == "__main__":  # run as a script: Chatmon's package is beside this folder
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chatmon import ed25519 as _curve  # noqa: E402

_P, _Q, _G = _curve._P, _curve._Q, _curve._G


def _encode(point: tuple) -> bytes:
    x, y, z, _t = point
    inverse = pow(z, _P - 2, _P)
    x, y = x * inverse % _P, y * inverse % _P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _expand(secret: bytes) -> tuple[int, bytes]:
    digest = hashlib.sha512(secret).digest()
    scalar = int.from_bytes(digest[:32], "little") & ((1 << 254) - 8) | (1 << 254)
    return scalar, digest[32:]


def public_key(secret: bytes) -> bytes:
    scalar, _ = _expand(secret)
    return _encode(_curve._mul(scalar, _G))


def sign(secret: bytes, message: bytes) -> bytes:
    scalar, prefix = _expand(secret)
    public = _encode(_curve._mul(scalar, _G))
    r = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % _Q
    big_r = _encode(_curve._mul(r, _G))
    k = int.from_bytes(hashlib.sha512(big_r + public + message).digest(), "little") % _Q
    return big_r + ((r + k * scalar) % _Q).to_bytes(32, "little")


def new_key() -> tuple[bytes, str]:
    """A throwaway key: (its secret, its public half as hex, as RELEASE_KEYS holds keys)."""
    secret = os.urandom(32)
    return secret, public_key(secret).hex()


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "keygen":
        secret, public = new_key()
        Path(argv[1]).write_bytes(secret)
        print(public)
        return 0
    if len(argv) == 3 and argv[0] == "sign":
        Path(argv[2] + ".sig").write_bytes(sign(Path(argv[1]).read_bytes(), Path(argv[2]).read_bytes()))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
