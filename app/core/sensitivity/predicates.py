"""
Inclusion predicates for sensitivity-engine specs.

A predicate is ``Callable[[DesignBrief], bool]`` that returns ``True``
when a SweepableParameter / OutputSpec / snowball pair is relevant to
the current configuration. The fetching pipeline filters specs with
``spec.is_included(brief)`` so the UI and the snowball compute only ever
see entries that actually contribute to the design.

This replaces the previous ad-hoc two-flag scheme
(``requires_uses_fuel`` + ``requires_is_electric``), which:

  * could not express ``is_power_mode`` (needed for ``prop_efficiency``
    which is meaningless for jets — see ``constraints.py`` Eq. 2.40–2.46
    where η_p only appears inside ``if self._is_power_mode:`` branches);
  * did not scale to future gating dimensions (mission segments,
    regulation class, payload class, etc.).

Authors of new specs should reuse one of the named predicates below
rather than inlining a lambda, so the call site reads as documentation.
"""

from __future__ import annotations

from typing import Callable

from app.core.entities import DesignBrief


# Public alias — callers and dataclass field types reference this.
InclusionPredicate = Callable[[DesignBrief], bool]


def always(brief: DesignBrief) -> bool:
    """Spec is always relevant (default for universal inputs/outputs)."""
    return True


def requires_uses_fuel(brief: DesignBrief) -> bool:
    """True for PISTON, TURBOPROP, TURBOJET, HYBRID — any fuel-burning."""
    return brief.propulsion_type.uses_fuel


def requires_is_electric(brief: DesignBrief) -> bool:
    """True for ELECTRIC, HYBRID — anything with a battery."""
    return brief.propulsion_type.is_electric


def requires_is_power_mode(brief: DesignBrief) -> bool:
    """True for power-mode propulsion (everything except TURBOJET).

    Used by ``prop_efficiency``: the propeller-shaft conversion η_p has
    no role in jet thrust calculations — every line in
    ``constraints.py`` that reads ``b.prop_efficiency`` sits inside an
    ``if self._is_power_mode:`` branch, and the weight engine's Breguet
    propeller form (Eq. 2.20 / 2.25) is only invoked for power-mode
    fuel aircraft.
    """
    return brief.propulsion_type.is_power_mode
