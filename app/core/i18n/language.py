"""Supported languages for report generation."""

from __future__ import annotations

from enum import Enum


class Language(Enum):
    """Languages the report engine can render in.

    The ``value`` is the locale code that gettext uses to find the catalogue
    under ``app/resources/locales/<value>/LC_MESSAGES/``.
    """

    EN = "en"
    AR = "ar"

    @property
    def display_name(self) -> str:
        """Human-readable name in the language itself (for UI selectors)."""
        return {
            Language.EN: "English",
            Language.AR: "العربية",
        }[self]

    @property
    def is_rtl(self) -> bool:
        """True if the language uses right-to-left script."""
        return self is Language.AR

    @property
    def complex_script_font(self) -> str:
        """Word ``cs.fontName`` value used for complex-script runs.

        Calibri (the body default for Latin script) does not contain Arabic
        glyphs, so RTL runs need a dedicated complex-script font. Tahoma is
        chosen because it ships with every Windows install and renders
        Arabic clearly at typical body sizes.
        """
        return "Tahoma" if self.is_rtl else "Calibri"
