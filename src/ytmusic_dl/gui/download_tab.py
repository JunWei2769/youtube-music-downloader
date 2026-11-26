"""Music download tab for the desktop application."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ytmusic_dl.downloader import AUDIO_FORMATS
from ytmusic_dl.gui.download_worker import DownloadWorker
from ytmusic_dl.models import DownloadProgress, Track

DEFAULT_OUTPUT = Path("downloads")

FORMAT_LABELS = {
    "mp3": "MP3",
    "opus": "Opus",
    "flac": "FLAC",
    "wav": "WAV",
    "m4a": "M4A (AAC)",
    "source": "Source (no re-encode)",
}

BROWSERS = (
    "vivaldi",
    "chrome",
    "chromium",
    "brave",
    "firefox",
    "edge",
    "opera",
    "whale",
)

class DownloadTab(QWidget):
    """Download a playlist or track with live progress."""

    def __init__(self) -> None:
        super().__init__()

        self._worker: DownloadWorker | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        heading = QLabel("Music Download")
        heading.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(heading)

        form = QFormLayout()

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "https://music.youtube.com/playlist?list=… "
            "or https://music.youtube.com/watch?v=…"
        )
        form.addRow("Playlist or track URL:", self.url_input)

        output_row = QHBoxLayout()

        self.output_input = QLineEdit(str(DEFAULT_OUTPUT))

        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._browse)

        output_row.addWidget(self.output_input, 1)
        output_row.addWidget(browse_button)

        form.addRow("Output directory:", output_row)

        self.format_combo = QComboBox()

        for audio_format in AUDIO_FORMATS:
            self.format_combo.addItem(
                FORMAT_LABELS.get(audio_format, audio_format),
                audio_format,
            )

        form.addRow("Audio format:", self.format_combo)

        self.browser_combo = QComboBox()
        self.browser_combo.addItem("Auto-detect", None)

        for name in BROWSERS:
            self.browser_combo.addItem(name, name)

        form.addRow("Browser cookies:", self.browser_combo)

        options_row = QHBoxLayout()

        self.lyrics_check = QCheckBox("Download lyrics")
        self.lyrics_check.setChecked(True)

        self.confidence_combo = QComboBox()
        self.confidence_combo.addItem("High", "high")
        self.confidence_combo.addItem("Medium", "medium")

        self.thumbnail_check = QCheckBox("Embed thumbnails")
        self.thumbnail_check.setChecked(True)

        options_row.addWidget(self.lyrics_check)
        options_row.addWidget(QLabel("Minimum confidence:"))
        options_row.addWidget(self.confidence_combo)
        options_row.addWidget(self.thumbnail_check)
        options_row.addStretch(1)

        form.addRow("Options:", options_row)

        layout.addLayout(form)

        controls = QHBoxLayout()

        self.start_button = QPushButton("Start download")
        self.start_button.clicked.connect(self._start)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)

        controls.addWidget(self.start_button)
        controls.addWidget(self.cancel_button)
        controls.addStretch(1)

        layout.addLayout(controls)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("Idle.")
        layout.addWidget(self.progress_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText(
            "Download log will appear here."
        )
        self.log_view.setMaximumBlockCount(5000)
        layout.addWidget(self.log_view, 1)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.summary_label)

        self.lyrics_check.toggled.connect(
            self.confidence_combo.setEnabled
        )

    # ---------------------------------------------------------
    # Controls
    # ---------------------------------------------------------

    def _browse(self) -> None:
        start = Path(
            self.output_input.text().strip()
            or str(DEFAULT_OUTPUT)
        ).expanduser()

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select output directory",
            str(start),
        )

        if directory:
            self.output_input.setText(directory)

    def _start(self) -> None:
        if self._worker is not None:
            return

        url = self.url_input.text().strip()

        if not url:
            QMessageBox.warning(
                self,
                "Missing URL",
                "Enter a playlist or track URL.",
            )
            return

        output_directory = Path(
            self.output_input.text().strip()
            or str(DEFAULT_OUTPUT)
        ).expanduser()

        worker = DownloadWorker(
            url=url,
            output_directory=output_directory,
            audio_format=self.format_combo.currentData(),
            browser_name=self.browser_combo.currentData(),
            download_lyrics=self.lyrics_check.isChecked(),
            download_thumbnails=(
                self.thumbnail_check.isChecked()
            ),
            lyrics_min_confidence=(
                self.confidence_combo.currentData()
            ),
            parent=self,
        )

        worker.log.connect(self._on_log)
        worker.progress.connect(self._on_progress)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_finished)

        self._worker = worker

        self._set_running(True)
        self.log_view.clear()
        self.summary_label.clear()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting…")

        worker.start()

    def _set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)

    def _cancel(self) -> None:
        if self._worker is None:
            return

        self._worker.cancel()
        self.cancel_button.setEnabled(False)
        self.progress_label.setText("Cancelling…")
        self.log_view.appendPlainText("Cancelling…")

    # ---------------------------------------------------------
    # Worker signals
    # ---------------------------------------------------------

    def _on_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def _on_progress(
        self,
        track: Track,
        update: DownloadProgress,
        index: int,
        total: int,
    ) -> None:
        stage = (
            "Converting"
            if update.stage == "postprocess"
            else "Downloading"
        )

        if update.percent is None:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(
                int(update.percent)
            )

        self.progress_label.setText(
            f"{stage} — track {index} of {total}: "
            f"{track.title}"
        )

    def _on_completed(self, result) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)

        status = "Cancelled" if result.cancelled else "Complete"

        self.summary_label.setText(
            f"{status}: {result.successful} successful, "
            f"{result.failed} failed, {result.skipped} skipped, "
            f"{result.lyrics} lyrics, "
            f"{result.thumbnails} thumbnails.\n"
            f"Output: {result.output_directory}"
        )

        self.progress_label.setText(status + ".")

        if result.failed_tracks:
            self.log_view.appendPlainText("")
            self.log_view.appendPlainText("Failed tracks:")

            for failure in result.failed_tracks:
                self.log_view.appendPlainText(
                    f"  - {failure}"
                )

    def _on_failed(self, message: str) -> None:
        self.summary_label.setText("Download failed.")
        self.progress_label.setText("Failed.")
        self.log_view.appendPlainText(message)

        QMessageBox.critical(
            self,
            "Download failed",
            message,
        )

    def _on_finished(self) -> None:
        self._set_running(False)

        if self._worker is not None:
            self._worker.deleteLater()

        self._worker = None

    # ---------------------------------------------------------
    # Window
    # ---------------------------------------------------------

    def shutdown(self) -> None:
        """Cancel and wait for a running download."""

        if self._worker is None:
            return

        self._worker.cancel()

        if self._worker.isRunning():
            self._worker.wait(15000)

    def closeEvent(self, event) -> None:
        self.shutdown()
        super().closeEvent(event)
