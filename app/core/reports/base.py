"""
Report Export — Core Abstractions
===================================
Defines the pluggable report section framework:

  SectionCategory   — enum grouping sections (FRONT_MATTER, ANALYSIS, APPENDIX)
  SectionEntry      — user-facing manifest entry (id, enabled, order)
  SectionRegistry   — auto-discovery registry populated via __init_subclass__
  ReportContext     — immutable snapshot of all app data passed to every section
  ReportSection     — abstract base class for all report sections

Design decisions:
  - Sections register themselves via __init_subclass__ — no manual registration.
  - ReportContext is frozen so sections cannot mutate shared state.
  - Sections receive a ReportBuilder (format-agnostic API) and never touch
    word/PDF libraries directly — that is the renderer's responsibility.
  - This module is pure Python — NO Qt, NO app.state, NO app.ui imports.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, Generic, Optional, TypeVar

if TYPE_CHECKING:
    from app.core.entities import DesignBrief
    from app.core.reports.renderer import ReportBuilder


# ===========================================================================
# Section Category
# ===========================================================================

class SectionCategory(Enum):
    FRONT_MATTER = "Front Matter"
    ANALYSIS     = "Analysis"
    APPENDIX     = "Appendix"


# ===========================================================================
# Section Config  (abstract base for per-section export customisation)
# ===========================================================================

class SectionConfig(ABC):
    """Abstract base for per-section export customisation payloads.

    Concrete subclasses are frozen dataclasses that carry the user's
    customisation knobs for one section. The base defines the contract
    every customisable section's config must honour:

      * ``validate(brief)`` — drop choices that don't apply to the
        current configuration (e.g. propulsion-gated outputs whose
        ``is_included`` predicate returns False). Default behaviour is
        a no-op; override when the config references propulsion- or
        mission-gated entities.

      * ``summary()`` — return a one-line human-readable description for
        the export dialog's badge ("3 tornados · 2 sweeps · margins").

    Sections that are not customisable do NOT subclass SectionConfig —
    they simply leave ``ReportSection.default_config`` returning ``None``.
    """

    def validate(self, brief: "DesignBrief") -> "SectionConfig":
        """Return a copy of this config with any context-invalid choices
        removed. Default: pass through unchanged."""
        return self

    def summary(self) -> str:
        """One-line description for the customise-badge in the export dialog."""
        return "(customised)"


# ``T_Config`` parameterises ``ReportSection`` so customisable sections
# get a precisely-typed ``self._config`` instead of falling back to
# ``Optional[Any]``. PEP 696 default = ``SectionConfig`` lets the 13
# non-customisable existing sections keep their unparameterised
# ``class XSection(ReportSection):`` declarations.
T_Config = TypeVar("T_Config", bound=SectionConfig, default=SectionConfig)


# ===========================================================================
# Section Entry  (user-facing manifest item)
# ===========================================================================

@dataclass
class SectionEntry:
    """
    Represents one section in the user's export manifest.

    The user can toggle `enabled` and adjust `order` via the export dialog.
    ``section_id`` links back to a registered ReportSection subclass.
    ``config`` holds the user's customisation payload (typed via the
    ``SectionConfig`` base hierarchy) when the section is customisable;
    ``None`` means "use the section's ``default_config()``".
    """

    section_id: str
    enabled: bool = True
    order: int    = 0    # copied from ReportSection.default_order initially
    config: Optional[SectionConfig] = None


# ===========================================================================
# Section Registry
# ===========================================================================

class SectionRegistry:
    """
    Global registry of all concrete ReportSection subclasses.

    Populated automatically when a subclass is defined — the
    ReportSection.__init_subclass__ hook calls register() for every
    non-abstract concrete class.
    """

    _sections: ClassVar[dict[str, type[ReportSection]]] = {}

    @classmethod
    def register(cls, section_cls: type[ReportSection]) -> None:
        sid = section_cls.section_id
        if sid in cls._sections:
            raise ValueError(
                f"Duplicate section_id '{sid}': "
                f"{cls._sections[sid].__name__} vs {section_cls.__name__}"
            )
        cls._sections[sid] = section_cls

    @classmethod
    def all_sections(cls) -> list[type[ReportSection]]:
        """All registered sections sorted by default_order."""
        return sorted(cls._sections.values(), key=lambda s: s.default_order)

    @classmethod
    def get(cls, section_id: str) -> type[ReportSection]:
        try:
            return cls._sections[section_id]
        except KeyError:
            raise KeyError(f"No section registered with id '{section_id}'")

    @classmethod
    def by_category(cls, cat: SectionCategory) -> list[type[ReportSection]]:
        return [s for s in cls.all_sections() if s.category is cat]

    @classmethod
    def default_manifest(cls) -> list[SectionEntry]:
        """Return the default export manifest (all sections, default order)."""
        return [
            SectionEntry(section_id=s.section_id, enabled=True, order=s.default_order)
            for s in cls.all_sections()
        ]

    @classmethod
    def enabled_sections(
        cls, manifest: list[SectionEntry]
    ) -> list[type[ReportSection]]:
        """Return section classes for enabled manifest entries, in order."""
        ordered = sorted(manifest, key=lambda e: e.order)
        result: list[type[ReportSection]] = []
        for entry in ordered:
            if entry.enabled:
                try:
                    result.append(cls.get(entry.section_id))
                except KeyError:
                    pass
        return result


# ===========================================================================
# Report Context  (immutable snapshot)
# ===========================================================================

@dataclass(frozen=True)
class ReportContext:
    """
    Immutable snapshot of all application data needed by report sections.

    Built once by ExportService from AppStore before rendering starts.
    Sections NEVER access AppStore directly — they receive this object.

    Fields may be None when the analysis has not been run yet.
    Sections must handle None gracefully and emit a placeholder message.
    """

    from app.core.entities import (
        DesignBrief,
        DesignPoint,
        WeightResult,
        ConstraintResult,
        RegressionCoeffs,
    )
    from app.core.display_converter import DisplayConverter
    from app.core.i18n import Language, Translator
    from app.state.settings import UserSettings
    from typing import Any, Callable

    # ── Report metadata ───────────────────────────────────────────────────
    project_name: str
    report_title: str
    author: str
    date_str: str
    revision: str

    # ── Design inputs ─────────────────────────────────────────────────────
    brief: DesignBrief
    settings: UserSettings

    # ── Results ───────────────────────────────────────────────────────────
    weight_result:     Optional[WeightResult]
    constraint_result: Optional[ConstraintResult]
    design_point:      Optional[DesignPoint]
    regression_coeffs: Optional[RegressionCoeffs]

    # ── Pre-rendered figures (PNG bytes, captured before export) ──────────
    matching_diagram_png:  Optional[bytes]
    mission_profile_png:   Optional[bytes]
    weight_pie_chart_png:  Optional[bytes]

    # ── Display converter ─────────────────────────────────────────────────
    display_converter: DisplayConverter

    # ── i18n ──────────────────────────────────────────────────────────────
    # Sections call ``ctx.t("key", **kwargs)`` to get a translated string.
    # ``language`` and ``translator`` are also exposed for renderer-level
    # decisions (e.g. RTL paragraph properties, Arabic complex-script font).
    language:   Language
    translator: Translator

    # ── Report options ────────────────────────────────────────────────────
    include_equations:     bool = True
    include_sadraey_refs:  bool = True

    @property
    def t(self) -> "Callable[..., str]":
        """Shortcut for ``self.translator.t`` — section authors use this."""
        return self.translator.t


# ===========================================================================
# ReportSection  (abstract base)
# ===========================================================================

class ReportSection(ABC, Generic[T_Config]):
    """
    Abstract base class for all report sections.

    Class-level mandatory metadata
    ───────────────────────────────
    section_id      : str   — unique snake_case identifier
    title           : str   — human-readable heading
    default_order   : int   — position (use multiples of 10 for easy insertion)
    category        : SectionCategory
    description     : str   — one-liner shown as tooltip in the export dialog

    Class-level optional metadata
    ──────────────────────────────
    is_customizable : bool                — when True, the export dialog
                                            renders a "Customize…" button
                                            next to the section row. Default
                                            False. Override + define a
                                            concrete ``T_Config`` subclass to
                                            opt in.
    depends_on      : tuple[str, ...]     — section_ids this section requires
    min_version     : str                 — first app version supporting this

    Instance / class methods
    ────────────────────────
    __init__(config) :  Per-export construction with the user's customisation
                        payload (or ``None`` to use ``default_config(ctx)``).
                        Non-customisable sections simply ignore ``config``.

    default_config(ctx) -> Optional[T_Config] :
                        Build the default config when none is provided.
                        Override only for customisable sections.

    build(ctx, rb) -> None :
                        Populate *rb* (a ReportBuilder) with this section's
                        content. The only method subclasses MUST implement.

    Auto-registration
    ─────────────────
    Every concrete (non-abstract) subclass is automatically registered in
    SectionRegistry when the class body is executed.
    """

    # ── Mandatory class-level metadata ────────────────────────────────────
    section_id:    ClassVar[str]
    title:         ClassVar[str]
    default_order: ClassVar[int]
    category:      ClassVar[SectionCategory]
    description:   ClassVar[str]

    # ── Optional metadata ─────────────────────────────────────────────────
    is_customizable: ClassVar[bool] = False
    depends_on:      ClassVar[tuple[str, ...]] = ()
    min_version:     ClassVar[str] = "1.0"

    # ── Construction ──────────────────────────────────────────────────────
    def __init__(self, config: Optional[T_Config] = None) -> None:
        self._config: Optional[T_Config] = config

    # ── Default config hook (override in customisable subclasses) ─────────
    @classmethod
    def default_config(cls, ctx: "ReportContext") -> Optional[T_Config]:
        """Build the default config for an export. Non-customisable
        sections return ``None`` (the default)."""
        return None

    # ── Auto-registration hook ────────────────────────────────────────────
    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Skip abstract intermediaries (classes that don't define section_id)
        if not inspect.isabstract(cls) and hasattr(cls, "section_id"):
            SectionRegistry.register(cls)

    # ── Abstract build method ─────────────────────────────────────────────
    @abstractmethod
    def build(self, ctx: ReportContext, rb: ReportBuilder) -> None:
        """Populate the report builder with this section's content."""
        ...
