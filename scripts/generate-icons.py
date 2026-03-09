#!/usr/bin/env python3
"""
Generate PNG icons for the Advanced Bookmarks extension.
Uses only Python standard library — no external dependencies.

Run from the project root:
    python3 scripts/generate-icons.py
"""

import os
import struct
import zlib


# ─────────────────────────────────────────
# Low-level PNG encoder
# ─────────────────────────────────────────

def _make_chunk(chunk_type: bytes, data: bytes) -> bytes:
    payload = chunk_type + data
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    return struct.pack('>I', len(data)) + payload + struct.pack('>I', crc)


def _encode_png_rgb(width: int, height: int, pixels: list[list[tuple]]) -> bytes:
    """Encode a W×H array of (R,G,B) tuples as a PNG byte string."""
    signature = b'\x89PNG\r\n\x1a\n'

    # IHDR: width, height, bit-depth=8, color-type=2 (RGB), compress=0, filter=0, interlace=0
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = _make_chunk(b'IHDR', ihdr_data)

    # IDAT: scanlines with filter-byte 0 prepended
    raw = bytearray()
    for row in pixels:
        raw.append(0)  # filter type None
        for r, g, b in row:
            raw.extend((r, g, b))

    idat = _make_chunk(b'IDAT', zlib.compress(bytes(raw), level=9))
    iend = _make_chunk(b'IEND', b'')

    return signature + ihdr + idat + iend


# ─────────────────────────────────────────
# Geometry helpers
# ─────────────────────────────────────────

def _point_in_polygon(px: float, py: float, poly: list[tuple]) -> bool:
    """Ray-casting point-in-polygon test."""
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _anti_aliased_coverage(px: float, py: float, poly: list[tuple], samples: int = 4) -> float:
    """Return the fraction of sub-pixels (on a √samples × √samples grid) inside poly."""
    import math
    grid = int(math.isqrt(samples))
    hits = 0
    step = 1.0 / (grid + 1)
    for di in range(1, grid + 1):
        for dj in range(1, grid + 1):
            if _point_in_polygon(px + di * step, py + dj * step, poly):
                hits += 1
    return hits / (grid * grid)


# ─────────────────────────────────────────
# Icon drawing
# ─────────────────────────────────────────

# Google Blue
ICON_COLOR = (26, 115, 232)
BG_COLOR   = (255, 255, 255)


def _lerp(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def _blend(bg: tuple, fg: tuple, alpha: float) -> tuple:
    return tuple(_lerp(b, f, alpha) for b, f in zip(bg, fg))


def _bookmark_polygon(size: int) -> list[tuple]:
    """
    Bookmark ribbon shape (pointed bottom).
    Coordinates in pixels for a given icon size.

         top-left ─── top-right
              |             |
         bottom-left   bottom-right
               \\         //
                V (notch)
    """
    m = 0.17   # left/right margin (fraction of size)
    t = 0.06   # top margin
    vx = 0.5   # V-notch horizontal centre
    vy = 0.70  # V-notch vertical position (fraction)

    s = size - 1  # use s so coordinates stay inside the canvas
    return [
        (m * s,        t * s),   # top-left
        ((1 - m) * s,  t * s),   # top-right
        ((1 - m) * s,  s),       # bottom-right
        (vx * s,       vy * s),  # V bottom point
        (m * s,        s),       # bottom-left
    ]


def create_icon(size: int) -> bytes:
    poly = _bookmark_polygon(size)
    pixels = []
    for y in range(size):
        row = []
        for x in range(size):
            coverage = _anti_aliased_coverage(x, y, poly, samples=16)
            if coverage >= 1.0:
                row.append(ICON_COLOR)
            elif coverage > 0.0:
                row.append(_blend(BG_COLOR, ICON_COLOR, coverage))
            else:
                row.append(BG_COLOR)
        pixels.append(row)
    return _encode_png_rgb(size, size, pixels)


# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icons_dir  = os.path.normpath(os.path.join(script_dir, '..', 'icons'))
    os.makedirs(icons_dir, exist_ok=True)

    for size in (16, 48, 128):
        png_data = create_icon(size)
        out_path = os.path.join(icons_dir, f'icon{size}.png')
        with open(out_path, 'wb') as fh:
            fh.write(png_data)
        print(f'  Created {out_path}  ({len(png_data)} bytes)')


if __name__ == '__main__':
    main()
