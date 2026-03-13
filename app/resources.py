"""
Asset & Data Path Helpers — UAV-CD-APP
=======================================
Centralised path resolution so every module uses the same root-relative
references regardless of where the process is launched from.
"""

from __future__ import annotations

import os
import sys

# ---------------------------------------------------------------------------
# Root resolution
# ---------------------------------------------------------------------------

def _project_root() -> str:
    """Return the absolute path to the project root directory."""
    # Works both when running from source and from a frozen executable.
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # __file__ → app/resources.py  →  ../  = project root
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_ROOT: str = _project_root()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def asset_path(*parts: str) -> str:
    """Return absolute path to a file located under <root>/assets/."""
    return os.path.join(_ROOT, "assets", *parts)


def data_path(*parts: str) -> str:
    """Return absolute path to a file located under <root>/data/."""
    return os.path.join(_ROOT, "data", *parts)


def root_path(*parts: str) -> str:
    """Return absolute path relative to the project root."""
    return os.path.join(_ROOT, *parts)
