"""
Purpose: Main window for the desktop application.

- Music Download tab
- Lyrics Only tab
- Settings tab with tool detection

Responsibility: Desktop user interface
"""

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ytmusic_dl.gui.environment import detect_tools, install_hint
from ytmusic_dl.gui.download_tab import DownloadTab
from ytmusic_dl.gui.lyrics_tab import LyricsTab

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
                hint = install_hint(name)

                text = (
                    f"Not found\nInstall with: {hint}"
                    if hint
                    else "Not found"
                )

            label = QLabel(text)
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            label.setWordWrap(True)

            self._form.addRow(f"{name}:", label)

class MainWindow(QMainWindow):
    """Application main window."""

    def __init__(
        self,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__()

        self._settings = settings or QSettings()

        self.setWindowTitle("YouTube Music Downloader")
        self.resize(900, 600)

        self.tabs = QTabWidget()
        self.tabs.addTab(
            DownloadTab(settings=self._settings),
            "Music Download",
        )
        self.tabs.addTab(
            LyricsTab(settings=self._settings),
            "Lyrics Only",
        )
        self.tabs.addTab(SettingsTab(), "Settings")

        self.setCentralWidget(self.tabs)

        geometry = self._settings.value(
            "window/geometry"
        )

        if geometry is not None:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:
        """Save state and let tabs stop background workers."""

        self._settings.setValue(
            "window/geometry",
            self.saveGeometry(),
        )

        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)

            save_state = getattr(widget, "save_state", None)

            if callable(save_state):
                save_state()

            shutdown = getattr(widget, "shutdown", None)

            if callable(shutdown):
                shutdown()

        super().closeEvent(event)
