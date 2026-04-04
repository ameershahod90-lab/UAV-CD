"""
DocxBuilder — Word (.docx) Report Renderer
============================================
Concrete implementation of ReportBuilder using python-docx.

Design decisions:
  - Uses a custom UAV-CD-APP document style (blue accent, Calibri body).
  - Equation blocks are rendered as styled paragraphs with right-aligned
    equation numbers — no LaTeX images, stays editable in Word.
  - Tables use the built-in "Light Grid Accent 1" style with a bold header row.
  - Figures are written to a NamedTemporaryFile, inserted, then cleaned up.
  - All widths are specified in centimetres (docx uses EMU internally).
"""

from __future__ import annotations

import io
import math
import tempfile
import os
from pathlib import Path
from typing import Optional

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Cm, Pt, RGBColor
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL

from app.core.reports.renderer import ReportBuilder, ReportConfig

# Brand colours
_BLUE   = RGBColor(0x1A, 0x5C, 0x96)   # heading blue
_DARK   = RGBColor(0x2C, 0x2C, 0x2C)   # body text (near-black)
_GREY   = RGBColor(0xF0, 0xF0, 0xF0)   # note background
_ACCENT = RGBColor(0x27, 0xAE, 0x60)   # green accent for values
_WHITE  = RGBColor(0xFF, 0xFF, 0xFF)


