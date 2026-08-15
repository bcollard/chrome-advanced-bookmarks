#!/usr/bin/env python3
"""
Verify that a published Advanced Bookmarks artifact was built from this source.

    python3 scripts/verify-reproducible.py <downloaded.zip>
    python3 scripts/verify-reproducible.py --self

The gap this closes: the Chrome Web Store signs the .crx itself from an uploaded
.zip. The developer never signs anything and nothing links the published bytes
to a commit, so "the source is on GitHub" is an assertion rather than a fact you
can check.

Because the packer stores entries rather than deflating them, the archive is a
pure function of the source with no toolchain in the way — any Python 3 on any
OS produces the same bytes. So unlike a build that depends on a pinned
compressor, a mismatch here is not explainable as "probably a different
toolchain version": it means the contents genuinely differ. This script says
which files, so the difference can be looked at rather than guessed about.
"""

import hashlib
import os
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def build() -> tuple[bytes, str]:
    """Run the packer and return (archive bytes, path)."""
    result = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "pack.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)
        sys.exit("\nverify: the build failed\n")

    build_dir = os.path.join(ROOT, "build")
    zips = [f for f in os.listdir(build_dir) if f.endswith(".zip")]
    if len(zips) != 1:
        sys.exit(
            f"\nverify: expected exactly one .zip in build/, found {len(zips)}.\n"
            "Run `make clean` and try again.\n"
        )
    path = os.path.join(build_dir, zips[0])
    with open(path, "rb") as fh:
        return fh.read(), path


# ─────────────────────────────────────────
# Minimal zip reader, so a mismatch is explained per file rather than as one
# opaque hash difference.
# ─────────────────────────────────────────

def find_eocd(buf: bytes) -> int:
    start = max(0, len(buf) - 22 - 0xFFFF)
    for i in range(len(buf) - 22, start - 1, -1):
        if struct.unpack_from("<I", buf, i)[0] == 0x06054B50:
            return i
    return -1


def read_zip(buf: bytes) -> dict[str, bytes]:
    """Return {archive path: uncompressed contents}."""
    import zlib

    eocd = find_eocd(buf)
    if eocd < 0:
        raise ValueError("not a zip archive (no end-of-central-directory record)")

    count = struct.unpack_from("<H", buf, eocd + 10)[0]
    pos = struct.unpack_from("<I", buf, eocd + 16)[0]

    files: dict[str, bytes] = {}
    for _ in range(count):
        if struct.unpack_from("<I", buf, pos)[0] != 0x02014B50:
            raise ValueError("corrupt central directory")
        method = struct.unpack_from("<H", buf, pos + 10)[0]
        comp_size = struct.unpack_from("<I", buf, pos + 20)[0]
        name_len = struct.unpack_from("<H", buf, pos + 28)[0]
        extra_len = struct.unpack_from("<H", buf, pos + 30)[0]
        comment_len = struct.unpack_from("<H", buf, pos + 32)[0]
        local_offset = struct.unpack_from("<I", buf, pos + 42)[0]
        name = buf[pos + 46 : pos + 46 + name_len].decode("utf-8")

        l_name = struct.unpack_from("<H", buf, local_offset + 26)[0]
        l_extra = struct.unpack_from("<H", buf, local_offset + 28)[0]
        start = local_offset + 30 + l_name + l_extra
        raw = buf[start : start + comp_size]

        files[name] = zlib.decompress(raw, -15) if method == 8 else raw
        pos += 46 + name_len + extra_len + comment_len

    return files


def compare(published: bytes, local: bytes) -> list[str]:
    a = read_zip(published)
    b = read_zip(local)
    differences = []
    for name in sorted(set(a) | set(b)):
        left, right = a.get(name), b.get(name)
        if left is None:
            differences.append(f"  + {name} (only in the local build)")
        elif right is None:
            differences.append(f"  - {name} (only in the published artifact)")
        elif left != right:
            differences.append(f"  ~ {name} ({len(right)} vs {len(left)} bytes)")
    return differences


# ─────────────────────────────────────────

def git(*args: str) -> str | None:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def main() -> int:
    args = [a for a in sys.argv[1:]]
    self_only = "--self" in args
    target = next((a for a in args if not a.startswith("-")), None)

    if not self_only and not target:
        print(
            "\nUsage:\n"
            "  python3 scripts/verify-reproducible.py <downloaded.zip>"
            "   compare against a published artifact\n"
            "  python3 scripts/verify-reproducible.py --self"
            "             check the build is stable across two runs\n",
            file=sys.stderr,
        )
        return 2

    print("\nAdvanced Bookmarks reproducible-build check")
    print(f"  python   {sys.version.split()[0]}")
    commit = git("rev-parse", "HEAD")
    if commit:
        dirty = git("status", "--porcelain")
        print(f"  commit   {commit}{'  (working tree has uncommitted changes)' if dirty else ''}")
    else:
        print("  commit   unavailable (not a git checkout)")

    print("\nBuilding...")
    first, path = build()
    print(f"  sha256   {sha256(first)}")

    # Two builds from the same source must agree before a comparison against a
    # published artifact means anything.
    print("\nBuilding again to confirm the build is stable...")
    second, _ = build()
    print(f"  sha256   {sha256(second)}")

    if first != second:
        print("\nFAIL: the build is not deterministic — two runs of the same source differ\n",
              file=sys.stderr)
        for line in compare(first, second):
            print(line, file=sys.stderr)
        print("", file=sys.stderr)
        return 1

    print("\nOK: the build is stable across runs")

    if self_only:
        print("")
        return 0

    candidates = [target, os.path.join(os.getcwd(), target)]
    found = next((p for p in candidates if os.path.isfile(p)), None)
    if not found:
        print(f"\nFAIL: not found: {target}\n", file=sys.stderr)
        return 1

    with open(found, "rb") as fh:
        published = fh.read()

    print(f"\nComparing against {found}")
    print(f"  sha256   {sha256(published)}")

    if published == first:
        print("\nOK: identical — the published artifact was built from this source\n")
        return 0

    print("\nFAIL: the artifacts differ\n", file=sys.stderr)
    try:
        differences = compare(published, first)
    except ValueError as exc:
        print(f"  could not read the published archive: {exc}\n", file=sys.stderr)
        return 1

    if not differences:
        # Same contents, different container — a different zip writer, not a
        # different extension.
        print("  Every file inside is identical; only the archive framing differs.",
              file=sys.stderr)
        print("  That points at the packaging step, not the extension contents.\n",
              file=sys.stderr)
        return 1

    for line in differences:
        print(line, file=sys.stderr)
    print(
        "\n  This build does not depend on a compressor or a toolchain version, so\n"
        "  a difference here is not explainable as a version mismatch. Check first:\n"
        "    - you are on the tag the release was cut from (git checkout vX.Y.Z)\n"
        "    - the working tree has no uncommitted changes\n"
        "\n  If neither explains it, please open a security advisory:\n"
        "  https://github.com/bcollard/chrome-advanced-bookmarks/security/advisories/new\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
