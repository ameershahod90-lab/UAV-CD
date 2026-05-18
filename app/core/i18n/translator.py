"""
Translator — language-bound key → string lookup.

Wraps a Babel ``Translations`` catalogue so we can swap implementations
later (e.g. fall back to in-memory dict for tests) without changing the
caller-facing API. Returns plain ``str`` everywhere; never a subclass.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from babel.support import NullTranslations, Translations

from app.core.i18n.language import Language
from app.core.i18n.smart_format import smart_format

_LOG = logging.getLogger(__name__)

# Conventional gettext catalogue base name (matches reports.po / reports.mo)
_DOMAIN = "reports"


class Translator:
    """Translate string keys to a specific language.

    Construction is via ``load_translator(locales_dir, language)``. The
    catalogue is loaded eagerly so any missing-file failure surfaces at
    construction time, not on first ``t()`` call.

    Usage::

        t = translator.t
        rb.add_heading(t("section.weight.title"), level=1)
        rb.add_paragraph(t("dp.summary", area=1.5, unit="m²"))

    Missing keys fall back to the literal key string (with placeholder
    substitution still applied) so authors can use prose keys during
    development and fill in real translations later.
    """

    __slots__ = ("_language", "_catalogue")

    def __init__(self, language: Language, catalogue: NullTranslations) -> None:
        self._language = language
        self._catalogue = catalogue

    @property
    def language(self) -> Language:
        return self._language

    def t(self, key: str, /, **kwargs: Any) -> str:
        """Translate ``key`` and substitute ``{name}`` placeholders.

        Math zones ``$${...}$$`` inside the translation are preserved verbatim
        — they will be converted to inline OMML downstream by the renderer.
        """
        translated = self._catalogue.gettext(key)
        # gettext returns the msgid unchanged when no translation exists; that
        # is the desired fall-back behaviour for unknown keys.
        return smart_format(translated, **kwargs)


def load_translator(locales_dir: Path, language: Language) -> Translator:
    """Load the ``reports`` catalogue for ``language`` from ``locales_dir``.

    ``locales_dir`` should contain ``<lang>/LC_MESSAGES/reports.mo`` files.
    If no compiled catalogue is found for the requested language, a
    ``NullTranslations`` instance is used — every ``t(key)`` will return the
    key unchanged. This is acceptable for English (msgid == display string)
    and for development environments where ``.mo`` files haven't been
    compiled yet.
    """
    try:
        catalogue = Translations.load(
            dirname=str(locales_dir),
            locales=[language.value],
            domain=_DOMAIN,
        )
    except Exception as exc:  # pragma: no cover — defensive
        _LOG.warning(
            "Failed to load translation catalogue for %s: %s — falling back "
            "to NullTranslations (keys returned verbatim)",
            language.value, exc,
        )
        catalogue = NullTranslations()

    if not isinstance(catalogue, Translations):
        # Translations.load() returns NullTranslations when no .mo is found.
        # That's expected for the EN catalogue (we author msgids in English)
        # but worth a debug log for any other language.
        if language is not Language.EN:
            _LOG.info(
                "No compiled .mo catalogue found for %s under %s — keys "
                "will be returned verbatim. Run scripts/compile_messages.py.",
                language.value, locales_dir,
            )

    return Translator(language=language, catalogue=catalogue)
