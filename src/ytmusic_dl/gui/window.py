"""
Purpose: Main window for the desktop application.

- Music Download tab
- Lyrics Only tab
- Settings tab with tool detection

Responsibility: Desktop user interface
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ytmusic_dl.gui.environment import detect_tools

class DownloadTab(QWidget):
    """Music download controls."""

    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)

        heading = QLabel("Music Download")
        heading.setStyleSheet("font-size: 18px; font-weight: 600;")

        layout.addWidget(heading)
        layout.addWidget(
            QLabel(
                "Playlist and track download controls are being "
                "wired up. Until then, use `ytmusic-dl URL`."
            )
        )
        layout.addStretch(1)

class LyricsTab(QWidget):
    """Lyrics-only search and download controls."""

    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)

        heading = QLabel("Lyrics Only")
        heading.setStyleSheet("font-size: 18px; font-weight: 600;")

        layout.addWidget(heading)
        layout.addWidget(
            QLabel(
                "Lyrics search and candidate previews are being wired "
                "up. Until then, use `ytmusic-dl lyrics search`."
            )
        )
        layout.addStretch(1)

class SettingsTab(QWidget):
    """Detected tools and application settings."""

    def __init__(self) -> None:
        super().__init__()

        self._form = QFormLayout()

        layout = QVBoxLayout(self)

        heading = QLabel("Settings")
        heading.setStyleSheet("font-size: 18px; font-weight: 600;")

        layout.addWidget(heading)
        layout.addLayout(self._form)

        refresh_button = QPushButton("Refresh tool detection")
        refresh_button.clicked.connect(self.refresh)
        layout.addWidget(refresh_button)
        layout.addStretch(1)

        self.refresh()

    def refresh(self) -> None:
        """Re-run tool detection and update the labels."""

        while self._form.rowCount():
            self._form.removeRow(0)

        for name, status in detect_tools().items():
            if status.available:
                text = f"{status.path}\n{status.version or ''}".strip()
            else:
                text = "Not found"

            label = QLabel(text)
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            label.setWordWrap(True)

            self._form.addRow(f"{name}:", label)

class MainWindow(QMainWindow):
    """Application main window."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("YouTube Music Downloader")
        self.resize(900, 600)

        self.tabs = QTabWidget()
        self.tabs.addTab(DownloadTab(), "Music Download")
        self.tabs.addTab(LyricsTab(), "Lyrics Only")
        self.tabs.addTab(SettingsTab(), "Settings")

        self.setCentralWidget(self.tabs)
