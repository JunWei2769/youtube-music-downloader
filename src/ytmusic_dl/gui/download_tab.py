"""Music download tab for the desktop application."""

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ytmusic_dl.downloader import AUDIO_FORMATS
from ytmusic_dl.gui.download_worker import DownloadWorker
from ytmusic_dl.gui.extract_worker import ExtractWorker
from ytmusic_dl.models import DownloadProgress, Track
from ytmusic_dl.utils import format_duration

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

TRACK_COLUMNS = (
    "Download",
    "#",
    "Title",
    "Artist",
    "Album",
    "Duration",
    "Lyrics",
)

LYRICS_COLORS = {
    "saved": QColor("#2e7d32"),
    "below_threshold": QColor("#b26a00"),
    "not_found": QColor("#b00020"),
    "error": QColor("#b00020"),
    "off": QColor("#8a8a8a"),
}

class DownloadTab(QWidget):
    """Load a playlist, review its tracks, then download them."""

    def __init__(
        self,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__()

        self._settings = settings or QSettings()
        self._worker: DownloadWorker | None = None
        self._load_worker: ExtractWorker | None = None
        self._tracks: list[Track] = []
        self._track_rows: dict[int, int] = {}
        self._populating = False

        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        heading = QLabel("Music Download")
        heading.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(heading)

        form = QFormLayout()

        url_row = QHBoxLayout()

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "https://music.youtube.com/playlist?list=… "
            "or https://music.youtube.com/watch?v=…"
        )
        self.url_input.textChanged.connect(
            self._on_url_changed
        )

        self.load_button = QPushButton("Load tracks")
        self.load_button.clicked.connect(self._load_tracks)

        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(self.load_button)

        form.addRow("Playlist or track URL:", url_row)

        output_row = QHBoxLayout()

        self.output_input = QLineEdit(str(DEFAULT_OUTPUT))

        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._browse)

        open_button = QPushButton("Open")
        open_button.clicked.connect(self._open_output)

        output_row.addWidget(self.output_input, 1)
        output_row.addWidget(browse_button)
        output_row.addWidget(open_button)

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

        selection_row = QHBoxLayout()

        self.selection_label = QLabel(
            "Load a URL to review its tracks."
        )

        self.select_all_button = QPushButton("Select all")
        self.select_all_button.setEnabled(False)
        self.select_all_button.clicked.connect(
            lambda: self._set_all_checked(True)
        )

        self.select_none_button = QPushButton("Select none")
        self.select_none_button.setEnabled(False)
        self.select_none_button.clicked.connect(
            lambda: self._set_all_checked(False)
        )

        selection_row.addWidget(self.selection_label, 1)
        selection_row.addWidget(self.select_all_button)
        selection_row.addWidget(self.select_none_button)

        layout.addLayout(selection_row)

        metadata_hint = QLabel(
            "Double-click Title, Artist, or Album to correct "
            "metadata before downloading. This also improves "
            "lyrics matching; the Lyrics column suggests provider "
            "metadata when a match is rejected."
        )
        metadata_hint.setWordWrap(True)
        metadata_hint.setStyleSheet(
            "color: palette(mid); font-size: 12px;"
        )
        layout.addWidget(metadata_hint)

        self.track_table = QTableWidget(
            0,
            len(TRACK_COLUMNS),
        )
        self.track_table.setHorizontalHeaderLabels(
            TRACK_COLUMNS
        )
        self.track_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.track_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.track_table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed
        )
        self.track_table.setAlternatingRowColors(True)
        self.track_table.setWordWrap(False)
        self.track_table.verticalHeader().setVisible(False)

        header = self.track_table.horizontalHeader()
        header.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )

        duration_header = self.track_table.horizontalHeaderItem(
            5
        )

        if duration_header is not None:
            duration_header.setToolTip(
                "Video duration from YouTube. Official videos can be "
                "longer than the track; lyrics matching allows a "
                "small difference."
            )

        self.track_table.itemChanged.connect(
            self._on_track_item_changed
        )

        layout.addWidget(self.track_table, 1)

        controls = QHBoxLayout()

        self.start_button = QPushButton("Start download")
        self.start_button.setEnabled(False)
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
    # Settings
    # ---------------------------------------------------------

    @staticmethod
    def _select_combo_data(combo, value) -> None:
        index = combo.findData(value)

        if index >= 0:
            combo.setCurrentIndex(index)

    def _load_settings(self) -> None:
        self.output_input.setText(
            str(
                self._settings.value(
                    "download/output",
                    str(DEFAULT_OUTPUT),
                )
            )
        )

        self._select_combo_data(
            self.format_combo,
            self._settings.value("download/format", "mp3"),
        )

        browser = self._settings.value(
            "download/browser",
            "",
        )

        if browser:
            self._select_combo_data(
                self.browser_combo,
                browser,
            )
        else:
            self.browser_combo.setCurrentIndex(0)

        self.lyrics_check.setChecked(
            self._settings.value(
                "download/lyrics",
                True,
                type=bool,
            )
        )

        self.thumbnail_check.setChecked(
            self._settings.value(
                "download/thumbnails",
                True,
                type=bool,
            )
        )

        self._select_combo_data(
            self.confidence_combo,
            self._settings.value(
                "download/confidence",
                "high",
            ),
        )

    def save_state(self) -> None:
        """Persist download defaults."""

        self._settings.setValue(
            "download/output",
            self.output_input.text().strip(),
        )
        self._settings.setValue(
            "download/format",
            self.format_combo.currentData(),
        )
        self._settings.setValue(
            "download/browser",
            self.browser_combo.currentData() or "",
        )
        self._settings.setValue(
            "download/lyrics",
            self.lyrics_check.isChecked(),
        )
        self._settings.setValue(
            "download/thumbnails",
            self.thumbnail_check.isChecked(),
        )
        self._settings.setValue(
            "download/confidence",
            self.confidence_combo.currentData(),
        )

    # ---------------------------------------------------------
    # Loading tracks
    # ---------------------------------------------------------

    def _on_url_changed(self, _text: str) -> None:
        self._invalidate_tracks()

    def _invalidate_tracks(self) -> None:
        if self._load_worker is not None or self._worker is not None:
            return

        if not self._tracks:
            return

        self._tracks = []
        self._track_rows = {}
        self._populating = True
        self.track_table.setRowCount(0)
        self._populating = False
        self._update_selection_label()

    def _load_tracks(self) -> None:
        if self._load_worker is not None or self._worker is not None:
            return

        url = self.url_input.text().strip()

        if not url:
            QMessageBox.warning(
                self,
                "Missing URL",
                "Enter a playlist or track URL.",
            )
            return

        self._invalidate_tracks()
        self.summary_label.clear()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Loading tracks…")
        self.log_view.clear()
        self.log_view.appendPlainText(
            "Loading track information…"
        )

        worker = ExtractWorker(url, parent=self)

        worker.completed.connect(self._on_tracks_loaded)
        worker.failed.connect(self._on_load_failed)
        worker.finished.connect(self._on_load_finished)

        self._load_worker = worker
        self._set_busy(True)

        worker.start()

    def _on_tracks_loaded(
        self,
        tracks: list[Track],
    ) -> None:
        self._populate_tracks(tracks)
        self.log_view.appendPlainText(
            f"Found {len(tracks)} track(s)."
        )
        self.progress_label.setText("Tracks loaded.")

    def _on_load_failed(self, message: str) -> None:
        self.progress_label.setText("Loading failed.")
        self.log_view.appendPlainText(message)

        QMessageBox.critical(
            self,
            "Could not load tracks",
            message,
        )

    def _on_load_finished(self) -> None:
        worker = self._load_worker
        self._load_worker = None

        if worker is not None:
            worker.deleteLater()

        self._set_busy(False)
        self._update_selection_label()

    def _populate_tracks(
        self,
        tracks: list[Track],
    ) -> None:
        self._tracks = list(tracks)
        self._track_rows = {}
        self._populating = True

        self.track_table.setRowCount(0)
        self.track_table.setRowCount(len(self._tracks))

        for row, track in enumerate(self._tracks):
            self._track_rows[id(track)] = row

            check = QTableWidgetItem()
            check.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            check.setCheckState(Qt.CheckState.Checked)

            self.track_table.setItem(row, 0, check)

            values = (
                str(row + 1),
                track.title,
                track.artist or "",
                track.album or "",
                format_duration(track.duration),
                "—",
            )

            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)

                flags = (
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                )

                if column in (2, 3, 4):
                    flags |= Qt.ItemFlag.ItemIsEditable
                    item.setToolTip(
                        "Double-click to correct this metadata."
                    )

                item.setFlags(flags)

                self.track_table.setItem(
                    row,
                    column,
                    item,
                )

        self._populating = False
        self._update_selection_label()

    def _selected_tracks(self) -> list[Track]:
        selected: list[Track] = []

        for row, track in enumerate(self._tracks):
            item = self.track_table.item(row, 0)

            if (
                item is not None
                and item.checkState()
                == Qt.CheckState.Checked
            ):
                selected.append(track)

        return selected

    def _set_all_checked(self, checked: bool) -> None:
        if not self._tracks:
            return

        state = (
            Qt.CheckState.Checked
            if checked
            else Qt.CheckState.Unchecked
        )

        self._populating = True

        for row in range(self.track_table.rowCount()):
            item = self.track_table.item(row, 0)

            if item is not None:
                item.setCheckState(state)

        self._populating = False
        self._update_selection_label()

    def _on_track_item_changed(
        self,
        item: QTableWidgetItem,
    ) -> None:
        if self._populating:
            return

        row = item.row()

        if not 0 <= row < len(self._tracks):
            return

        track = self._tracks[row]

        if item.column() == 0:
            self._update_selection_label()
            return

        text = item.text().strip()

        if item.column() == 2:
            if text:
                track.title = text
            else:
                item.setText(track.title)
        elif item.column() == 3:
            track.artist = text or None
        elif item.column() == 4:
            track.album = text or None

    def _on_track_complete(self, track, result) -> None:
        """Show the per-track lyrics result in the table."""

        row = self._track_rows.get(id(track))

        if row is None:
            return

        item = self.track_table.item(row, 6)

        if item is None:
            return

        status = result.lyrics_status

        if status == "saved":
            text = (
                f"Saved ({result.lyrics_note})"
                if result.lyrics_note
                else "Saved"
            )
        elif status == "below_threshold":
            text = (
                f"Skipped ({result.lyrics_note})"
                if result.lyrics_note
                else "Skipped"
            )
        elif status == "not_found":
            text = "Not found"
            if result.lyrics_note:
                text += f" ({result.lyrics_note})"
        elif status == "error":
            text = "Error"
            if result.lyrics_note:
                text += f" ({result.lyrics_note})"
        else:
            text = "Off"

        color = LYRICS_COLORS.get(status)

        item.setText(text)
        item.setToolTip(text)

        if color is not None:
            item.setForeground(QBrush(color))

    def _update_selection_label(self) -> None:
        count = len(self._selected_tracks())
        total = len(self._tracks)

        self.selection_label.setText(
            f"{count} of {total} selected"
            if total
            else "Load a URL to review its tracks."
        )

        busy = (
            self._load_worker is not None
            or self._worker is not None
        )

        self.start_button.setEnabled(not busy and count > 0)

        has_tracks = total > 0
        self.select_all_button.setEnabled(
            not busy and has_tracks
        )
        self.select_none_button.setEnabled(
            not busy and has_tracks
        )

    def _set_busy(self, busy: bool) -> None:
        self.load_button.setEnabled(not busy)
        self.url_input.setEnabled(not busy)
        self.cancel_button.setEnabled(
            busy and self._worker is not None
        )

        self.start_button.setEnabled(
            not busy and bool(self._selected_tracks())
        )

        self.select_all_button.setEnabled(
            not busy and bool(self._tracks)
        )
        self.select_none_button.setEnabled(
            not busy and bool(self._tracks)
        )

    # ---------------------------------------------------------
    # Downloading
    # ---------------------------------------------------------

    def _start(self) -> None:
        if self._worker is not None:
            return

        tracks = self._selected_tracks()

        if not tracks:
            QMessageBox.warning(
                self,
                "No tracks selected",
                "Load a URL and select at least one track.",
            )
            return

        output_directory = Path(
            self.output_input.text().strip()
            or str(DEFAULT_OUTPUT)
        ).expanduser()

        worker = DownloadWorker(
            tracks=tracks,
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
        worker.track_complete.connect(self._on_track_complete)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_finished)

        self._worker = worker

        self._set_busy(True)
        self.log_view.clear()
        self.summary_label.clear()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting…")
        self.log_view.appendPlainText(
            f"Starting download of {len(tracks)} track(s)…"
        )

        worker.start()

    def _cancel(self) -> None:
        if self._worker is None:
            return

        self._worker.cancel()
        self.cancel_button.setEnabled(False)
        self.progress_label.setText("Cancelling…")
        self.log_view.appendPlainText("Cancelling…")

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
        worker = self._worker
        self._worker = None

        if worker is not None:
            worker.deleteLater()

        self._set_busy(False)
        self._update_selection_label()

    # ---------------------------------------------------------
    # Files
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

    def _open_output(self) -> None:
        directory = Path(
            self.output_input.text().strip()
            or str(DEFAULT_OUTPUT)
        ).expanduser()

        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            QMessageBox.warning(
                self,
                "Cannot open folder",
                str(error),
            )
            return

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(directory.resolve()))
        )

    # ---------------------------------------------------------
    # Window
    # ---------------------------------------------------------

    def shutdown(self) -> None:
        """Cancel and wait for running work."""

        if self._worker is not None:
            self._worker.cancel()

            if self._worker.isRunning():
                self._worker.wait(15000)

        if (
            self._load_worker is not None
            and self._load_worker.isRunning()
        ):
            self._load_worker.wait(15000)

    def closeEvent(self, event) -> None:
        self.shutdown()
        super().closeEvent(event)
