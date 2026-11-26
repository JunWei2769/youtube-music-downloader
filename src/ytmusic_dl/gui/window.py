"""
Purpose: Main window for the desktop application.

- Music Download tab
- Lyrics Only tab
- Settings tab with tool detection

Responsibility: Desktop user interface
"""

from importlib.metadata import version

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
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

        self._build_menu()

        geometry = self._settings.value(
            "window/geometry"
        )

        if geometry is not None:
            self.restoreGeometry(geometry)

        tab_index = int(
            self._settings.value("window/tab", 0)
        )

        if 0 <= tab_index < self.tabs.count():
            self.tabs.setCurrentIndex(tab_index)

    def _build_menu(self) -> None:
        """Add a Help menu with an About entry."""

        about_action = QAction(
            "About YouTube Music Downloader",
            self,
        )
        about_action.setMenuRole(
            QAction.MenuRole.AboutRole
        )
        about_action.triggered.connect(self._show_about)

        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(about_action)

    def _show_about(self) -> None:
        try:
            app_version = version(
                "youtube-music-downloader"
            )
        except Exception:
            app_version = "unknown"

        QMessageBox.about(
            self,
            "About YouTube Music Downloader",
            "Version "
            f"{app_version}\n\n"
            "Download music from YouTube Music playlists and "
            "tracks, with lyrics search and a desktop interface.",
        )

    def closeEvent(self, event) -> None:
        """Save state and let tabs stop background workers."""

        self._settings.setValue(
            "window/geometry",
            self.saveGeometry(),
        )
        self._settings.setValue(
            "window/tab",
            self.tabs.currentIndex(),
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
