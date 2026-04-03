# UI / UX Bible

## Core Principle: Show Only What's Relevant

**Only relevant data should be shown to the user at any step.**

- Input fields that don't apply to the current propulsion type must be **hidden**
  (not disabled, not greyed out — hidden via `setVisible(False)`).
- Labels containing T or P (thrust/power) must **dynamically change** based on
  the selected propulsion type. Never show both simultaneously.
- If a segment (e.g. takeoff) is disabled, its related input field (e.g. takeoff
  run distance) should be hidden.

---

## Reactive Unit System

### Rule: Internal = SI, Display = User Preference

1. **All domain values are stored and computed in SI** (m, s, kg, N, W, m²).
2. **`DisplayConverter`** is the single entry point for converting SI → display.
3. When the user changes a unit in settings, **every UI element** must update:
   - Input field suffix labels
   - Input field numerical values (convert from old unit to new unit)
   - Result cards (label + value + unit)
   - Plot axis labels
   - Plot data values (replot with new units)
   - Toast / status messages
4. **Never hard-code unit strings** in UI code. Always get from `DisplayConverter`.

### How It Works

```
User sets speed_unit = "km/h" in Settings
  → settings_changed signal fires
  → All widgets with speed values:
      1. Read current SI value from store
      2. Call DisplayConverter.speed(si_val) → (display_val, "km/h")
      3. Update their labels and values
```

---

## Widget Rules

### Input Fields

- Use `ValidatedInput` for numeric inputs — it auto-configures label, min/max,
  tooltip, and validation from `FieldSpec`.
- Use `EnumCombo` for enum-based dropdowns — auto-populates from enum values.
- Use `SliderInput` for coefficients with well-known ranges (CD0, CL, etc.)
  — shows live numeric value alongside the slider.

### Cards / Results

- Use `ResultCard` for all result readouts (MTOW, wing area, power, etc.).
- Card backgrounds: use the `QFrame#ResultCard` QSS style.
- **Label, value, and unit labels must have `background: transparent`** so the
  card background shows through cleanly.

### Icons

- **Never use emoji** for icons in PyQt6 widgets. They render inconsistently
  across platforms and font configurations.
- Use **reliable Unicode characters** (e.g. `✕` for close, `⠿` for drag grip)
  with explicit `font-size` QSS.
- For indicator icons (checkbox checkmark, radio dot, combo arrow) use **inline
  SVG data URIs** in QSS `image: url("data:image/svg+xml,...")`.

---

## Theming (QSS)

- Two themes: `QSS_DARK` and `QSS_LIGHT` in `themes.py`.
- When adding any new widget style, **add it to both themes**.
- **QSS gotcha:** when you apply a global stylesheet, Qt stops drawing native
  widget chrome. You must explicitly declare every sub-control (`::indicator`,
  `::drop-down`, `::up-button`, etc.) — otherwise they render as blank.
- Always test new QSS changes visually on Windows before committing.

---

## Constraint Violation Alerts

- When a user clicks a design point on the matching diagram:
  - If the point is **feasible** → show a green confirmation banner.
  - If the point **violates** one or more constraints → show a red banner with
    a bullet-point list naming each violated constraint and the percentage
    deviation from the boundary.
- The banner lives in `ConstraintsTab` and is driven by the
  `AppStore.constraint_violation` signal.

---

## Loading / Feedback States

- All long-running operations (Run Sizing, file save/load) must:
  1. **Disable** the trigger button immediately.
  2. **Show a loading indicator** (change button text to "⏳ Running…").
  3. On completion: re-enable button, show a **toast/status** with result
     (success with key values, or error message).
- Never leave the user without feedback — every button click must produce a
  visible response.

---

## Plot Interactions

- The matching diagram is interactive: clicking places a design point.
- **The star marker must move** to the clicked position.
- **All derived values (MTOW, S, b, P/T)** must update immediately.
- **Constraint violations** must be re-evaluated at the new point.
- Plots must re-render with updated units when settings change.

---

## Tab & Layout Standards

- Use `QScrollArea` for any tab whose content may exceed viewport height.
- Group related inputs in `QGroupBox` with descriptive titles.
- Use `QFormLayout` for label-value pairs.
- Use `QHBoxLayout` rows of `ResultCard` for output readouts.
- Sections separated by `QLabel#SectionTitle`.
