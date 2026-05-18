"""
Report Renderer — Format-Agnostic Builder API
===============================================
Defines the abstract ReportBuilder interface that all sections use to
emit content, and the ReportConfig user-preference dataclass.

Sections never import python-docx, reportlab, or any output format library.
They call methods on ReportBuilder, and the concrete renderer translates
those calls into the target format.

This module is pure Python — NO Qt, NO app.state, NO app.ui.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.core.i18n import Language


# ===========================================================================
# Export Format
# ===========================================================================

class ExportFormat(Enum):
    DOCX = "Word (.docx)"
    PDF  = "PDF (.pdf)"      # future — via reportlab or docx2pdf


# ===========================================================================
# Report Config  (user preferences from the export dialog)
# ===========================================================================

@dataclass
class ReportConfig:
    """
    All user-configurable export options.
    Passed from the ExportDialog to ExportService.export().
    """

    report_title: str = "UAV Conceptual Design Report"
    author:       str = ""
    revision:     str = "1.0"
    format:       ExportFormat = ExportFormat.DOCX
    output_path:  str = ""

    # ── Section manifest ─────────────────────────────────────────────
    # Populated by ExportDialog from SectionRegistry.default_manifest()
    # and then modified by the user (enable/disable/reorder).
    sections: list = field(default_factory=list)   # list[SectionEntry]

    # ── Content options ──────────────────────────────────────────────
    include_equations:    bool = True
    include_sadraey_refs: bool = True
    logo_path: Optional[str]  = None   # path to custom logo image

    # ── Language ─────────────────────────────────────────────────────
    # English by default; AR flips paragraph direction, complex-script
    # font, and translates every catalogued string.
    language: Language = Language.EN


# ===========================================================================
# ReportBuilder  (abstract format-agnostic content API)
# ===========================================================================

class ReportBuilder(ABC):
    """
    Abstract builder that converts section content calls into format output.

    Concrete implementations:
      DocxBuilder (core/reports/renderers/docx_renderer.py) — Word
      PdfBuilder  (future)                                  — PDF

    Method naming conventions:
      add_*   — appends content to the current position in the document
      The builder maintains an internal cursor; content is always appended.
    """

    # ── Structural ────────────────────────────────────────────────────────

    @abstractmethod
    def add_heading(self, text: str, level: int = 1) -> None:
        """
        Add a heading.
        level=1 → chapter heading (e.g. "1. Mission Requirements")
        level=2 → sub-heading    (e.g. "1.1 Performance Targets")
        level=3 → sub-sub        (e.g. "1.1.1 Speed")
        """
        ...

    @abstractmethod
    def add_paragraph(
        self,
        text: str,
        bold: bool = False,
        italic: bool = False,
        indent: bool = False,
    ) -> None:
        """Add a plain text paragraph."""
        ...

    @abstractmethod
    def add_page_break(self) -> None:
        """Insert a hard page break."""
        ...

    # ── Rich content ──────────────────────────────────────────────────────

    @abstractmethod
    def add_table(
        self,
        headers: list[str],
        rows: list[list[str]],
        caption: str = "",
        style: str = "default",
    ) -> None:
        """
        Add a formatted table.
        headers — column header strings
        rows    — list of rows, each a list of cell strings
        caption — optional caption rendered below the table
        style   — hint ("default", "compact") for renderer formatting
        """
        ...

    @abstractmethod
    def add_figure(
        self,
        image_bytes: bytes,
        caption: str = "",
        width_cm: float = 16.0,
    ) -> None:
        """
        Add an image figure.
        image_bytes — PNG bytes (captured from pyqtgraph before export)
        caption     — rendered below the figure
        width_cm    — display width; aspect ratio is preserved
        """
        ...

    @abstractmethod
    def add_equation(self, equation_text: str) -> None:
        """Add a displayed equation block.

        equation_text — LaTeX math source, e.g.
            ``r"\\frac{W}{S} = \\tfrac{1}{2}\\rho_0 V_s^2 C_{L_{\\max}}"``

        The renderer auto-numbers equations as ``(section.sub)``; the
        section counter advances on every level-1 heading, and the sub
        counter resets per section. Sadraey citations should appear once
        in the section's introductory paragraph, not under each equation.
        """
        ...

    @abstractmethod
    def add_key_value_list(
        self,
        items: list[tuple[str, str]],
        columns: int = 2,
    ) -> None:
        """
        Add a two-column key/value list (label: value pairs).
        columns=2 renders as a two-column table.
        """
        ...

    @abstractmethod
    def add_bulleted_list(self, items: list[str]) -> None:
        """Add a bulleted list."""
        ...

    @abstractmethod
    def add_note(self, text: str) -> None:
        """
        Add a styled note/callout block (grey background, italic text).
        Used for analysis notes, assumptions, or warnings.
        """
        ...

    @abstractmethod
    def add_horizontal_rule(self) -> None:
        """Add a visual separator line between major sections."""
        ...

    # ── Finalisation ──────────────────────────────────────────────────────

    @abstractmethod
    def save(self, output_path: str) -> None:
        """Write the built document to disk at output_path."""
        ...
