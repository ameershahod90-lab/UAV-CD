"""
Report Export Test Suite — UAV-CD-APP
========================================
End-to-end tests for the pluggable report export system.

Why this file exists:
  The original test_core.py never imports any report-section module, so
  AttributeError-class bugs inside section.build() methods slip through.
  These tests instantiate every section, run the full ExportService
  pipeline against multiple propulsion types, and re-open the resulting
  .docx with python-docx to verify the structural contracts of the doc.

Requirements: Qt headless (QT_QPA_PLATFORM=offscreen), python-docx, lxml.
"""

from __future__ import annotations

import os

# Must be set before any PyQt6 import
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
from pathlib import Path

import pytest
from docx import Document
from lxml import etree

from PyQt6.QtWidgets import QApplication

# Triggers section auto-registration before SectionRegistry is queried
import app.core.reports.sections  # noqa: F401

from app.core.display_converter import DisplayConverter
from app.core.enums import PropulsionType
from app.core.reports.base import ReportContext, SectionRegistry, SectionCategory
from app.core.reports.renderer import ExportFormat, ReportConfig
from app.core.reports.renderers.docx_renderer import DocxBuilder, _make_omath
from app.services.export_service import ExportService
from app.services.sizing_service import SizingService
from app.state.store import AppStore

_OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def store(qapp):
    return AppStore()


@pytest.fixture
def sized_store(store):
    """Store with a default sizing run completed."""
    SizingService(store).run_now()
    return store


def _build_context(store: AppStore, *, include_equations: bool = True) -> ReportContext:
    s = store.state
    return ReportContext(
        project_name="Test Project",
        report_title="Test Report",
        author="Test Author",
        date_str="2026-05-16",
        revision="1.0",
        brief=s.sizing.brief,
        settings=store.settings,
        weight_result=s.sizing.weight_result,
        constraint_result=s.sizing.constraint_result,
        design_point=s.sizing.design_point,
        regression_coeffs=None,
        matching_diagram_png=None,
        mission_profile_png=None,
        weight_pie_chart_png=None,
        display_converter=DisplayConverter(store.settings),
        include_equations=include_equations,
        include_sadraey_refs=True,
    )


def _export(store: AppStore, out_path: Path) -> tuple[bool, str]:
    cfg = ReportConfig(
        report_title="Test",
        author="Test",
        revision="1.0",
        format=ExportFormat.DOCX,
        sections=SectionRegistry.default_manifest(),
        output_path=str(out_path),
    )
    return ExportService(store).export(cfg, figure_grabbers={})


# ── Registry tests ───────────────────────────────────────────────────────────


class TestSectionRegistry:
    def test_thirteen_sections_registered(self):
        assert len(SectionRegistry.all_sections()) == 13

    def test_section_ids_unique(self):
        ids = [s.section_id for s in SectionRegistry.all_sections()]
        assert len(set(ids)) == len(ids)

    def test_sections_have_required_metadata(self):
        for cls in SectionRegistry.all_sections():
            assert cls.section_id, f"{cls.__name__} missing section_id"
            assert cls.title, f"{cls.__name__} missing title"
            assert isinstance(cls.category, SectionCategory)
            assert isinstance(cls.default_order, int)

    def test_default_manifest_in_order(self):
        manifest = SectionRegistry.default_manifest()
        orders = [
            SectionRegistry.get(e.section_id).default_order for e in manifest
        ]
        assert orders == sorted(orders)


# ── Each section can build without raising ──────────────────────────────────


class TestSectionBuilds:
    """Catches AttributeError-class bugs that the rest of the suite misses."""

    @pytest.mark.parametrize(
        "propulsion",
        [
            PropulsionType.ELECTRIC,
            PropulsionType.PISTON,
            PropulsionType.HYBRID,
            PropulsionType.TURBOJET,
        ],
    )
    def test_every_section_builds(self, store, propulsion):
        store.update_brief_field("propulsion_type", propulsion)
        SizingService(store).run_now()
        ctx = _build_context(store)

        failures: list[str] = []
        for section_cls in SectionRegistry.all_sections():
            rb = DocxBuilder(ReportConfig())
            try:
                section_cls().build(ctx, rb)
            except Exception as exc:
                failures.append(f"[{propulsion.name}] {section_cls.__name__}: {exc!r}")

        if failures:
            pytest.fail("Sections failed to build:\n" + "\n".join(failures))


