#!/usr/bin/env python3
"""
Package the extension into the .zip uploaded to the Chrome Web Store.

Deliberately not `zip -r`: that embeds mtimes, takes entries in filesystem
order and writes Unix permission bits, so the archive depends on when and where
it was built. An artifact that is not a pure function of the source cannot be
attested to in any way a user can check.

The gap being closed: the Chrome Web Store signs the .crx itself from an
uploaded .zip. The developer never signs anything, and nothing links the
published bytes to a commit — so "the source is on GitHub" is an assertion
rather than something anyone can verify. Making the build reproducible, then
attesting to it in CI, is what turns it into a fact.

Run from the project root:
    python3 scripts/pack.py
"""

import hashlib
import json
import os
import struct
import sys
import zlib

# ─────────────────────────────────────────
# What ships
# ─────────────────────────────────────────

# An explicit allowlist, not an exclude list. The previous exclude-based packer
# silently shipped 484 KiB of store screenshots to every user because nobody
# had remembered to add a new directory to it. Anything not named here does not
# reach the artifact, so a new top-level directory is inert by default.
INCLUDE = [
    "manifest.json",
    "popup.html",
    "popup.css",
    "popup.js",
    "icons/icon16.png",
    "icons/icon48.png",
    "icons/icon128.png",
]
INCLUDE_GLOBS = [
    ("_locales", "messages.json"),  # _locales/<locale>/messages.json
]


def collect(root: str) -> list[tuple[str, bytes]]:
    """Return [(archive_path, contents)] for everything that ships."""
    entries: list[tuple[str, bytes]] = []

    for rel in INCLUDE:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            sys.exit(f"pack: missing required file: {rel}")
        with open(path, "rb") as fh:
            entries.append((rel, fh.read()))

    for parent, filename in INCLUDE_GLOBS:
        base = os.path.join(root, parent)
        if not os.path.isdir(base):
            continue
        for locale in sorted(os.listdir(base)):
            path = os.path.join(base, locale, filename)
            if os.path.isfile(path):
                with open(path, "rb") as fh:
                    entries.append((f"{parent}/{locale}/{filename}", fh.read()))

    return entries


def check_manifest_covered(root: str, entries: list[tuple[str, bytes]]) -> None:
    """Every file manifest.json points at must actually be in the archive."""
    with open(os.path.join(root, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)

    referenced = set()
    referenced.add(manifest.get("action", {}).get("default_popup", ""))
    referenced.update(manifest.get("icons", {}).values())
    referenced.update(manifest.get("action", {}).get("default_icon", {}).values())
    referenced.discard("")

    shipped = {path for path, _ in entries}
    missing = sorted(referenced - shipped)
    if missing:
        sys.exit(
            "pack: manifest.json references files the archive does not contain:\n  "
            + "\n  ".join(missing)
            + "\n\nAdd them to INCLUDE in scripts/pack.py."
        )


# ─────────────────────────────────────────
# Deterministic ZIP writer
# ─────────────────────────────────────────

# Three sources of nondeterminism removed:
#
#   1. Timestamps — every entry gets a fixed DOS timestamp instead of its mtime.
#      1980-01-01 is the earliest instant the DOS format can encode.
#   2. Entry order — sorted by path rather than taken in readdir order, which
#      varies by filesystem.
#   3. Metadata — no extra fields, no comments, no external attributes (which
#      would otherwise encode the umask), no data descriptors.
#
# Entries are STORED rather than deflated, which is the one place this diverges
# from the approach used in headsmith. Deflate output is only stable for a given
# zlib build, which forces the toolchain version to become part of the
# reproducibility contract — headsmith pins Node in .nvmrc for exactly that
# reason, and its verify script has to soften a mismatch into "probably a
# different Node". This extension has no build step and a 53 KiB payload, so
# storing costs ~33 KiB on a one-time download and buys an artifact that is
# byte-identical from any Python 3 on any OS. The verification becomes an
# unqualified yes or no, which is the entire point.

DOS_EPOCH_DATE = (1 << 5) | 1  # 1980-01-01
DOS_EPOCH_TIME = 0  # 00:00:00

SIG_LOCAL = 0x04034B50
SIG_CENTRAL = 0x02014B50
SIG_EOCD = 0x06054B50

METHOD_STORED = 0


def create_zip(entries: list[tuple[str, bytes]]) -> bytes:
    locals_: list[bytes] = []
    centrals: list[bytes] = []
    offset = 0

    for path, data in sorted(entries, key=lambda e: e[0]):
        # Forward slashes regardless of host platform: a backslash is a literal
        # character in a zip entry name, not a separator.
        name = path.replace("\\", "/").encode("utf-8")
        crc = zlib.crc32(data) & 0xFFFFFFFF

        local = struct.pack(
            "<IHHHHHIIIHH",
            SIG_LOCAL,
            20,                 # version needed
            0,                  # flags — no data descriptor, no UTF-8 bit
            METHOD_STORED,
            DOS_EPOCH_TIME,
            DOS_EPOCH_DATE,
            crc,
            len(data),          # compressed size
            len(data),          # uncompressed size
            len(name),
            0,                  # no extra field
        )
        locals_.extend((local, name, data))

        central = struct.pack(
            "<IHHHHHHIIIHHHHHII",
            SIG_CENTRAL,
            20,                 # version made by — MS-DOS, not Unix, so no file mode
            20,                 # version needed
            0,                  # flags
            METHOD_STORED,
            DOS_EPOCH_TIME,
            DOS_EPOCH_DATE,
            crc,
            len(data),
            len(data),
            len(name),
            0,                  # extra length
            0,                  # comment length
            0,                  # disk number start
            0,                  # internal attributes
            0,                  # external attributes — no file mode
            offset,
        )
        centrals.extend((central, name))

        offset += len(local) + len(name) + len(data)

    central_buf = b"".join(centrals)
    eocd = struct.pack(
        "<IHHHHIIH",
        SIG_EOCD,
        0,                      # disk number
        0,                      # central directory start disk
        len(entries),
        len(entries),
        len(central_buf),
        offset,
        0,                      # no archive comment
    )

    return b"".join(locals_) + central_buf + eocd


# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────

def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    with open(os.path.join(root, "manifest.json"), encoding="utf-8") as fh:
        version = json.load(fh)["version"]

    entries = collect(root)
    check_manifest_covered(root, entries)

    blob = create_zip(entries)
    digest = hashlib.sha256(blob).hexdigest()

    out_dir = os.path.join(root, "build")
    os.makedirs(out_dir, exist_ok=True)
    name = f"advanced-bookmarks-{version}.zip"
    out_path = os.path.join(out_dir, name)
    with open(out_path, "wb") as fh:
        fh.write(blob)

    print(f"\npacked {len(entries)} file(s)\n")
    for path, data in sorted(entries):
        print(f"  {path:38} {len(data):>7,} B")
    print(f"\n  build/{name}")
    print(f"  {len(blob) / 1024:.1f} KiB")
    print(f"  sha256  {digest}\n")

    # Consumed by .github/workflows/release.yml
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            fh.write(f"zip_path={out_path}\nzip_name={name}\nsha256={digest}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
