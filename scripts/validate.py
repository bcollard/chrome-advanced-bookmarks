#!/usr/bin/env python3
"""
Validate manifest.json before packing:
  - manifest parses and every file it references exists
  - every __MSG_key__ placeholder resolves in the default locale
  - all locales carry the same keys (no half-translated release)
  - store name / summary stay inside the Chrome Web Store limits
  - every data-i18n key used by popup.html and popup.js is defined

Run from the project root: python3 scripts/validate.py
"""

import json
import os
import re
import sys

# Chrome Web Store listing limits
NAME_LIMIT = 75
SUMMARY_LIMIT = 132


def check_file(path: str, errors: list) -> None:
    if not path:
        return
    if os.path.exists(path):
        print(f"  OK: {path}")
    else:
        errors.append(f"missing file: {path}")
        print(f"  MISSING: {path}")


def load_locales(errors: list) -> dict:
    """Return {locale: {key: message}} for every _locales/<locale>/messages.json."""
    locales = {}
    if not os.path.isdir("_locales"):
        return locales

    for locale in sorted(os.listdir("_locales")):
        path = os.path.join("_locales", locale, "messages.json")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}: invalid JSON ({exc})")
            continue
        locales[locale] = {k: v.get("message", "") for k, v in raw.items()}
    return locales


def check_locales(manifest: dict, locales: dict, errors: list) -> None:
    default = manifest.get("default_locale")

    if not default:
        if any("__MSG_" in json.dumps(manifest) for _ in [0]):
            errors.append('manifest uses __MSG_ placeholders but has no "default_locale"')
        return

    print(f"\n_locales — default locale: {default}")

    if default not in locales:
        errors.append(f'default_locale "{default}" has no _locales/{default}/messages.json')
        return

    # 1. Every placeholder in the manifest resolves in the default locale
    placeholders = set(re.findall(r"__MSG_([A-Za-z0-9_@]+)__", json.dumps(manifest)))
    for key in sorted(placeholders):
        if key in locales[default]:
            print(f"  OK: __MSG_{key}__")
        else:
            errors.append(f"__MSG_{key}__ is not defined in _locales/{default}/messages.json")
            print(f"  UNRESOLVED: __MSG_{key}__")

    # 2. Every locale carries the same keys as the default one
    reference = set(locales[default])
    for locale, messages in sorted(locales.items()):
        if locale == default:
            continue
        missing = reference - set(messages)
        extra = set(messages) - reference
        if missing or extra:
            detail = []
            if missing:
                detail.append(f"missing {sorted(missing)}")
            if extra:
                detail.append(f"unknown {sorted(extra)}")
            errors.append(f"_locales/{locale}: " + "; ".join(detail))
            print(f"  KEY MISMATCH: {locale} — " + "; ".join(detail))
        else:
            print(f"  OK: {locale} ({len(messages)} keys)")

    # 3. Store listing limits, per locale
    print("\nStore listing limits")
    for locale, messages in sorted(locales.items()):
        name = messages.get("extName", "")
        summary = messages.get("extDescription", "")

        problems = []
        if len(name) > NAME_LIMIT:
            problems.append(f"name {len(name)}>{NAME_LIMIT}")
        if len(summary) > SUMMARY_LIMIT:
            problems.append(f"summary {len(summary)}>{SUMMARY_LIMIT}")
        if "\n" in summary:
            problems.append("summary contains a newline (must be plain single-line text)")

        if problems:
            errors.append(f"_locales/{locale}: " + ", ".join(problems))
            print(f"  TOO LONG: {locale} — " + ", ".join(problems))
        else:
            print(f"  OK: {locale} — name {len(name)}/{NAME_LIMIT}, summary {len(summary)}/{SUMMARY_LIMIT}")


def check_ui_keys(locales: dict, default: str, errors: list) -> None:
    """Every key the popup asks for at runtime must exist in the default locale."""
    if default not in locales:
        return

    used = set()
    for path in ("popup.html", "popup.js"):
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        used |= set(re.findall(r'data-i18n(?:-placeholder)?="([A-Za-z0-9_]+)"', source))
        used |= set(re.findall(r"\bt\('([A-Za-z0-9_]+)'\)", source))

    print(f"\nUI message keys — {len(used)} referenced by popup.html / popup.js")
    unknown = sorted(used - set(locales[default]))
    for key in unknown:
        errors.append(f"popup references undefined message key: {key}")
        print(f"  UNDEFINED: {key}")

    unused = sorted(set(locales[default]) - used - {"extName", "extDescription", "cmdOpenDialog"})
    if unused:
        print(f"  note: defined but unused — {', '.join(unused)}")
    if not unknown:
        print("  OK: all referenced keys are defined")


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

    # 8. Localization
    locales = load_locales(errors)
    check_locales(manifest, locales, errors)
    check_ui_keys(locales, manifest.get("default_locale", ""), errors)

    if errors:
        print(f"\n{len(errors)} problem(s):")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"\nAll checks passed ({len(locales)} locales). Ready to pack.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