# ── End-to-end export ───────────────────────────────────────────────────────


class TestEndToEndExport:
    @pytest.mark.parametrize(
        "propulsion",
        [
            PropulsionType.ELECTRIC,
            PropulsionType.PISTON,
            PropulsionType.HYBRID,
            PropulsionType.TURBOJET,
        ],
    )
    def test_export_produces_valid_docx(self, store, propulsion, tmp_path):
        store.update_brief_field("propulsion_type", propulsion)
        SizingService(store).run_now()

        out = tmp_path / f"report_{propulsion.name.lower()}.docx"
        ok, msg = _export(store, out)
        assert ok, f"Export failed for {propulsion.name}: {msg}"
        assert out.exists()
        assert out.stat().st_size > 5000

        # File must be readable by python-docx
        doc = Document(str(out))
        assert len(doc.paragraphs) > 10


# ── Structural inspection of the rendered .docx ─────────────────────────────


class TestExportedDocxStructure:
    @pytest.fixture
    def exported_doc(self, sized_store, tmp_path):
        out = tmp_path / "smoke.docx"
        ok, msg = _export(sized_store, out)
        assert ok, msg
        return Document(str(out))

    def test_no_error_notes_leaked_into_body(self, exported_doc):
        bad_phrases = ["could not be rendered", "AttributeError", "Traceback"]
        for p in exported_doc.paragraphs:
            for phrase in bad_phrases:
                assert phrase not in p.text, (
                    f"Error text leaked into doc paragraph: {p.text!r}"
                )

    def test_expected_section_headings_present(self, exported_doc):
        full_text = "\n".join(p.text for p in exported_doc.paragraphs)
        expected_substrings = [
            "Mission Requirements",
            "Mission Profile",
            "Weight Estimation",
            "Constraint Analysis",
            "Design Point",
            "Aerodynamic Parameters",
            "Sanity Checks",
            "Appendix",
        ]
        for needle in expected_substrings:
            assert needle in full_text, f"Missing heading text: {needle!r}"

    def test_omml_math_elements_present(self, exported_doc):
        """At least one m:oMath element must appear (real Word equation object)."""
        body_xml = etree.tostring(exported_doc.element).decode("utf-8")
        assert f"{{{_OMML_NS}}}oMath" in body_xml or "m:oMath" in body_xml, (
            "No <m:oMath> elements found — equations are not rendered as Word math"
        )

    def test_omml_has_real_structure_not_just_text(self, exported_doc):
        """Equations must produce structural OMML — fractions, radicals, sub/sup —
        not just <m:t> text inside <m:oMath>. Without this, Word renders the
        equation as plain italic text rather than proper math layout.

        python-docx serializes OMML with the ``m:`` prefix (e.g. ``<m:f>``);
        match the prefix form rather than the Clark-notation tag.
        """
        body_xml = etree.tostring(exported_doc.element).decode("utf-8")
        # The doc must contain at least one of each: fraction, radical,
        # subscript, and subscript+superscript (a baseline of math richness).
        assert "<m:f>" in body_xml or "<m:f " in body_xml, "No <m:f> fractions found"
        assert "<m:rad>" in body_xml or "<m:rad " in body_xml, "No <m:rad> radicals found"
        assert "<m:sSub>" in body_xml or "<m:sSub " in body_xml, "No <m:sSub> subscripts found"
        # sSup is rarer in our equations; sSubSup is the more common combined form
        assert (
            "<m:sSup>" in body_xml or "<m:sSubSup>" in body_xml
        ), "No <m:sSup> / <m:sSubSup> superscripts found"

    def test_mission_segments_energy_matches_electric_propulsion(
        self, exported_doc
    ):
        """For default (Electric) brief, every segment must show Battery, not Fuel."""
        found = False
        for tbl in exported_doc.tables:
            headers = [c.text.strip() for c in tbl.rows[0].cells]
            if "Segment Type" in headers and "Energy Source" in headers:
                idx = headers.index("Energy Source")
                for row in tbl.rows[1:]:
                    val = row.cells[idx].text.strip().lower()
                    assert val == "battery", (
                        f"Electric propulsion segment shows Energy Source = {val!r}, "
                        f"expected 'battery'"
                    )
                found = True
                break
        assert found, "Mission Segments table not found in exported doc"

    def test_weight_pie_chart_image_present(self, exported_doc):
        """Weight Estimation should embed a pie-chart figure."""
        inline_shapes = exported_doc.inline_shapes
        assert len(inline_shapes) >= 1, (
            f"Expected at least 1 embedded figure (weight pie chart), "
            f"found {len(inline_shapes)}"
        )

    def test_cover_page_uses_today_not_brief_date(self, exported_doc):
        """Date on cover should be a recent ISO date, not 2026-04-04 (frozen)."""
        full_text = "\n".join(p.text for p in exported_doc.paragraphs)
        for tbl in exported_doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    full_text += "\n" + cell.text
        assert "2026-04-04" not in full_text, (
            "Cover page date is frozen at 2026-04-04 — should use today's date"
        )


