# Code Style Bible

## Language & Typing

- **Python 3.14+** — use the latest features (`from __future__ import annotations`
  in every file for forward-ref type hints).
- **Strictly typed.** Every function signature must have full type annotations:
  argument types, return type, no `Any` unless unavoidable.
- **Type aliases** go at module top, not inline.
- **`Optional[X]`** preferred over `X | None` for readability.

---

## OOP Principles

### SOLID

| Principle | How we apply it |
|---|---|
| **S** — Single Responsibility | One class = one job. `WeightBuildupEngine` does weight calculation only; it does NOT draw charts or save files. |
| **O** — Open/Closed | Engine classes can be extended (new propulsion types) without modifying existing methods. |
| **L** — Liskov Substitution | `CruiseMissionSegment` and `LoiterMissionSegment` are fully substitutable for `MissionSegment` everywhere. |
| **I** — Interface Segregation | Widgets connect to only the AppStore signals they need (e.g. `weight_result_changed`, not all-state-changed). |
| **D** — Dependency Inversion | Engines depend on domain entities (abstractions), not on UI or state classes. |

### DRY

- **Never duplicate formulas.** If a calculation (like `LD_max = 1/(2√(CD0·k))`)
  is needed in multiple places, compute it once and pass it as a parameter or
  store it on a shared object.
- **Field specs** (`validation.py`) define min/max/label/unit in one place;
  the UI auto-generates inputs from these specs.
- **Unit conversion** is centralized in `DisplayConverter`; widgets never hard-code
  conversion factors.

---

## Naming Conventions

| Item | Convention | Example |
|---|---|---|
| Files | `snake_case.py` | `weight_buildup.py` |
| Classes | `PascalCase` | `WeightBuildupEngine` |
| Functions / methods | `snake_case` | `solve()`, `_stall_ws()` |
| Constants | `UPPER_SNAKE_CASE` | `_G = 9.80665`, `_N_WS = 150` |
| Private members | Leading `_` | `self._brief`, `def _build()` |
| Signals | `snake_case` (no prefix) | `brief_changed`, `weight_result_changed` |
| Enums | `PascalCase` members | `PropulsionType.ELECTRIC` |
| Dataclass fields | `snake_case` with SI unit suffix | `cruise_speed_ms`, `wing_area_m2` |

### SI Unit Suffixes for Domain Fields

Always suffix physical-quantity fields with their SI unit:

```python
payload_mass_kg: float      # mass in kilograms
cruise_speed_ms: float      # speed in metres/second
wing_area_m2: float         # area in square metres
service_ceiling_m: float    # altitude in metres
range_km: float             # distance in kilometres (exception: km is more natural)
endurance_hr: float         # time in hours (exception: hours more natural)
```

---

## Module Structure

Every Python file follows this template:

```python
"""
Module Title — UAV-CD-APP
===========================
Brief description of what this module does and why.

References (if applicable):
  - Sadraey (2020) §X.Y — specific equation numbers
"""

from __future__ import annotations

# stdlib imports
import math
from typing import Final, Optional

# third-party imports
import numpy as np

# internal imports (core → state → services, never backwards)
from app.core.entities import DesignBrief
from app.core.enums import PropulsionType

# Module-level constants
_G: Final[float] = 9.806_65


class MyEngine:
    """Docstring with full description."""

    def public_method(self, arg: float) -> float:
        """One-line docstring."""
        ...

    def _private_method(self) -> None:
        ...
```

---

## Dataclass Rules

1. **Mutable input types** (user-editable): `@dataclass` (not frozen).
   Example: `DesignBrief`, `MissionSegment`.

2. **Immutable result types** (computed output): `@dataclass(frozen=True)`.
   Example: `WeightResult`, `DesignPoint`, `ConstraintResult`.

3. **All fields have default values** for serialization safety.

4. **Field metadata** uses `field(metadata={...})` for label, unit, tooltip.
   The `FieldSpec` in `validation.py` auto-registers these.

5. **Don't use `dict` when a dataclass will do.** Structured data = dataclass.

---

## Error Handling

- **Validation errors** are collected (not raised one-at-a-time). The
  `EntityValidator.validate()` method returns a list of all errors.
- **Calculation errors** should never crash the app. Engines return a
  fallback result (e.g. `converged=False`) and the UI shows a warning toast.
- **Never use bare `except:`.** Always catch specific exceptions.

---

## Git Commit Rules

- **All tests pass before committing.** Run `pytest tests/ -v --tb=short`.
- **Commit messages** use conventional commits:
  - `feat:` for new features
  - `fix:` for bug fixes
  - `refactor:` for refactors with no behavior change
  - `test:` for test additions/changes only
  - `docs:` for documentation only
- **Message body** should explain *what changed and why*, listing affected
  files/components and equation references where applicable.
- **One logical change per commit.** Don't mix unrelated feature + bugfix.