def _shade_cell(cell, fill_hex: str) -> None:
    """Apply a solid background shade to a table cell via OOXML."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex)
    tc_pr.append(shd)


class DocxBuilder(ReportBuilder):
    """Word (.docx) implementation of the ReportBuilder interface."""

    def __init__(self, config: ReportConfig) -> None:
        self._config = config
        self._doc = Document()
        self._section_counter: int = 0
        self._figure_counter:  int = 0
        self._table_counter:   int = 0
        self._setup_document()

    # ── Document setup ────────────────────────────────────────────────────

    def _setup_document(self) -> None:
        """Configure page margins and override default paragraph styles."""
        # Page margins
        for section in self._doc.sections:
            section.top_margin    = Cm(2.5)
            section.bottom_margin = Cm(2.5)
            section.left_margin   = Cm(3.0)
            section.right_margin  = Cm(2.5)

        # Default body font
        normal = self._doc.styles["Normal"]
        normal.font.name = "Calibri"
        normal.font.size = Pt(11)
        normal.font.color.rgb = _DARK

        # Heading 1
        h1 = self._doc.styles["Heading 1"]
        h1.font.name = "Calibri"
        h1.font.size = Pt(16)
        h1.font.bold = True
        h1.font.color.rgb = _BLUE

        # Heading 2
        h2 = self._doc.styles["Heading 2"]
        h2.font.name = "Calibri"
        h2.font.size = Pt(13)
        h2.font.bold = True
        h2.font.color.rgb = _BLUE

        # Heading 3
        h3 = self._doc.styles["Heading 3"]
        h3.font.name = "Calibri"
        h3.font.size = Pt(11)
        h3.font.bold = True
        h3.font.color.rgb = _DARK

    # ── ReportBuilder implementation ──────────────────────────────────────

    def add_heading(self, text: str, level: int = 1) -> None:
        if level == 1:
            self._section_counter += 1
            numbered = f"{self._section_counter}.  {text}"
        else:
            numbered = text
        self._doc.add_heading(numbered, level=min(level, 3))

    def add_paragraph(
        self,
        text: str,
        bold: bool = False,
        italic: bool = False,
        indent: bool = False,
    ) -> None:
        p = self._doc.add_paragraph()
        if indent:
            p.paragraph_format.left_indent = Cm(1)
        run = p.add_run(text)
        run.bold   = bold
        run.italic = italic

    def add_page_break(self) -> None:
        self._doc.add_page_break()

    def add_table(
        self,
        headers: list[str],
        rows: list[list[str]],
        caption: str = "",
        style: str = "default",
    ) -> None:
        self._table_counter += 1
        col_count = len(headers)
        row_count = 1 + len(rows)

        table = self._doc.add_table(rows=row_count, cols=col_count)
        table.style = "Table Grid"
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        # Header row
        hdr_cells = table.rows[0].cells
        for i, hdr in enumerate(headers):
            hdr_cells[i].text = hdr
            _shade_cell(hdr_cells[i], "1A5C96")
            p = hdr_cells[i].paragraphs[0]
            run = p.runs[0] if p.runs else p.add_run(hdr)
            run.bold = True
            run.font.color.rgb = _WHITE
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Data rows
        for r_idx, row_data in enumerate(rows):
            cells = table.rows[r_idx + 1].cells
            fill = "F5F5F5" if r_idx % 2 == 0 else "FFFFFF"
            for c_idx, cell_text in enumerate(row_data):
                cells[c_idx].text = str(cell_text)
                _shade_cell(cells[c_idx], fill)
                cells[c_idx].paragraphs[0].alignment = (
                    WD_ALIGN_PARAGRAPH.CENTER if c_idx > 0
                    else WD_ALIGN_PARAGRAPH.LEFT
                )

        if caption:
            cap_p = self._doc.add_paragraph(
                f"Table {self._table_counter}: {caption}"
            )
            cap_p.runs[0].italic = True
            cap_p.runs[0].font.size = Pt(9)
            cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        self._doc.add_paragraph()   # spacer

    def add_figure(
        self,
        image_bytes: bytes,
        caption: str = "",
        width_cm: float = 16.0,
    ) -> None:
        self._figure_counter += 1
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        try:
            tmp.write(image_bytes)
            tmp.flush()
            tmp.close()
            p = self._doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run()
            run.add_picture(tmp.name, width=Cm(width_cm))
        finally:
            os.unlink(tmp.name)

        if caption:
            cap_p = self._doc.add_paragraph(
                f"Figure {self._figure_counter}: {caption}"
            )
            cap_p.runs[0].italic = True
            cap_p.runs[0].font.size = Pt(9)
            cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        self._doc.add_paragraph()

    def add_equation(
        self,
        equation_text: str,
        eq_number: str = "",
        reference: str = "",
    ) -> None:
        """
        Add a displayed equation block.

        Layout:  [indent] equation_text ... (Eq. X.XX)
                           Sadraey §X.X (italic sub-caption, if reference given)
        """
        p = self._doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(1.5)
        eq_run = p.add_run(equation_text)
        eq_run.font.name = "Cambria Math"
        eq_run.font.size = Pt(11)
        eq_run.italic = True

        if eq_number:
            tab_run = p.add_run(f"\t\t(Eq. {eq_number})")
            tab_run.font.size = Pt(10)
            tab_run.font.color.rgb = RGBColor(0x60, 0x60, 0x60)
            p.paragraph_format.tab_stops.add_tab_stop(
                Cm(14), WD_ALIGN_PARAGRAPH.RIGHT
            )

        if reference:
            ref_p = self._doc.add_paragraph(f"    {reference}")
            ref_p.runs[0].italic = True
            ref_p.runs[0].font.size = Pt(9)
            ref_p.runs[0].font.color.rgb = RGBColor(0x60, 0x60, 0x60)
            ref_p.paragraph_format.left_indent = Cm(1.5)

    def add_key_value_list(
        self,
        items: list[tuple[str, str]],
        columns: int = 2,
    ) -> None:
        """Render as a borderless two-column table (label | value)."""
        if not items:
            return
        # Split into two side-by-side pairs if columns=2
        half = math.ceil(len(items) / columns) if columns > 1 else len(items)
        # Always render as a single 2-column table (Label | Value)
        table = self._doc.add_table(rows=len(items), cols=2)
        table.style = "Table Grid"
        table.alignment = WD_TABLE_ALIGNMENT.LEFT
        for r, (lbl, val) in enumerate(items):
            row = table.rows[r]
            row.cells[0].text = lbl
            row.cells[1].text = val
            fill = "F5F5F5" if r % 2 == 0 else "FFFFFF"
            _shade_cell(row.cells[0], fill)
            _shade_cell(row.cells[1], fill)
            row.cells[0].paragraphs[0].runs[0].bold = True
        self._doc.add_paragraph()

    def add_bulleted_list(self, items: list[str]) -> None:
        for item in items:
            self._doc.add_paragraph(item, style="List Bullet")

    def add_note(self, text: str) -> None:
        p = self._doc.add_paragraph()
        p.paragraph_format.left_indent  = Cm(1.0)
        p.paragraph_format.right_indent = Cm(1.0)
        run = p.add_run(f"📌  {text}")
        run.italic = True
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(0x4A, 0x4A, 0x4A)

    def add_horizontal_rule(self) -> None:
        p = self._doc.add_paragraph()
        pPr = p._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), "1A5C96")
        pBdr.append(bottom)
        pPr.append(pBdr)

    def save(self, output_path: str) -> None:
        self._doc.save(output_path)