# ── OMML XML helper ─────────────────────────────────────────────────────────


class TestOMMLBuilder:
    """Verify the LaTeX→OMML transform produces real Word math structure,
    not just <m:t> text-runs wrapped in <m:oMath>."""

    def _count(self, el, *local_names):
        """Count descendants whose local-name is in ``local_names``."""
        total = 0
        for d in el.iter():
            tag = d.tag.split("}", 1)[1] if "}" in d.tag else d.tag
            if tag in local_names:
                total += 1
        return total

    def test_make_omath_returns_oMath_element(self):
        el = _make_omath(r"a + b = c")
        assert el.tag == f"{{{_OMML_NS}}}oMath"

    def test_fraction_emits_omml_frac(self):
        el = _make_omath(r"\frac{W_E}{W_{TO}} = a")
        assert self._count(el, "f") >= 1, (
            "LaTeX \\frac should produce <m:f> (real fraction structure)"
        )
        # Each <m:f> must contain <m:num> and <m:den>
        assert self._count(el, "num") >= 1
        assert self._count(el, "den") >= 1

    def test_sqrt_emits_omml_rad(self):
        el = _make_omath(r"C_L = \sqrt{C_{D_0} / k}")
        assert self._count(el, "rad") >= 1, (
            "LaTeX \\sqrt should produce <m:rad> (real radical structure)"
        )

    def test_subscript_emits_omml_sSub(self):
        el = _make_omath(r"V_s")
        assert self._count(el, "sSub") >= 1, (
            "LaTeX subscript should produce <m:sSub>"
        )

    def test_superscript_emits_omml_sSup(self):
        el = _make_omath(r"V^2")
        assert self._count(el, "sSup") >= 1, (
            "LaTeX superscript should produce <m:sSup>"
        )

    def test_sub_and_sup_combined_emits_sSubSup(self):
        el = _make_omath(r"V_s^2")
        assert self._count(el, "sSubSup") >= 1, (
            "LaTeX sub+sup on same base should produce <m:sSubSup>"
        )

    def test_greek_letters_preserved_in_text(self):
        el = _make_omath(r"\rho_0 \cdot V")
        # Find all <m:t> elements and concatenate their text
        all_text = "".join(
            (t.text or "")
            for t in el.iter(f"{{{_OMML_NS}}}t")
        )
        assert "ρ" in all_text, "Greek rho missing from OMML output"

    def test_well_formed_xml(self):
        el = _make_omath(r"\frac{1}{2}\rho_0 V_s^2 C_{L_{\max}}")
        s = etree.tostring(el)
        reparsed = etree.fromstring(s)
        assert reparsed.tag.endswith("}oMath")


# ── Auto-numbering, inline math, and citation style ────────────────────────


