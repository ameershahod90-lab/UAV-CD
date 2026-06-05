"""
Test-wide fixtures and isolation.

Most importantly: redirects ``SettingsManager`` to a per-test-session
temporary directory so test runs **never touch the user's real
%APPDATA%/UAV-CD/settings.json**. Without this, tests that call
``store.update_settings(...)`` would silently overwrite the developer's
own preferences (theme, units, tornado output picks, …).
"""

from __future__ import annotations

import os

# Headless Qt for CI / smoke runs. Must be set before any PyQt6 import
# pulls a real platform plugin.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolated_settings_path(tmp_path_factory) -> None:
    """Point ``app.state.settings._settings_path`` at a throwaway dir.

    Applies for the entire test session via ``autouse=True``. The fixture
    monkeypatches the module-level path resolver before the first
    ``AppStore()`` instantiates a ``SettingsManager``; subsequent
    ``SettingsManager.load()`` / ``save()`` calls land in
    ``<tmpdir>/UAV-CD-Test/settings.json`` instead of ``%APPDATA%``.
    """
    import app.state.settings as settings_mod

    tmp_dir = tmp_path_factory.mktemp("uavcd-test-settings")
    fake_path = str(tmp_dir / "settings.json")

    original = settings_mod._settings_path
    settings_mod._settings_path = lambda: fake_path     # type: ignore[assignment]
    try:
        yield
    finally:
        settings_mod._settings_path = original          # type: ignore[assignment]
