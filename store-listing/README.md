# Store listing copy

Ready-to-paste text for the Chrome Web Store Developer Dashboard, one file per
language. Each file has three blocks that map 1:1 to dashboard fields:

| Block in the file | Dashboard field | Limit |
|---|---|---|
| `## Name` | Store listing → Name | 75 chars (comes from `_locales/<locale>/messages.json` → `extName`) |
| `## Summary` | Store listing → Summary | **132 chars**, plain text, no HTML |
| `## Detailed description` | Store listing → Description | 16 000 chars |

## How localized listings work

The dashboard shows a language selector at the top of the **Store listing** tab.
It only offers the languages the uploaded `.zip` declares — i.e. the ones present
under `_locales/`. So the order is always:

1. Upload the new `.zip` (which contains `_locales/`)
2. *Then* switch language in the dashboard and paste each translation

Name and summary are pulled from `_locales/<locale>/messages.json` automatically.
The **detailed description and screenshots are not** — those you paste per
language, by hand, from the files here.

## Rules these texts follow

Straight from the [store listing guidelines](https://developer.chrome.com/docs/webstore/best-listing):

- Summary is plain text, no HTML, at or under 132 characters
- No superlatives ("fastest", "best"), no generic praise, no comparisons to other
  extensions — all three are called out as things to avoid
- No repeated keywords: keyword spam is grounds for suspension, so each target
  term appears where it genuinely belongs and nowhere else
- Description opens with an overview paragraph, then a short feature list

## Keeping them in sync

If you edit a summary here, edit `extDescription` in the matching
`_locales/<locale>/messages.json` too — the manifest is what the store actually
reads. `make validate` checks that every locale carries the same keys and that no
summary exceeds 132 characters.