class TestEquationNumberingAndCitations:
    @pytest.fixture
    def exported(self, sized_store, tmp_path):
        out = tmp_path / "numbering.docx"
        ok, msg = _export(sized_store, out)
        assert ok, msg
        return Document(str(out))

    def test_no_section_sign_in_body(self, exported):
        """The § character should not appear anywhere in the document — we
        use 'Sec.' instead so the report reads as natural prose."""
        body = etree.tostring(exported.element).decode("utf-8")
        # Strip the namespace declarations so § in xml namespaces (none in
        # this doc, but defensive) doesn't trigger a false positive
        assert "§" not in body, "Section sign § found in document body"

    def test_auto_numbered_equation_labels(self, exported):
        """Displayed equations should carry labels of the form (N.M) where
        N is the level-1 section index and M is the sub-counter."""
        import re

        body = etree.tostring(exported.element).decode("utf-8")
        labels = re.findall(r"\((\d+)\.(\d+)\)", body)
        # Filter out "Sec. 2.9" / "Eq. 2.49-2.51" textual section refs:
        labels = [(n, m) for n, m in labels if int(n) <= 20 and int(m) <= 99]
        # We expect at least 5 auto-numbered equations in a default export.
        assert len(labels) >= 5, f"Too few auto-numbered eq labels: {labels}"

        # Within each section, sub-counters should be 1..K consecutive.
        from collections import defaultdict
        per_section = defaultdict(list)
        for n, m in labels:
            per_section[int(n)].append(int(m))
        for section, subs in per_section.items():
            assert subs == list(range(1, len(subs) + 1)), (
                f"Section {section} eq numbers are not 1..N consecutive: {subs}"
            )

    def test_no_legacy_eq_2_dot_prefix_labels(self, exported):
        """The old per-equation labels were '(Eq. 2.38)', '(Eq. 2.49)', etc.
        After auto-numbering, no '(Eq. <digit>.<digit>)' should remain."""
        import re

        body = etree.tostring(exported.element).decode("utf-8")
        legacy = re.findall(r"\(Eq\.\s*\d+\.\d+\)", body)
        assert not legacy, f"Legacy (Eq. N.NN) labels still present: {legacy}"


class TestInlineMathTemplate:
    def test_paragraph_inline_math_emits_omml(self, sized_store, tmp_path):
        """A paragraph containing {{{LaTeX}}} should produce inline OMML
        alongside the surrounding text."""
        from app.core.reports.renderers.docx_renderer import DocxBuilder
        from app.core.reports.renderer import ReportConfig

        out = tmp_path / "inline_math.docx"
        rb = DocxBuilder(ReportConfig())
        rb.add_heading("Test Section", level=1)
        rb.add_paragraph(
            "The propulsive efficiency {{{\\eta_p}}} appears here, and "
            "so does {{{\\rho_0 V_s^2}}}."
        )
        rb.save(str(out))

        from docx import Document
        doc = Document(str(out))
        body = etree.tostring(doc.element).decode("utf-8")
        # Two inline math sources → two <m:oMath> elements (plus none from
        # add_equation, since we never called it)
        omath_count = body.count("<m:oMath>") + body.count("<m:oMath ")
        assert omath_count == 2, (
            f"Expected 2 inline OMML elements, found {omath_count}"
        )

    def test_inline_math_in_default_export(self, sized_store, tmp_path):
        """Section files use {{{...}}} in their intros / kv-lists. Confirm
        those round-trip into the rendered .docx as inline OMML."""
        out = tmp_path / "with_inline.docx"
        ok, msg = _export(sized_store, out)
        assert ok, msg
        body = etree.tostring(Document(str(out)).element).decode("utf-8")
        # The raw {{{...}}} sigil should NOT appear in the rendered doc
        assert "{{{" not in body, (
            "Raw inline-math sigil leaked into the rendered document"
        )
        # And at least one inline OMML run should exist (section intros add them)
        omath_count = body.count("<m:oMath>") + body.count("<m:oMath ")
        assert omath_count >= 1, "No OMML elements at all — inline math not emitted"


# ── Display-rule tests: only relevant data should appear ────────────────────


def _doc_text(doc) -> str:
    """Concatenate all text content (paragraphs + table cells) into one string."""
    parts = [p.text for p in doc.paragraphs]
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


