"""
Export Service — UAV-CD-APP
============================
Orchestrates report export:

  1. Builds a ReportContext snapshot from AppStore
  2. Captures figure PNGs from live pyqtgraph widgets
  3. Instantiates the appropriate ReportBuilder (DocxBuilder or future PdfBuilder)
  4. Iterates enabled sections in order and calls section.build(ctx, rb)
  5. Saves the file

Layer: services/ — imports from core/ and state/, NOT from ui/ widgets directly.
Figure capture is done by passing widget grabbers as callables, keeping ui/ decoupled.
"""

from __future__ import annotations

import logging
import math
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from app.core.display_converter import DisplayConverter
from app.core.entities import (
    ConstraintResult,
    DesignPoint,
    WeightResult,
    RegressionCoeffs,
)
from app.core.reports.base import ReportContext, SectionRegistry, SectionEntry
from app.core.reports.renderer import ExportFormat, ReportConfig
from app.core.reports.renderers.docx_renderer import DocxBuilder

# Triggers auto-registration of all section classes
import app.core.reports.sections  # noqa: F401

from app.state.store import AppStore

_LOG = logging.getLogger(__name__)


class ExportService:
    """
    Report Export Service.

    Usage:
        service = ExportService(store)
        ok, msg = service.export(config, figure_grabbers)

    figure_grabbers:
        dict[str, Callable[[], bytes]] mapping figure keys to callables
        that return PNG bytes captured from live UI widgets.
        Keys: "matching_diagram", "mission_profile", "weight_pie_chart"
        Callables are provided by the ExportDialog — keeps services/
        decoupled from specific widget classes.
    """

    def __init__(self, store: AppStore) -> None:
        self._store = store

    def export(
        self,
        config: ReportConfig,
        figure_grabbers: Optional[dict[str, Callable[[], bytes]]] = None,
    ) -> tuple[bool, str]:
        """
        Run the full export pipeline.

        Returns (success, message) — message describes error on failure
        or the output path on success.
        """
        if not config.output_path:
            return False, "No output path specified."

        try:
            ctx = self._build_context(config, figure_grabbers or {})
            rb  = self._build_renderer(config)
            self._render_sections(config, ctx, rb)
            rb.save(config.output_path)
            _LOG.info("Report exported to %s", config.output_path)
            return True, config.output_path
        except Exception as exc:
            _LOG.exception("Export failed: %s", exc)
            return False, str(exc)

    # ── Context builder ───────────────────────────────────────────────────

    def _build_context(
        self,
        config: ReportConfig,
        figure_grabbers: dict[str, Callable[[], bytes]],
    ) -> ReportContext:
        state    = self._store.state
        settings = self._store.settings
        sizing   = state.sizing

        def grab(key: str) -> Optional[bytes]:
            fn = figure_grabbers.get(key)
            if fn is None:
                return None
            try:
                return fn()
            except Exception as exc:
                _LOG.warning("Figure grab '%s' failed: %s", key, exc)
                return None

        # Also generate weight pie chart as bytes in-process
        weight_pie = self._render_weight_pie(sizing.weight_result) or grab("weight_pie_chart")

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
            matching_diagram_png=grab("matching_diagram"),
            mission_profile_png=grab("mission_profile"),
            weight_pie_chart_png=weight_pie,
            display_converter=DisplayConverter(settings),
            include_equations=config.include_equations,
            include_sadraey_refs=config.include_sadraey_refs,
        )

    def _render_weight_pie(self, wr: Optional[WeightResult]) -> Optional[bytes]:
        """Generate a simple weight pie chart as PNG bytes using matplotlib."""
        if wr is None:
            return None
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            labels, sizes, colors = [], [], []
            if wr.w_payload_kg > 0:
                labels.append(f"Payload\n{wr.w_payload_kg:.2f} kg")
                sizes.append(wr.w_payload_kg)
                colors.append("#3498db")
            if wr.w_fuel_kg > 0:
                labels.append(f"Fuel\n{wr.w_fuel_kg:.2f} kg")
                sizes.append(wr.w_fuel_kg)
                colors.append("#e67e22")
            if wr.w_battery_kg > 0:
                labels.append(f"Battery\n{wr.w_battery_kg:.2f} kg")
                sizes.append(wr.w_battery_kg)
                colors.append("#9b59b6")
            if wr.w_empty_kg > 0:
                labels.append(f"Empty\n{wr.w_empty_kg:.2f} kg")
                sizes.append(wr.w_empty_kg)
                colors.append("#2ecc71")

            if not sizes:
                return None

            fig, ax = plt.subplots(figsize=(6, 4))
            ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%",
                   startangle=90, pctdistance=0.8)
            ax.set_title(f"MTOW = {wr.w_to_kg:.3f} kg", fontsize=12)
            fig.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            return buf.read()
        except ImportError:
            _LOG.warning("matplotlib not available — weight pie chart skipped")
            return None
        except Exception as exc:
            _LOG.warning("Weight pie chart render failed: %s", exc)
            return None

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
