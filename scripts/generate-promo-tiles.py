#!/usr/bin/env python3
"""
Render the Chrome Web Store promo tiles from promo/*.html to promo/*.png.

The Web Store asks for two promotional images:
    small promo tile   440 × 280   (search results, category pages)
    marquee tile      1400 × 560   (homepage carousel, featured placement)

Rendering is done with headless Chrome, which is already required by
`make sign`, so there is no extra dependency to install. Edit the HTML
files to change the design — open them directly in a browser to preview.

Run from the project root:
    python3 scripts/generate-promo-tiles.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

TILES = [
    ('tile-small.html',   440,  280),
    ('tile-marquee.html', 1400, 560),
]

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


def render(chrome: str, src: str, dst: str, width: int, height: int) -> bool:
    """Screenshot `src` at exactly width×height into `dst`."""
    if os.path.exists(dst):
        os.remove(dst)

    with tempfile.TemporaryDirectory() as profile:
        cmd = [
            chrome,
            '--headless=new',
            '--disable-gpu',
            '--hide-scrollbars',
            '--force-device-scale-factor=1',
            # Chrome otherwise lingers on background network chatter long after
            # the screenshot has been written, so shut all of it off.
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-background-networking',
            '--disable-sync',
            '--disable-extensions',
            '--disable-component-update',
            '--virtual-time-budget=1500',
            f'--user-data-dir={profile}',
            f'--window-size={width},{height}',
            f'--screenshot={dst}',
            f'file://{src}',
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            stderr = proc.stderr
        except subprocess.TimeoutExpired as exc:
            # Chrome sometimes fails to exit even once the PNG is on disk;
            # the file is what we care about.
            stderr = (exc.stderr or b'').decode(errors='replace')

    if not os.path.exists(dst):
        print(f'  FAILED: {os.path.basename(src)}', file=sys.stderr)
        print(stderr.strip()[:800], file=sys.stderr)
        return False
    return True


def main() -> int:
    chrome = find_chrome()
    if not chrome:
        print('Could not find Chrome. Set CHROME=/path/to/chrome and retry.', file=sys.stderr)
        return 1

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    promo_dir = os.path.join(root, 'promo')

    failures = 0
    for filename, width, height in TILES:
        src = os.path.join(promo_dir, filename)
        if not os.path.exists(src):
            print(f'  MISSING: promo/{filename}', file=sys.stderr)
            failures += 1
            continue

        dst = os.path.join(promo_dir, filename.replace('.html', f'-{width}x{height}.png'))
        if render(chrome, src, dst, width, height):
            size_kb = os.path.getsize(dst) // 1024
            print(f'  Created promo/{os.path.basename(dst)}  ({width}×{height}, {size_kb} KiB)')
        else:
            failures += 1

    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
