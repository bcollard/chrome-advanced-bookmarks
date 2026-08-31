# Store screenshots

Nothing in this directory ships to users — `scripts/pack.py` uses an explicit
allowlist, so `screenshots/` is inert by default. These are upload-only assets
for the Chrome Web Store dashboard.

Every image must be **exactly 1280×800** (or 640×400). The store rejects an
entire submission for one wrong-sized image without saying which one, so
`generate-screenshots.py` reads the size back out of the PNG header and fails
rather than trusting the capture.

## Recommended upload order

The dashboard orders screenshots manually, and **the first one is the hero** —
it is the large image at the top of the listing detail page. Lead with the
feature that distinguishes the extension, not with a neutral empty state.

| # | File | What it shows |
|---|---|---|
| 1 | `hero-fuzzy-search.png` | `wpr` matching WordPress, Work Projects, Weekly Prep — fuzzy matching across word boundaries, generated |
| 2 | `fuzzy-search-nested-matches.png` | `bl` reaching Mobile Bookmarks and Kub controller — non-contiguous matches in a real tree |
| 3 | `folder-list-in-page-context.png` | The dialog open over a real page, full folder tree with paths |
| 4 | `new-folder-dialog.png` | Creating a folder inline, without leaving the dialog |
| 5 | `save-to-selected-folder.png` | The saved state |

The rest are alternates kept for future listing edits.

## Generated vs captured

`hero-fuzzy-search.png` is **generated** — run `make screenshots`. Its scene
lives in `src/` and is composed at build time with the real `popup.html`,
`popup.css`, `popup.js` and `_locales` catalogue, driven against a stubbed
`chrome.*` API. So it is a capture of the actual UI, not a mock of it: change
the stylesheet and the screenshot changes with it, and there is no second copy
of the markup to drift.

The catalogue is injected for a reason. Stubbing `chrome.i18n.getMessage` to
return empty strings makes `t()` in `popup.js` fall back to raw message keys,
which silently produced a screenshot showing `newFolderItem` instead of
"New folder…". A missing translation now shows up as a visibly broken image.

The remaining files are **hand-captured** from a real browser in March 2026 and
show the author's own bookmark folders. They are still accurate, but they cannot
be regenerated — port a scene to `src/` if one of them needs updating.

## Adding a scene

Copy `src/hero-fuzzy-search.html`, change the `window.SCENE` block (query,
active tab, bookmark tree) and the caption, then `make screenshots`. Files
starting with `_` are ignored, and `src/.build/` holds the composed pages —
open one in a browser to iterate on a design without re-rendering.

## Localized screenshots

`SCENE_LOCALE=fr make screenshots` renders the popup against
`_locales/fr/messages.json` and writes `hero-fuzzy-search-fr.png`, leaving the
English file untouched.

This is not yet shippable: the **caption is scene copy, not extension UI**, so
it stays English while the dialog translates. Per-language screenshots need the
caption text moved into the scene's locale data first. The dashboard takes
screenshots per language, so this is worth finishing before pushing localized
listings.
