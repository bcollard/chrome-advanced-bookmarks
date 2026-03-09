#!/usr/bin/env bash
# Resize all screenshots to 1280x800 (preserves ratio, pads with white).
# Requires ImageMagick (brew install imagemagick).

set -euo pipefail

SCREENSHOTS_DIR="$(dirname "$0")/../screenshots"

if ! command -v magick >/dev/null 2>&1 && ! command -v convert >/dev/null 2>&1; then
  echo "ImageMagick not found. Install with: brew install imagemagick"
  exit 1
fi

CONVERT=$(command -v magick || command -v convert)
count=0

for f in "$SCREENSHOTS_DIR"/*.png "$SCREENSHOTS_DIR"/*.jpg "$SCREENSHOTS_DIR"/*.jpeg; do
  [ -f "$f" ] || continue
  echo "Resizing $f → 1280x800"
  "$CONVERT" "$f" -resize 1280x800 -gravity center -background white -extent 1280x800 "$f"
  count=$((count + 1))
done

echo "Done — resized $count file(s) to 1280x800."
