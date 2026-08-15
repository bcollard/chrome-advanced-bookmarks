# Shipping a release to the Chrome Web Store

Operational checklist for publishing a new version of Advanced Bookmarks. The
account already exists and the item is already live, so this covers the update
path only. First-time setup notes are at the bottom.

**Dashboard:** <https://chrome.google.com/webstore/devconsole>
**Item ID:** `lllhlboikkambnobbpjifhkpckiigdio`

---

## 0 — Context: what actually drives ranking

Worth keeping in mind while filling in the fields below, because it changes where
the effort is worth spending. Per Google's
[discoverability docs](https://developer.chrome.com/docs/webstore/discovery),
store search ranks on listing metadata **plus** user ratings and usage statistics
(installs versus uninstalls over time).

At low install counts the metadata is the only lever you control, but it is not
the dominant one — the flywheel only starts turning with installs and reviews
coming from outside the store. So: fill the listing out completely (§4), then do
§8. Skipping §8 makes the rest largely decorative.

---

## 1 — Pre-flight

```bash
make validate     # manifest, _locales key parity, name/summary length limits
```

Then walk the checklist:

- [ ] `manifest.json` → `"version"` bumped (the store rejects a re-upload of an existing version)
- [ ] `docs/index.html` → `softwareVersion` in the JSON-LD block matches
- [ ] Every `_locales/<locale>/messages.json` carries the same keys (validate enforces this)
- [ ] Every new UI string is translated in all 7 locales, not just `en`
- [ ] `store-listing/<locale>.md` updated if any feature copy changed
- [ ] `docs/privacy.html` → "Last updated" and version line still accurate
- [ ] Loaded unpacked and clicked through: add, edit, remove, new folder, non-bookmarkable page (e.g. `chrome://extensions`)
- [ ] Checked the popup in at least one non-English locale — see below

### Testing a locale without changing your system language

Launch a throwaway Chrome profile with a forced UI language:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir=/tmp/ab-locale-test --lang=fr
```

Then load the unpacked extension in that window. `chrome.i18n` follows the
browser UI language, so the popup should come up fully translated.

---

## 2 — Regenerate assets (only if they changed)

```bash
make icons     # PNG icons
make promo     # promo/tile-small-440x280.png + promo/tile-marquee-1400x560.png
```

`make promo` renders `promo/*.html` through headless Chrome. To iterate on the
design, open those HTML files directly in a browser, edit, then re-run.

---

## 3 — Package and upload

```bash
make pack      # runs icons + validate, then builds build/advanced-bookmarks.zip
```

Confirm the zip contains **only** runtime files — `manifest.json`, `popup.*`,
`icons/`, `_locales/`. It should be ~20 KiB. If it is hundreds of KiB, something
from `screenshots/`, `docs/` or `promo/` leaked in; check `ZIP_EXCLUDES` in the
Makefile.

Then, in the dashboard: **select the item → Package → Upload new package →**
upload `build/advanced-bookmarks.zip`.

> Upload the package **before** touching the listing text. The language selector
> on the Store listing tab only offers languages that the uploaded package
> declares under `_locales/`, so a fresh upload is what unlocks the six
> non-English tabs.

---

## 4 — Store listing, per language

The **Store listing** tab has a language dropdown at the top. Do English first,
then each other locale.

| Field | Where it comes from |
|---|---|
| Name | `_locales/<locale>/messages.json` → `extName` — automatic, read-only in the dashboard |
| Summary | `_locales/<locale>/messages.json` → `extDescription` — automatic |
| **Detailed description** | **paste by hand** from `store-listing/<locale>.md` |
| **Screenshots** | **upload per language** (the same 1280×800 files are fine) |

So per locale the manual work is: switch language → paste the description →
attach screenshots → save.

### Fields that are global (set once, on any language tab)

| Field | Value |
|---|---|
| Category | **Tools** — keep it there; a bookmark dialog is a utility, not a planning app |
| Store icon | `icons/icon128.png` |
| Small promo tile | `promo/tile-small-440x280.png` |
| Marquee promo tile | `promo/tile-marquee-1400x560.png` |
| Website | `https://bcollard.github.io/chrome-advanced-bookmarks/` |
| Support URL | `https://github.com/bcollard/chrome-advanced-bookmarks/issues` |

### Screenshots

Five max, 1280×800, no padding, square corners. Order matters — the first one is
the thumbnail. Lead with the dropdown open mid-search, since that is the one
thing the listing has to communicate in a single glance.

Source files live in `screenshots/`. `make resize-screenshots` normalizes new
captures to 1280×800.

### Copy rules the descriptions already follow

Do not "improve" them into a policy violation. Per the
[listing guidelines](https://developer.chrome.com/docs/webstore/best-listing):

- Summary: plain text, ≤132 chars, no HTML — `make validate` checks this
- No superlatives ("fastest", "best"), no generic praise, no naming competitors
- No repeated keywords — keyword spam is grounds for **suspension**, not just rejection

---

## 5 — Privacy tab

Unchanged release to release, but re-confirm it every time — a blank field here
blocks submission.

| Field | Value |
|---|---|
| Single purpose | Bookmark management: saving and organizing bookmarks into folders |
| `bookmarks` justification | Read the user's folder tree to make it searchable, and create, update, move or delete bookmarks on request |
| `tabs` justification | Read the active tab's title and URL to pre-fill the bookmark form |
| Remote code | **No** — all code is in the package |
| Data collection | **None** — tick every "does not collect" box |
| Privacy policy URL | `https://bcollard.github.io/chrome-advanced-bookmarks/privacy.html` |

Then tick the three data-usage compliance certifications at the bottom.

---

## 6 — Submit

**Submit for review**, top right. Reviews for an update on an existing item
typically land in 1–3 business days; a change of name or category can push it
longer since it gets a fuller pass.

You can choose to **publish immediately on approval** or hold it. Holding is
useful if you want the launch posts in §8 to go out the same day the new listing
goes live.

### If it gets rejected

| Reason given | What it usually means here |
|---|---|
| "Single purpose not clear" | The description drifted into unrelated features — trim back to bookmarking |
| "Permissions not justified" | The §5 justification text no longer matches the manifest |
| "Keyword spam" | A target term got repeated across name + summary + description; thin it out |
| "Screenshots don't reflect functionality" | Re-shoot with the folder dropdown open and results visible |
| "Metadata inconsistent across locales" | A translation promises a feature the English one doesn't (or vice versa) |

Fix, then resubmit — the review clock restarts.

---

## 7 — After it goes live

- [ ] Tag the release: `git tag v1.2.0 && git push --tags`
- [ ] Enable GitHub Pages if not already on: repo **Settings → Pages → Source: `main` / `/docs`**
- [ ] Load the live listing in an incognito window and read it as a stranger would
- [ ] Check the listing in French and Japanese (`?hl=fr`, `?hl=ja`) — confirm the translations actually took
- [ ] Submit the landing page to [Google Search Console](https://search.google.com/search-console) and request indexing

---

## 8 — Distribution (the part that moves the needle)

Ranking follows installs; installs do not follow ranking when you are starting
near zero. This section is the actual growth work — treat it as part of the
release, not as optional follow-up.

**Launch day**

- [ ] **Show HN** — the fuzzy-folder-search angle is the hook, not "a bookmark manager". Link the GitHub repo, not the store
- [ ] **Product Hunt** — schedule for 00:01 PT
- [ ] **Reddit** — r/chrome, r/productivity, r/browsers. Read each sub's self-promotion rule first; lead with the problem, not the product

**Ongoing**

- [ ] Make the GitHub repo public with topics: `chrome-extension`, `bookmarks`, `fuzzy-search`, `manifest-v3`, `productivity`
- [ ] List it on [alternativeto.net](https://alternativeto.net)
- [ ] Answer existing Reddit / Super User / Stack Exchange questions about picking bookmark folders quickly — these keep sending traffic for years
- [ ] Ask early users for a review. Zero ratings is a hard ceiling on store ranking, and the first handful matter disproportionately
- [ ] Ship something small every couple of months. "Last updated" is a freshness signal, and a stale item drifts down

**Measuring it**

The dashboard's stats tab gives installs, uninstalls and weekly users. Uninstall
rate is the number that feeds ranking most directly — if it climbs after a
release, the onboarding regressed, not the marketing.

---

## Appendix A — First-time setup (already done)

Kept for reference:

1. Register at <https://chrome.google.com/webstore/devconsole> — one-time **$5 USD** fee, per Google account, unlimited items
2. Accept the Developer Agreement
3. **New item** → upload the zip → fill listing → submit
4. First review of a brand-new item runs longer than an update: 3–7 business days

Chrome signs and packages the `.crx` on their end. Never upload a `.crx` — the
store only accepts a plain `.zip`.

## Appendix B — Self-distribution outside the store

Only relevant for enterprise or local installs.

```bash
make sign      # wraps Chrome's --pack-extension
```

- On first run Chrome generates `build/advanced-bookmarks.pem`. **Keep it.** It is the extension's permanent identity; a different key means a different extension to Chrome
- Self-distributed `.crx` files are blocked on Windows and macOS unless deployed through enterprise policy (Group Policy / MDM)
- For public distribution the Web Store is the only practical route

## Appendix C — Links

- [Developer Dashboard](https://chrome.google.com/webstore/devconsole)
- [Best practices for listings](https://developer.chrome.com/docs/webstore/best-listing)
- [Discoverability and search ranking](https://developer.chrome.com/docs/webstore/discovery)
- [Program policies](https://developer.chrome.com/docs/webstore/program-policies/)
- [Review process](https://developer.chrome.com/docs/webstore/review-process/)
- [Internationalization (`chrome.i18n`)](https://developer.chrome.com/docs/extensions/reference/api/i18n)
