#!/usr/bin/env python3
"""
Render the Chrome Web Store screenshots from screenshots/src/*.html.

The store requires screenshots to be *exactly* 1280×800 or 640×400 and rejects a
whole submission for one wrong-sized image without saying which — so the size is
enforced here rather than trusted. Capturing through DevTools on a Retina display
writes 2560×1600 at devicePixelRatio 2, which is the usual way this goes wrong;
`--force-device-scale-factor=1` is what prevents it.

Each scene is a template that this script composes with the *real* extension:

    screenshots/src/<scene>.html      template with {{POPUP_BODY}} etc.
      + popup.html  (body markup)
      + popup.css   (stylesheet)
      + popup.js    (the shipped logic, driven against a stubbed chrome.*)
    → screenshots/src/.build/<scene>.html      composed, previewable in a browser
    → screenshots/<scene>.png                  1280×800, ready to upload

Composing beats mocking because there is no second copy of the UI to keep in
sync: change popup.css and the screenshot changes with it. It also means a
screenshot can never show a control that no longer exists.

Run from the project root:
    python3 scripts/generate-screenshots.py
    python3 scripts/generate-screenshots.py hero-fuzzy-search   # just one scene
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

WIDTH, HEIGHT = 1280, 800

# Which _locales catalogue the scenes render with. Override to shoot the
# localized screenshots the dashboard takes per language:
#     SCENE_LOCALE=fr python3 scripts/generate-screenshots.py
LOCALE = os.environ.get('SCENE_LOCALE', 'en')
UI_LANGUAGE = {'en': 'en-US', 'pt_BR': 'pt-BR', 'zh_CN': 'zh-CN'}.get(LOCALE, LOCALE)

CHROME_CANDIDATES = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
]


def find_chrome() -> str | None:
    override = os.environ.get('CHROME')
    if override and os.path.exists(override):
        return override
    for path in CHROME_CANDIDATES:
        if os.path.exists(path):
            return path
    for name in ('google-chrome', 'chromium', 'chromium-browser'):
        found = shutil.which(name)
        if found:
            return found
    return None


def popup_body(root: str) -> str:
    """The inner HTML of popup.html's <body>, minus the popup.js script tag.

    The script is re-added by the scene *after* its chrome.* stub is defined, so
    it must not come along with the markup.
    """
    with open(os.path.join(root, 'popup.html'), encoding='utf-8') as fh:
        html = fh.read()

    match = re.search(r'<body[^>]*>(.*)</body>', html, re.DOTALL | re.IGNORECASE)
    if not match:
        sys.exit('generate-screenshots: could not find <body> in popup.html')

    body = match.group(1)
    body, n = re.subn(r'\s*<script\s+src="popup\.js"\s*></script>', '', body, flags=re.IGNORECASE)
    if n != 1:
        sys.exit(
            'generate-screenshots: expected exactly one <script src="popup.js"> in '
            f'popup.html, found {n}. Update this script if the markup changed.'
        )
    return body


def messages(root: str) -> str:
    """_locales/<LOCALE>/messages.json flattened to a {key: message} JSON literal."""
    path = os.path.join(root, '_locales', LOCALE, 'messages.json')
    if not os.path.isfile(path):
        sys.exit(f'generate-screenshots: no catalogue at _locales/{LOCALE}/messages.json')
    with open(path, encoding='utf-8') as fh:
        catalogue = json.load(fh)
    return json.dumps({k: v['message'] for k, v in catalogue.items()}, ensure_ascii=False, indent=2)


def compose(root: str, scene_path: str, build_dir: str) -> str:
    """Substitute the real extension into a scene template. Returns the built path."""
    with open(scene_path, encoding='utf-8') as fh:
        template = fh.read()

    required = ('{{POPUP_BODY}}', '{{POPUP_CSS}}', '{{POPUP_JS}}',
                '{{MESSAGES_JSON}}', '{{UI_LANGUAGE}}')
    missing = [p for p in required if p not in template]
    if missing:
        sys.exit(f'generate-screenshots: {os.path.basename(scene_path)} is missing {", ".join(missing)}')

    page = (template
            .replace('{{POPUP_CSS}}', 'file://' + os.path.join(root, 'popup.css'))
            .replace('{{POPUP_JS}}', 'file://' + os.path.join(root, 'popup.js'))
            .replace('{{MESSAGES_JSON}}', messages(root))
            .replace('{{UI_LANGUAGE}}', UI_LANGUAGE)
            .replace('{{POPUP_BODY}}', popup_body(root)))

    out = os.path.join(build_dir, os.path.basename(scene_path))
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write(page)
    return out


def render(chrome: str, src: str, dst: str) -> bool:
    """Screenshot `src` at exactly WIDTH×HEIGHT into `dst`."""
    if os.path.exists(dst):
        os.remove(dst)

    with tempfile.TemporaryDirectory() as profile:
        cmd = [
            chrome,
            '--headless=new',
            '--disable-gpu',
            '--hide-scrollbars',
            # Without this a Retina display writes 2560×1600 and the store
            # rejects the submission.
            '--force-device-scale-factor=1',
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-background-networking',
            '--disable-sync',
            '--disable-extensions',
            '--disable-component-update',
            # The scene drives the popup on a timer after init resolves; this
            # budget lets those timers run without waiting in real time.
            '--virtual-time-budget=4000',
            f'--user-data-dir={profile}',
            f'--window-size={WIDTH},{HEIGHT}',
            f'--screenshot={dst}',
            f'file://{src}',
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            stderr = proc.stderr
        except subprocess.TimeoutExpired as exc:
            # Chrome sometimes fails to exit even once the PNG is on disk.
            stderr = (exc.stderr or b'').decode(errors='replace')

    if not os.path.exists(dst):
        print(f'  FAILED: {os.path.basename(src)}', file=sys.stderr)
        print(stderr.strip()[:800], file=sys.stderr)
        return False
    return True


def check_size(path: str) -> bool:
    """Verify the PNG really is WIDTH×HEIGHT, read straight from the IHDR chunk."""
    with open(path, 'rb') as fh:
        header = fh.read(24)
    if len(header) < 24 or header[:8] != b'\x89PNG\r\n\x1a\n':
        print(f'  NOT A PNG: {os.path.basename(path)}', file=sys.stderr)
        return False
    width = int.from_bytes(header[16:20], 'big')
    height = int.from_bytes(header[20:24], 'big')
    if (width, height) != (WIDTH, HEIGHT):
        print(
            f'  WRONG SIZE: {os.path.basename(path)} is {width}×{height}, '
            f'need {WIDTH}×{HEIGHT} — the store rejects the whole submission for this',
            file=sys.stderr,
        )
        return False
    return True


def main() -> int:
    chrome = find_chrome()
    if not chrome:
        print('Could not find Chrome. Set CHROME=/path/to/chrome and retry.', file=sys.stderr)
        return 1

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(root, 'screenshots', 'src')
    out_dir = os.path.join(root, 'screenshots')
    build_dir = os.path.join(src_dir, '.build')

    if not os.path.isdir(src_dir):
        print(f'No scenes found: {src_dir} does not exist.', file=sys.stderr)
        return 1

    wanted = sys.argv[1:]
    scenes = sorted(
        f for f in os.listdir(src_dir)
        if f.endswith('.html') and not f.startswith('_')
        and (not wanted or f[:-5] in wanted)
    )
    if not scenes:
        print(f'No matching scenes in screenshots/src/{" for " + ", ".join(wanted) if wanted else ""}',
              file=sys.stderr)
        return 1

    os.makedirs(build_dir, exist_ok=True)

    failures = 0
    for scene in scenes:
        name = scene[:-5]
        built = compose(root, os.path.join(src_dir, scene), build_dir)
        # Localized runs get their own filenames so SCENE_LOCALE=fr cannot
        # silently overwrite the English screenshot that is already uploaded.
        suffix = '' if LOCALE == 'en' else f'-{LOCALE}'
        dst = os.path.join(out_dir, f'{name}{suffix}.png')

        if render(chrome, built, dst) and check_size(dst):
            size_kb = os.path.getsize(dst) // 1024
            print(f'  Created screenshots/{name}{suffix}.png  ({WIDTH}×{HEIGHT}, {size_kb} KiB, {LOCALE})')
        else:
            failures += 1

    if not failures:
        print(f'\nComposed pages left in screenshots/src/.build/ — open one to preview.')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