class TestDisplayRules:
    """Hide irrelevant data per propulsion type (ui_ux.md bible rule)."""

    def _exported(self, store, tmp_path, propulsion):
        store.update_brief_field("propulsion_type", propulsion)
        SizingService(store).run_now()
        out = tmp_path / f"display_{propulsion.name.lower()}.docx"
        ok, msg = _export(store, out)
        assert ok, msg
        return Document(str(out))

    def test_electric_propulsion_hides_thrust_to_weight(self, store, tmp_path):
        doc = self._exported(store, tmp_path, PropulsionType.ELECTRIC)
        text = _doc_text(doc)
        # Electric uses W/P — (T/W) should not appear as a variable definition
        # or as a sizing-results row label.
        assert "(T/W)_d" not in text, (
            "Electric propulsion design-point summary should not mention (T/W)_d"
        )
        assert "Thrust-to-Weight Ratio (T/W)" not in text, (
            "Electric propulsion sizing results should not show Thrust-to-Weight Ratio"
        )

    def test_turbojet_propulsion_hides_power_loading(self, store, tmp_path):
        doc = self._exported(store, tmp_path, PropulsionType.TURBOJET)
        text = _doc_text(doc)
        # Turbojet uses T/W — (W/P) should not appear as variable def or
        # as a results-row label.
        assert "(W/P)_d" not in text, (
            "Turbojet propulsion design-point summary should not mention (W/P)_d"
        )
        assert "Power Loading (W/P)" not in text, (
            "Turbojet propulsion sizing results should not show Power Loading"
        )

    def test_no_alternative_notes_column_in_sizing_results(
        self, sized_store, tmp_path
    ):
        out = tmp_path / "no_alt.docx"
        ok, _ = _export(sized_store, out)
        assert ok
        doc = Document(str(out))
        for tbl in doc.tables:
            headers = [c.text.strip() for c in tbl.rows[0].cells]
            assert "Alternative / Notes" not in headers, (
                f"Sizing Results table still has 'Alternative / Notes' column: {headers}"
            )

    def test_matching_diagram_wing_loading_no_duplicate_si(
        self, sized_store, tmp_path
    ):
        """Wing loading line should not show '... | <same value> N/m²' suffix."""
        out = tmp_path / "no_dup.docx"
        ok, _ = _export(sized_store, out)
        assert ok
        doc = Document(str(out))
        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    text = cell.text
                    if "Wing Loading (W/S)" in text:
                        # cell with the label only; the value cell is the next one
                        continue
                    if "N/m²" in text and "|" in text:
                        pytest.fail(
                            f"Duplicate SI value in matching-diagram cell: {text!r}"
                        )


# ── Bonus: include/exclude equations toggle ─────────────────────────────────


class TestIncludeEquationsToggle:
    """include_equations=False skips the displayed (auto-numbered) equation
    blocks but does NOT scrub inline {{{...}}} math from prose — those are
    integral to the surrounding sentences."""

    def test_displayed_equations_excluded_when_toggled_off(
        self, sized_store, tmp_path
    ):
        import re

        cfg_off = ReportConfig(
            report_title="No equations",
            author="Test",
            revision="1.0",
            format=ExportFormat.DOCX,
            sections=SectionRegistry.default_manifest(),
            output_path=str(tmp_path / "no_eq.docx"),
            include_equations=False,
        )
        ok, _ = ExportService(sized_store).export(cfg_off, figure_grabbers={})
        assert ok
        doc_off = Document(str(tmp_path / "no_eq.docx"))
        body_off = etree.tostring(doc_off.element).decode("utf-8")

        # Auto-numbered displayed equations look like "(7.1)", "(7.2)", etc.
        # Inline math has no such label. So the toggle's signature is:
        eq_labels_off = re.findall(r"\(\d+\.\d+\)", body_off)
        # The cover page shows "Sec. 2.6-2.7" / "Eq. 2.49-2.51" — those are
        # textual section references, not auto-numbered equation labels.
        # Filter them out:
        eq_labels_off = [
            lbl for lbl in eq_labels_off
            if "Sec." not in lbl and "Eq." not in lbl
        ]
        assert not eq_labels_off, (
            f"include_equations=False but auto-numbered eq labels still appear: "
            f"{eq_labels_off[:5]}"
        )

    def test_displayed_equations_present_when_toggled_on(
        self, sized_store, tmp_path
    ):
        import re

        cfg_on = ReportConfig(
            report_title="With equations",
            author="Test",
            revision="1.0",
            format=ExportFormat.DOCX,
            sections=SectionRegistry.default_manifest(),
            output_path=str(tmp_path / "with_eq.docx"),
            include_equations=True,
        )
        ok, _ = ExportService(sized_store).export(cfg_on, figure_grabbers={})
        assert ok
        doc_on = Document(str(tmp_path / "with_eq.docx"))
        body_on = etree.tostring(doc_on.element).decode("utf-8")
        eq_labels_on = re.findall(r"\(\d+\.\d+\)", body_on)
        eq_labels_on = [
            lbl for lbl in eq_labels_on
            if "Sec." not in lbl and "Eq." not in lbl
        ]
        assert len(eq_labels_on) >= 5, (
            f"Expected auto-numbered equation labels; only found {eq_labels_on}"
        )
