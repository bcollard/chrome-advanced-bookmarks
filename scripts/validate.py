#!/usr/bin/env python3
"""
Validate manifest.json and verify all referenced files exist.
Run from the project root: python3 scripts/validate.py
"""

import json
import os
import sys


def check_file(path: str, errors: list) -> None:
    if not path:
        return
    if os.path.exists(path):
        print(f"  OK: {path}")
    else:
        errors.append(path)
        print(f"  MISSING: {path}")


def main() -> int:
    errors: list[str] = []

    # 1. Parse manifest.json
    try:
        with open("manifest.json") as f:
            manifest = json.load(f)
        print("manifest.json — valid JSON")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"manifest.json — ERROR: {e}", file=sys.stderr)
        return 1

    # 2. Action popup
    popup = manifest.get("action", {}).get("default_popup", "")
    check_file(popup, errors)

    # 3. Action icons
    for size, path in manifest.get("action", {}).get("default_icon", {}).items():
        check_file(path, errors)

    # 4. Top-level icons
    for size, path in manifest.get("icons", {}).items():
        check_file(path, errors)

    # 5. Background service worker
    sw = manifest.get("background", {}).get("service_worker", "")
    check_file(sw, errors)

    # 6. Content scripts
    for cs in manifest.get("content_scripts", []):
        for f in cs.get("js", []) + cs.get("css", []):
            check_file(f, errors)

    # 7. Web-accessible resources
    for entry in manifest.get("web_accessible_resources", []):
        for res in entry.get("resources", []):
            if "*" not in res:
                check_file(res, errors)

    if errors:
        print(f"\n{len(errors)} missing file(s):")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("\nAll referenced files present. Ready to pack.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
