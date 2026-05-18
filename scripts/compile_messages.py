"""
Compile gettext message catalogues (.po → .mo).

Run this whenever you edit ``app/resources/locales/<lang>/LC_MESSAGES/reports.po``
to regenerate the binary ``.mo`` catalogues the Translator loads at runtime.

Usage::

    python scripts/compile_messages.py

The compiled ``.mo`` files are committed to the repo so end users don't
need to run this themselves — it only matters for developers editing
translations.
"""

from __future__ import annotations

import sys
from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po


def compile_catalogue(po_path: Path) -> Path:
    """Compile a single .po file to .mo in the same directory."""
    mo_path = po_path.with_suffix(".mo")
    with po_path.open("rb") as src:
        catalogue = read_po(src)
    with mo_path.open("wb") as dst:
        write_mo(dst, catalogue)
    return mo_path


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    locales_dir = repo_root / "app" / "resources" / "locales"

    if not locales_dir.exists():
        print(f"error: locales directory not found at {locales_dir}", file=sys.stderr)
        return 1

    po_files = list(locales_dir.rglob("*.po"))
    if not po_files:
        print(f"error: no .po files found under {locales_dir}", file=sys.stderr)
        return 1

    for po in po_files:
        mo = compile_catalogue(po)
        rel = mo.relative_to(repo_root)
        print(f"compiled {rel}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
