"""
Purpose: Desktop application entry point.

Responsibility: Qt application bootstrap
"""

import sys

from PySide6.QtWidgets import QApplication

from ytmusic_dl.gui.environment import extend_path_with_tools
from ytmusic_dl.gui.window import MainWindow

def main() -> None:
    """Start the desktop application."""

    extend_path_with_tools()

    app = QApplication(sys.argv)
    app.setApplicationName("YouTube Music Downloader")
    app.setOrganizationName("ytmusic-dl")

    window = MainWindow()
    window.show()

    raise SystemExit(app.exec())
