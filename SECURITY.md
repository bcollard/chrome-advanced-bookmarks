# Security

## Reporting a vulnerability

Report privately through GitHub Security Advisories:

**<https://github.com/bcollard/chrome-advanced-bookmarks/security/advisories/new>**

Please do not open a public issue for a security problem. You should get a first
response within a few days; this is a personal project, not a staffed one, so
please allow for that.

## What is worth reporting

The extension has a small attack surface — no network access, no remote code, no
storage, no host permissions — so the realistic categories are:

- **A build that does not reproduce.** If
  `python3 scripts/verify-reproducible.py <released.zip>` reports differing file
  contents on a clean checkout of the matching tag, that is a security report,
  not a bug report. Check the two mundane causes first (wrong tag, uncommitted
  local changes) — the script prints them.
- **A failed attestation.** If
  `gh attestation verify <zip> --repo bcollard/chrome-advanced-bookmarks` fails
  for an artifact downloaded from a GitHub release here.
- **A published extension that differs from the released artifact.** The zip on
  the Chrome Web Store should be byte-identical to the one attached to the
  matching GitHub release.
- **XSS in the popup.** Bookmark folder titles are attacker-influenceable in the
  sense that they can contain arbitrary text, and the dropdown renders them.
  They are passed through `escapeHtml()`; a way around that is a real finding.
- **Anything that causes a network request.** There is no code that makes one.
  If you observe one, something is very wrong.

## What is not a vulnerability

- The `bookmarks` and `tabs` permissions themselves. Both are required for the
  extension to do its job and are documented in the
  [privacy policy](https://bcollard.github.io/chrome-advanced-bookmarks/privacy.html).
- The extension being able to read the active tab's URL and title. That is the
  `tabs` permission working as declared; the value is used to pre-fill the form
  and is not stored or transmitted.

## Provenance

Releases are built by [`.github/workflows/release.yml`](.github/workflows/release.yml)
on a `v*` tag and carry a
[build provenance attestation](https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds)
binding the artifact to this repository, the commit and the workflow run.

The archive is a pure function of the source: entries are stored rather than
compressed, sorted by path, with fixed timestamps and no filesystem metadata. Any
Python 3 on any OS produces identical bytes, so verification is an unqualified
yes or no rather than something a toolchain difference can explain away.

See [Verify the build](README.md#verify-the-build) for the commands.
