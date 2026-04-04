"""
sections/__init__.py — triggers auto-registration of all section classes.

Import all section modules here so their class bodies execute and
__init_subclass__ registers each class in SectionRegistry.

To add a new section:
  1. Create a new file in this directory
  2. Add the import below — that's all.
"""

from app.core.reports.sections.cover_page           import CoverPageSection           # noqa: F401
from app.core.reports.sections.mission_requirements import MissionRequirementsSection  # noqa: F401
from app.core.reports.sections.mission_profile      import MissionProfileSection       # noqa: F401
from app.core.reports.sections.weight_breakdown     import WeightBreakdownSection      # noqa: F401
from app.core.reports.sections.weight_equations     import WeightEquationsSection      # noqa: F401
from app.core.reports.sections.matching_diagram     import MatchingDiagramSection      # noqa: F401
from app.core.reports.sections.constraint_equations import ConstraintEquationsSection  # noqa: F401
from app.core.reports.sections.constraint_status    import ConstraintStatusSection     # noqa: F401
from app.core.reports.sections.design_point_summary import DesignPointSummarySection   # noqa: F401
from app.core.reports.sections.aerodynamic_parameters import AerodynamicParametersSection  # noqa: F401
from app.core.reports.sections.sanity_checks        import SanityChecksSection         # noqa: F401
from app.core.reports.sections.appendix_inputs      import AppendixInputsSection       # noqa: F401
from app.core.reports.sections.appendix_references  import AppendixReferencesSection   # noqa: F401
