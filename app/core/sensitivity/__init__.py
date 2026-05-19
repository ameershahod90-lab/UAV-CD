"""
Sensitivity analysis — pure-Python design-studio engines.

Implements the "Design Sensitivity Studio" methodology from classical
aircraft conceptual design (Raymer Ch. 19, Sadraey §2.10, Keane et al. Ch. 4):

  - OAT (one-at-a-time) sweeps: vary one input parameter across a range,
    observe how each design output responds.
  - Tornado: rank input parameters by influence on a chosen output.
  - Constraint margins: distance from current design point to each
    constraint boundary, expressed as percentage slack.
  - Snowball factors: partial derivatives ∂(output)/∂(input) at the
    current design point, computed by central differences. These are the
    rules-of-thumb every aircraft designer carries in their head
    ("each extra kg of payload grows MTOW by ~4 kg").

Layer: ``app/core/`` — pure Python (numpy is allowed). No Qt, no AppStore.
Sensitivity engines call the SAME ``WeightBuildupEngine`` / ``ConstraintAnalyzer``
/ ``DesignPointFinder`` used by the live UI, so results are guaranteed to
match what the user sees in the sizing tabs.
"""

from app.core.sensitivity.margins import (
    ConstraintMargin,
    MarginsReport,
    compute_constraint_margins,
)
from app.core.sensitivity.outcome import (
    OUTPUT_CATALOG,
    OutputSpec,
    SizingOutcome,
)
from app.core.sensitivity.parameter_spec import (
    SWEEPABLE_PARAMETERS,
    SweepableParameter,
    sweepable_parameters_for,
)
from app.core.sensitivity.runner import SizingRunner
from app.core.sensitivity.snowball import (
    SnowballFactor,
    SnowballReport,
    compute_snowball_factors,
)
from app.core.sensitivity.sweep import OATSweep, SweepPoint, run_oat_sweep
from app.core.sensitivity.tornado import TornadoBar, TornadoData, compute_tornado

__all__ = [
    # outcomes
    "OUTPUT_CATALOG",
    "OutputSpec",
    "SizingOutcome",
    # parameters
    "SWEEPABLE_PARAMETERS",
    "SweepableParameter",
    "sweepable_parameters_for",
    # runner
    "SizingRunner",
    # sweep + tornado
    "OATSweep",
    "SweepPoint",
    "run_oat_sweep",
    "TornadoBar",
    "TornadoData",
    "compute_tornado",
    # margins
    "ConstraintMargin",
    "MarginsReport",
    "compute_constraint_margins",
    # snowball
    "SnowballFactor",
    "SnowballReport",
    "compute_snowball_factors",
]
