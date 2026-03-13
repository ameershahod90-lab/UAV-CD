"""
UAV-CD-APP — Application Entry Point
========================================
Bootstraps QApplication, creates AppStore, launches MainWindow.
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
_LOG = logging.getLogger("uav-cd")


def main() -> int:
    # Must import Qt before any other Qt-dependent module
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("UAV-CD-APP")
    app.setOrganizationName("UAV-CD")
    app.setApplicationVersion("1.0.0")

    # Initialise store
    from app.state.store import create_store
    store = create_store()

    # Launch main window
    from app.ui.main_window import MainWindow
    window = MainWindow(store)
    window.show()

    _LOG.info("UAV-CD-APP Phase 1 started.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
