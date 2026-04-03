# Domain Bible — Aerospace Engineering Reference

## Primary Textbook

**Mohammad H. Sadraey (2020).** *Design of Unmanned Aerial Systems.*
Aerospace Series. John Wiley & Sons.  ISBN 978-1-119-50862-5.

> Every formula implemented in this application must be traceable to a
> specific equation number in the Sadraey textbook.  When implementing
> or modifying an equation, **cite the equation number** in both the
> code docstring and the commit message.

---

## Active Sections & Equations

### Chapter 2 — Preliminary Design

| Section | Topic | Status |
|---|---|---|
| §2.4 | CL at best L/D — `CL* = √(CD0/k)` | ✅ Implemented |
| §2.6 | Fuel-based weight estimation (Breguet segments) | ✅ Implemented |
| §2.7 | Battery-based weight estimation (energy budget) | ✅ Implemented |
| §2.9 | Wing & engine sizing (matching plot) | ✅ Implemented |

### §2.6-2.7: Weight Estimation (Segment Method)

- **Fuel Breguet range/endurance** equations per-segment:
  - Range (cruise): `Wi/Wi-1 = exp(-R·g·SFC/(η·(CL/CD)))` (Eq. 2.17)
  - Endurance (loiter): per Eq. 2.18
- **Electric energy budget** per-segment:
  - Energy = Power × Endurance, with battery energy density and efficiency
- **Hybrid UAVs**: each segment independently assigned FUEL or BATTERY energy source
- Fixed segments (takeoff, climb, descent, landing): use Table 2.4 k-factors
- Dynamic segments (cruise, loiter): Breguet or energy-budget calculation

### §2.9: Constraint Analysis (Matching Plot)

Five constraints on the W/S vs W/P (or T/W) diagram:

| Constraint | Prop (W/P) Equation | Jet (T/W) Equation | Ref |
|---|---|---|---|
| Stall | `(W/S) = ½ρ₀ Vs² CLmax` | same | Eq. 2.38 |
| Max speed | `W/P = ηp / (½ρσV³CD0/(W/S) + 2k(W/S)/(ρσV))` | `T/W = qCD0/(W/S) + k(W/S)/q` | Eq. 2.39-2.40 |
| Takeoff | Exponential formula with `χ=exp(−0.6ρg·C_DG·S_TO/(W/S))`, `C_DG=CD0−μCL_TO` | Same exponential form | Eq. 2.41-2.42 |
| Rate of climb | `W/P = 1/(ROC/η + Vmp·1.155/(LDmax·η))`, `Vmp=√(2WS/ρ√(3CD0/k))` | `T/W = ROC/Vmd + 1/LDmax` | Eq. 2.43-2.44 |
| Service ceiling | Same as ROC × σ_C (density ratio ρ_ceil/ρ_SL) | Same with 1/σ_C factors | Eq. 2.45-2.46 |

Wing/engine sizing from design point:
- **Wing area**: `S = W_TO / (W/S)_d` (Eq. 2.49)
- **Engine power** (prop): `P = W_TO / (W/P)_d` (Eq. 2.50)
- **Engine thrust** (jet): `T = (T/W)_d × W_TO` (Eq. 2.51)

---

## Key Derived Quantities

| Quantity | Formula | Where used |
|---|---|---|
| Induced drag factor `k` | `1 / (π e AR)` | Everywhere |
| CL at best L/D (`CL*`) | `√(CD0 / k)` | Weight engine, constraint analysis |
| Maximum L/D ratio `LDmax` | `CL* / (2 CD0)` = `1/(2√(CD0·k))` | Breguet range, constraint analysis |
| Speed at max power excess `Vmp` | `√(2(W/S) / (ρ√(3CD0/k)))` | ROC / ceiling constraints |
| Speed at max L/D `Vmd` | `√(2(W/S) / (ρ√(CD0/k)))` | Jet ROC / ceiling constraints |
| Density ratio `σ` | `ρ(h) / ρ_SL` | Ceiling constraint, Vmax |

---

## Propulsion Type Rules

| PropulsionType | Constraint mode | Weight engine | Energy source |
|---|---|---|---|
| `ELECTRIC` | W/P (power loading) | Electric energy-budget | Always `BATTERY` |
| `PISTON` | W/P (power loading) | Fuel Breguet | Always `FUEL` |
| `TURBOPROP` | W/P (power loading) | Fuel Breguet | Always `FUEL` |
| `JET` | T/W (thrust loading) | Fuel Breguet | Always `FUEL` |
| `HYBRID` | W/P (power loading) | Per-segment dispatch | User chooses per-segment |

---

## Mission Segment Model

- **Base class**: `MissionSegment` — `segment_type`, `enabled`, `energy_source`
- **Cruise child**: `CruiseMissionSegment` — adds `range_km`
- **Loiter child**: `LoiterMissionSegment` — adds `endurance_hr`
- Default 6-segment profile (Sadraey Fig 2.2):
  `Takeoff → Climb → Cruise → Loiter → Descent → Landing`
- Fixed segments (takeoff/climb/descent/landing): weight fractions from Table 2.4
- Dynamic segments (cruise/loiter): Breguet or energy calculation
- At least one dynamic segment must exist
- Range and endurance are aggregated from segments, not stored at top level

---

## Physical Constants

| Constant | Value | Unit |
|---|---|---|
| `g` | `9.80665` | m/s² |
| Sea-level density `ρ₀` | `1.225` | kg/m³ |
| ROC at service ceiling | `0.508` | m/s (100 ft/min) |
| Runway friction `μ` (paved) | `0.04` | — |

---

## Historical Data & Regression

- When the "Use historical regression" setting is enabled, regression coefficients
  (`we_a`, `we_b`, `b_coeff`, `b_exp`, `s_coeff`, `s_exp`) are fitted from the
  user's database.
- When disabled, **textbook default coefficients** are used.
- Scaling-law sanity checks compare computed wing geometry against power-law
  predictions from the database.
- The user is still gathering data — the dataset is small and incomplete.
  Expect regression quality to be low initially.
