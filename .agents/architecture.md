# Architecture Bible

## Project Identity

- **Application:** UAV-CD-APP (UAV Conceptual Design Application)
- **Runtime:** Desktop, Python 3.14+, PyQt6, pyqtgraph
- **Purpose:** Interactive UAV conceptual design tool following academic textbook
  methodologies (primarily Sadraey 2020).

---

## Layer Structure

```
app/
├── core/          # Pure-Python domain logic — NO Qt, NO UI, NO I/O
│   ├── entities.py         # All dataclasses (Brief, Results, Segments, etc.)
│   ├── enums.py            # All enumerations (PropulsionType, SegmentType, etc.)
│   ├── constraints.py      # Constraint analysis engine (matching diagram)
│   ├── weight_buildup.py   # Weight estimation engine (Sadraey §2.6-2.7)
│   ├── design_point.py     # Design point finder & scaling-law checks
│   ├── validation.py       # Field specs & entity validators
│   ├── atmosphere.py       # ISA atmosphere model
│   ├── regression.py       # Power-law / linear regression
│   ├── units.py            # Unit conversion (SI ↔ display)
│   └── display_converter.py# High-level converter using UserSettings
│
├── state/         # Application state — AppStore (reactive), persistence
│   ├── store.py            # AppStore: single source of truth + Qt signals
│   ├── app_state.py        # AppState dataclass tree
│   ├── settings.py         # UserSettings + SettingsManager (QSettings)
│   └── project_file.py     # .uavcd file save/load (JSON)
│
├── services/      # Orchestration — calls core, updates state
│   ├── sizing_service.py   # Full sizing pipeline orchestrator
│   └── database_service.py # Historical database + regression
│
└── ui/            # PyQt6 widgets — NO domain logic
    ├── main_window.py
    ├── themes.py           # QSS_DARK, QSS_LIGHT
    ├── tabs/
    │   ├── sizing/
    │   │   ├── general_tab.py
    │   │   ├── mission_tab.py
    │   │   ├── constraints_tab.py
    │   │   ├── weight_tab.py
    │   │   └── output_tab.py
    │   ├── settings_tab.py
    │   └── historical_data/
    └── widgets/
        ├── validated_input.py
        ├── slider_input.py
        ├── result_card.py
        ├── enum_combo.py
        ├── mission_segment_widget.py
        └── mission_diagram.py
```

---

## Strict Layer Rules

1. **`core/` is a pure library** — it must NEVER import `PyQt6`, `app.state`,
   `app.services`, or `app.ui`.  All functions take plain Python arguments
   and return plain Python objects (dataclasses, tuples, floats, etc.).

2. **`state/` depends only on `core/`** — it wraps domain objects in a
   reactive Qt container (`AppStore`) but contains zero business logic.

3. **`services/` depends on `core/` and `state/`** — orchestrates
   multi-step pipelines (weight → constraints → design point).

4. **`ui/` depends on `core/`, `state/`, and `services/`** — builds widgets,
   binds to AppStore signals, and calls services. It does NOT implement
   engineering formulas.

5. **Never bypass layers.** A widget must not call `WeightBuildupEngine`
   directly; it goes through `SizingService`.

---

## Data Flow

```
User Input → UI Widget → AppStore.update_brief_field()
                              ↓
                        brief_changed signal
                              ↓
            SizingService.run_now() [when "Run" clicked]
                ├── WeightBuildupEngine.solve()     → WeightResult
                ├── ConstraintAnalyzer.analyze()    → ConstraintResult
                └── DesignPointFinder.find()         → DesignPoint
                              ↓
                   AppStore.update_*() + signals
                              ↓
            UI widgets react via signal/slot connections
```

---

## Key Design Patterns

| Pattern | Where | Why |
|---|---|---|
| **Single source of truth** | `AppStore` | All state in one place; widgets never own domain state |
| **Signal/slot reactive UI** | PyQt6 signals | Widgets subscribe to only the data they need |
| **Immutable results** | `frozen=True` dataclasses | WeightResult, DesignPoint, ConstraintResult can't be accidentally mutated |
| **Mutable inputs** | Plain dataclasses | DesignBrief, MissionSegment — mutated in-place by widgets |
| **Strategy pattern** | Engine classes | WeightBuildupEngine, ConstraintAnalyzer are stateless; called with inputs |
| **Composition over inheritance** | UI widgets | `ValidatedInput` wraps `QDoubleSpinBox` rather than subclassing it |
| **Base/child hierarchy** | `MissionSegment` | `CruiseMissionSegment`, `LoiterMissionSegment` — different params, same interface |

---

## File Dependencies (What May Import What)

```
core/entities.py  ← core/enums.py
core/validation.py ← core/entities.py, core/enums.py
core/weight_buildup.py ← core/entities.py, core/enums.py, core/atmosphere.py
core/constraints.py ← core/entities.py, core/enums.py, core/atmosphere.py
core/design_point.py ← core/entities.py, core/enums.py, core/atmosphere.py

state/store.py ← core/entities.py, state/app_state.py, state/project_file.py
state/project_file.py ← core/entities.py, core/enums.py

services/sizing_service.py ← core/*, state/store.py

ui/* ← core/entities.py, core/enums.py, core/validation.py, 
        core/display_converter.py, state/store.py, services/*
```

---

## Testing Rules

- **Test location:** `tests/test_core.py` (all core tests in one file for now)
- **Test framework:** `pytest` + `pytest-qt`
- **All tests must pass before committing.** Run: `pytest tests/ -v --tb=short`
- **Core tests are headless** — they never instantiate `QApplication` or any widget.
- **Test coverage targets:** every engine (weight, constraint, design point),
  entity roundtrip (project file), and validation rule.
