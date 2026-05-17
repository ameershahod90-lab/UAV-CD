"""
Export Service — UAV-CD-APP
============================
Orchestrates report export:

  1. Builds a ReportContext snapshot from AppStore
  2. Renders figures server-side via matplotlib (no Qt grab needed)
  3. Instantiates the appropriate ReportBuilder (DocxBuilder, future PdfBuilder)
  4. Iterates enabled sections in order and calls section.build(ctx, rb)
  5. Saves the file

Layer: services/ — imports from core/ and state/, NOT from ui/ widgets directly.

Figures are rendered server-side using ``app/services/figure_renderers.py``,
which consumes the same plot-data builders in ``app/core/plots/`` that the
live Qt UI uses. This decouples the export pipeline from Qt rendering state
(visibility, layout, theme) entirely — previous widget-grab approaches kept
producing empty / mis-scaled figures depending on which tab was active.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from app.core.display_converter import DisplayConverter
from app.core.entities import RegressionCoeffs  # noqa: F401 (kept for legacy callers)
from app.core.reports.base import ReportContext, SectionRegistry, SectionEntry
from app.core.reports.renderer import ExportFormat, ReportConfig
from app.core.reports.renderers.docx_renderer import DocxBuilder
from app.services.figure_renderers import (
    render_matching_diagram_png,
    render_mission_profile_png,
    render_weight_pie_png,
)

# Triggers auto-registration of all section classes
import app.core.reports.sections  # noqa: F401

from app.state.store import AppStore

_LOG = logging.getLogger(__name__)


class ExportService:
    """Report Export Service.

    All figures (matching diagram, mission profile, weight pie chart) are
    rendered server-side via matplotlib (see ``figure_renderers``). The
    optional ``figure_grabbers`` parameter on ``export()`` is kept for
    backward compatibility but is no longer used by the default pipeline.

    Usage::

        service = ExportService(store)
        ok, msg = service.export(config)
    """

    def __init__(self, store: AppStore) -> None:
        self._store = store

    def export(
        self,
        config: ReportConfig,
        figure_grabbers: Optional[dict[str, Callable[[], bytes]]] = None,
    ) -> tuple[bool, str]:
        """Run the full export pipeline.

        ``figure_grabbers`` is accepted but ignored — figures are now
        rendered server-side. Returns ``(success, message)`` where the
        message describes the error on failure or the output path on
        success.
        """
        if not config.output_path:
            return False, "No output path specified."

        try:
            ctx = self._build_context(config)
            rb  = self._build_renderer(config)
            self._render_sections(config, ctx, rb)
            rb.save(config.output_path)
            _LOG.info("Report exported to %s", config.output_path)
            return True, config.output_path
        except Exception as exc:
            _LOG.exception("Export failed: %s", exc)
            return False, str(exc)

    # ── Context builder ───────────────────────────────────────────────────

    def _build_context(self, config: ReportConfig) -> ReportContext:
        state    = self._store.state
        settings = self._store.settings
        sizing   = state.sizing
        dc       = DisplayConverter(settings)

        # All three figures are rendered server-side via matplotlib using
        # the shared plot-data builders in app/core/plots/.
        matching_png = render_matching_diagram_png(
            sizing.constraint_result, sizing.design_point, dc,
        )
        mission_png = render_mission_profile_png(sizing.brief)
        weight_pie  = render_weight_pie_png(
            sizing.weight_result, sizing.brief.propulsion_type,
        )

        return ReportContext(
            project_name=state.meta.name or "Unnamed Project",
            report_title=config.report_title,
            author=config.author,
            date_str=datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            revision=config.revision,
            brief=sizing.brief,
            settings=settings,
            weight_result=sizing.weight_result,
            constraint_result=sizing.constraint_result,
            design_point=sizing.design_point,
            regression_coeffs=state.historical_data.regression_coefficients.get(
                sizing.brief.propulsion_type.name.lower()
            ) if state.historical_data.regression_coefficients else None,
            matching_diagram_png=matching_png,
            mission_profile_png=mission_png,
            weight_pie_chart_png=weight_pie,
            display_converter=dc,
            include_equations=config.include_equations,
            include_sadraey_refs=config.include_sadraey_refs,
        )

    # ── Renderer factory ──────────────────────────────────────────────────

    def _build_renderer(self, config: ReportConfig):
        if config.format is ExportFormat.DOCX:
            return DocxBuilder(config)
        raise NotImplementedError(
            f"Export format {config.format} is not yet implemented."
        )

    # ── Section rendering ─────────────────────────────────────────────────

    def _render_sections(
        self,
        config: ReportConfig,
        ctx: ReportContext,
        rb,
    ) -> None:
        sections = SectionRegistry.enabled_sections(config.sections)
        for section_cls in sections:
            section_cls().build(ctx, rb)
            rb.add_horizontal_rule()
