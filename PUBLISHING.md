# Publishing to the Chrome Web Store

A complete guide from packaging to going live.

---

## Overview

```
Build .zip  →  Pay $5 one-time fee  →  Upload to Dashboard
→  Fill store listing  →  Submit for review  →  Published (1–3 days)
```

Chrome handles all cryptographic signing internally — you never sign a `.crx` yourself when publishing through the Web Store.

---

## Step 1 — Register a developer account

1. Go to <https://chrome.google.com/webstore/devconsole>
2. Sign in with a Google account
3. Pay the **one-time $5 USD** registration fee (credit card required)
4. Accept the Developer Agreement

> This fee is per Google account, not per extension. One account can publish unlimited extensions.

---

## Step 2 — Prepare assets

### Required before submission

| Asset | Spec | Notes |
|---|---|---|
| Extension `.zip` | All source files (no `.git`, no `scripts/`, no `Makefile`) | Run `make pack` |
| Store icon | **128 × 128 px PNG** | Already in `icons/icon128.png` — you may want a higher-quality version |
| Screenshot(s) | **1280 × 800 px** or **640 × 400 px** PNG or JPEG | At least 1 required; up to 5 |

### Optional but strongly recommended

| Asset | Spec |
|---|---|
| Small promo tile | 440 × 280 px PNG (shown in search results) |
| Large promo tile | 920 × 680 px PNG (featured placement) |
| YouTube demo video | Public YouTube URL |

### Taking screenshots

The easiest way to produce exact-size screenshots on macOS:

```bash
# Open Chrome with the popup visible, then:
# Chrome DevTools → device toolbar → set to 1280×800 → screenshot
```

Or use a tool like [Pixelmator](https://www.pixelmator.com) / Figma / Canva to mock up the UI at the required resolution.

---

## Step 3 — Package the extension

```bash
make pack
```

This creates `build/advanced-bookmarks.zip` containing only the files Chrome needs:

```
advanced-bookmarks.zip
├── manifest.json
├── popup.html
├── popup.css
├── popup.js
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

Files excluded from the zip: `scripts/`, `Makefile`, `*.md`, `.git/`, `.DS_Store`.

> **Do not submit a `.crx` file.** The Web Store requires a plain `.zip`. Chrome signs and packages it as `.crx` on their end.

---

## Step 4 — Upload to the Developer Dashboard

1. Go to <https://chrome.google.com/webstore/devconsole>
2. Click **New item**
3. Upload `build/advanced-bookmarks.zip`
4. Chrome will parse the manifest and show a summary — fix any validation errors before continuing

---

## Step 5 — Fill in the store listing

Navigate to each section in the left sidebar:

### Store listing

| Field | Suggested value |
|---|---|
| **Name** | Advanced Bookmarks |
| **Short description** (up to 132 chars) | Save bookmarks instantly with a searchable, filterable folder picker. |
| **Detailed description** | See below |
| **Category** | Productivity |
| **Language** | English |
| **Screenshots** | Upload the 1280×800 screenshots you prepared |
| **Store icon** | Upload a higher-quality 128×128 icon if you have one |

#### Suggested detailed description

```
Advanced Bookmarks replaces Chrome's default bookmark dialog with a faster,
more powerful version — designed for people who actually organise their bookmarks.

KEY FEATURE: Fuzzy searchable folder picker
Instead of scrolling through a flat list, just start typing. The folder
dropdown instantly filters all your bookmark folders using fuzzy search —
find folders even with partial or out-of-order characters. Matches are
highlighted and full breadcrumb trails show you exactly where each folder lives.

SMART DEFAULTS:
• The dialog guesses the best target folder from the page title, so the
  right folder is pre-selected the moment you open it
• The folder you most recently bookmarked into appears at the top of the
  list, making repeat saves to the same folder instant

OTHER FEATURES:
• Edit existing bookmarks — the dialog auto-detects bookmarked pages and
  pre-selects the current folder
• Remove bookmarks directly from the dialog
• Full keyboard navigation (↑↓ arrows, Enter, Escape)
• Configurable keyboard shortcut (suggested: Alt+D)
• No ads, no tracking, no external requests

PERMISSIONS USED:
• bookmarks — to read your folder tree and save/edit/remove bookmarks
• tabs — to read the current page's URL and title (never sent anywhere)
```

### Privacy tab

| Field | Value |
|---|---|
| **Single purpose** | Bookmark management |
| **Does it handle user data?** | No (no data is collected or transmitted) |
| **Privacy policy URL** | Required only if you collect data — leave blank or link to a simple page |

> If you don't collect any data, you can state that in the privacy practices section without needing a dedicated privacy policy URL. However, some reviewers still ask for one. A one-page GitHub Pages site saying "This extension collects no data" is sufficient.

### Distribution tab

| Field | Value |
|---|---|
| **Visibility** | Public |
| **Regions** | All regions (or restrict as needed) |
| **Price** | Free |

---

## Step 6 — Submit for review

1. Click **Submit for review** (top-right of the dashboard)
2. Confirm you comply with the [Chrome Web Store Developer Program Policies](https://developer.chrome.com/docs/webstore/program-policies/)
3. Your extension enters the **Pending review** state

### Review timeline

| Scenario | Typical wait |
|---|---|
| First submission of a new extension | **3–7 business days** |
| Update to an existing extension | **1–3 business days** |
| Extensions with broad permissions | May take longer |

You'll receive an email when the status changes.

### Common rejection reasons (and fixes)

| Rejection reason | Fix |
|---|---|
| "Single purpose not clear" | Tighten the store description to focus only on bookmarking |
| "Permissions not justified" | Add a `"permissions"` explanation in the manifest or description |
| "Screenshots don't show functionality" | Show the popup open with the folder dropdown visible |
| "Privacy policy missing" | Add a simple one-paragraph policy page |

---

## Step 7 — After publication

- Your extension gets a permanent URL: `https://chromewebstore.google.com/detail/<id>`
- Updates: bump `"version"` in `manifest.json`, run `make pack`, upload the new zip in the dashboard, submit for review again
- Respond to user reviews regularly — it helps ranking

---

## About signing (.crx) for self-distribution

If you want to distribute the extension **outside** the Chrome Web Store (e.g. via your own website or enterprise deployment), you need to create and sign a `.crx` file yourself:

```bash
# Chrome can pack and sign a .crx from the command line:
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --pack-extension=/path/to/extension \
  --pack-extension-key=/path/to/key.pem
```

- On first run (no `--pack-extension-key`), Chrome generates a `key.pem` alongside the `.crx` — **keep this file safe and private**. It's your extension's permanent identity.
- For subsequent updates you must use the same `key.pem` or Chrome will treat it as a different extension.
- Self-distributed `.crx` files are blocked by Chrome on Windows/macOS unless deployed via enterprise policy (Group Policy / MDM). The Web Store is the practical path for public distribution.

> **Summary:** For public distribution → use the Web Store (Chrome signs it for you). For internal/enterprise → use `--pack-extension` with a `.pem` key + enterprise policy deployment.

---

## Useful links

- [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole)
- [Developer Program Policies](https://developer.chrome.com/docs/webstore/program-policies/)
- [Publishing guide (official)](https://developer.chrome.com/docs/webstore/publish/)
- [MV3 migration notes](https://developer.chrome.com/docs/extensions/develop/migrate)
- [Extension review process](https://developer.chrome.com/docs/webstore/review-process/)
