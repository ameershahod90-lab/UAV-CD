"""
Internationalisation (i18n) — UAV-CD-APP
============================================
GNU gettext-based translation infrastructure for report export.

Public API
----------
- ``Language``         — enum of supported languages (EN, AR) with RTL flag
- ``Translator``       — bound to one language; translates keys to strings
- ``load_translator``  — load a translator from compiled ``.mo`` catalogues
- ``smart_format``     — math-zone-aware ``str.format`` (skips ``$${...}$$``)

Layer: ``core/`` — pure Python, no Qt and no python-docx dependencies.

Catalogue layout::

    app/resources/locales/
      <lang>/LC_MESSAGES/
        reports.po          ← human-editable
        reports.mo          ← compiled (run scripts/compile_messages.py)

Translation keys are abstract identifiers (e.g. ``"section.weight.title"``),
not English source strings. This decouples the translation effort from
small wording changes on the English side.
"""

from app.core.i18n.language import Language
from app.core.i18n.smart_format import smart_format
from app.core.i18n.translator import Translator, load_translator

__all__ = [
    "Language",
    "Translator",
    "load_translator",
    "smart_format",
]
