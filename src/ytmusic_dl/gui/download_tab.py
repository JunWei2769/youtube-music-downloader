"""Music download tab for the desktop application."""

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
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
from ytmusic_dl.gui.lyrics_scan_worker import LyricsScanWorker
from ytmusic_dl.lyrics import confidence_at_least
from ytmusic_dl.models import DownloadProgress, Track
from ytmusic_dl.utils import format_duration, parse_duration

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
        *,
        auto_scan_lyrics: bool = True,
    ) -> None:
        super().__init__()

        self._settings = settings or QSettings()
        self._worker: DownloadWorker | None = None
        self._load_worker: ExtractWorker | None = None
        self._scan_worker: LyricsScanWorker | None = None
        self._scan_workers: list[LyricsScanWorker] = []
        self._scan_generation = 0
        self._scan_best: dict[int, object] = {}
        self._scan_note: dict[int, str] = {}
        self._edited_tracks: set[int] = set()
        self._pending_rescans: dict[int, Track] = {}
        self._targeted_worker: LyricsScanWorker | None = None
        self._tracks: list[Track] = []
        self._track_rows: dict[int, int] = {}
        self._checkboxes: dict[int, QCheckBox] = {}
        self._populating = False
        self._auto_scan_lyrics = auto_scan_lyrics

        self._rescan_timer = QTimer(self)
        self._rescan_timer.setSingleShot(True)
        self._rescan_timer.setInterval(600)
        self._rescan_timer.timeout.connect(
            self._run_targeted_rescan
        )

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

        self.scan_button = QPushButton("Find lyrics")
        self.scan_button.setEnabled(False)
        self.scan_button.clicked.connect(self._start_lyrics_scan)

        selection_row.addWidget(self.selection_label, 1)
        selection_row.addWidget(self.select_all_button)
        selection_row.addWidget(self.select_none_button)
        selection_row.addWidget(self.scan_button)

        layout.addLayout(selection_row)

        metadata_hint = QLabel(
            "Double-click Title, Artist, Album, or Duration to "
            "correct metadata before downloading. This also "
            "improves lyrics matching. The tab shows the YouTube "
            "video length; enter the track length if you know it, "
            "for example 3:30."
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
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Fixed,
        )
        self.track_table.setColumnWidth(0, 80)

        duration_header = self.track_table.horizontalHeaderItem(
            5
        )

        if duration_header is not None:
            duration_header.setToolTip(
                "Video duration from YouTube. Double-click to enter "
                "the track length (for example 3:30); lyrics "
                "matching uses this value."
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
            self._on_lyrics_toggled
        )
        self.confidence_combo.currentIndexChanged.connect(
            self._render_all_lyrics
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

        self._stop_lyrics_scan()
        self._stop_targeted_scan()
        self._scan_best.clear()
        self._scan_note.clear()
        self._edited_tracks.clear()

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

        if (
            self._auto_scan_lyrics
            and self._tracks
            and self._scan_worker is None
        ):
            self._start_lyrics_scan()

    # ---------------------------------------------------------
    # Lyrics scan
    # ---------------------------------------------------------

    def _on_lyrics_toggled(self, checked: bool) -> None:
        self.confidence_combo.setEnabled(checked)

        if not checked:
            self._stop_lyrics_scan()
            self._stop_targeted_scan()
            self._set_lyrics_off()
        elif self._tracks:
            self._start_lyrics_scan()

    def _set_lyrics_off(self) -> None:
        self._scan_best.clear()
        self._scan_note.clear()

        for row in range(self.track_table.rowCount()):
            item = self.track_table.item(row, 6)

            if item is None:
                continue

            item.setText("Off")
            item.setForeground(QBrush(LYRICS_COLORS["off"]))
            item.setToolTip("Lyrics download is disabled.")

    def _start_lyrics_scan(self) -> None:
        self._stop_lyrics_scan()
        self._stop_targeted_scan()
        self._edited_tracks.clear()

        if (
            not self._tracks
            or self._worker is not None
            or self._load_worker is not None
        ):
            return

        if not self.lyrics_check.isChecked():
            self._set_lyrics_off()
            return

        self._scan_best.clear()
        self._scan_note.clear()

        for row in range(self.track_table.rowCount()):
            item = self.track_table.item(row, 6)

            if item is None:
                continue

            item.setText("Searching…")
            item.setForeground(QBrush(LYRICS_COLORS["off"]))
            item.setToolTip("Searching lyrics providers…")

        self._scan_generation += 1
        generation = self._scan_generation

        worker = LyricsScanWorker(self._tracks, parent=self)

        worker.scanned.connect(
            lambda track, best, closest, gen=generation: (
                self._on_lyrics_scanned(
                    gen,
                    track,
                    best,
                    closest,
                )
            )
        )
        worker.failed.connect(
            lambda track, message, gen=generation: (
                self._on_lyrics_scan_failed(
                    gen,
                    track,
                    message,
                )
            )
        )
        worker.progress.connect(
            lambda index, total, gen=generation: (
                self._on_lyrics_scan_progress(
                    gen,
                    index,
                    total,
                )
            )
        )
        worker.finished.connect(
            lambda current=worker: (
                self._on_scan_worker_finished(current)
            )
        )

        self._scan_worker = worker
        self._scan_workers.append(worker)
        self.scan_button.setEnabled(False)
        self.scan_button.setText("Scanning…")
        worker.start()

    def _stop_lyrics_scan(self) -> None:
        worker = self._scan_worker

        if worker is not None:
            worker.cancel()

        self._scan_worker = None
        self._scan_generation += 1

        self.scan_button.setText("Find lyrics")
        self.scan_button.setEnabled(
            bool(self._tracks)
            and self._worker is None
            and self._load_worker is None
            and self.lyrics_check.isChecked()
        )

    def _on_scan_worker_finished(self, worker) -> None:
        if worker in self._scan_workers:
            self._scan_workers.remove(worker)

        worker.deleteLater()

        if worker is self._scan_worker:
            self._scan_worker = None
            self._edited_tracks.clear()
            self.scan_button.setText("Find lyrics")
            self.scan_button.setEnabled(
                bool(self._tracks)
                and self._worker is None
                and self.lyrics_check.isChecked()
            )

    def _on_lyrics_scan_progress(
        self,
        generation: int,
        index: int,
        total: int,
    ) -> None:
        if generation != self._scan_generation:
            return

        self.scan_button.setText(
            f"Scanning {index}/{total}…"
        )

    def _on_lyrics_scanned(
        self,
        generation: int,
        track,
        best,
        closest,
    ) -> None:
        if generation != self._scan_generation:
            return

        if self._worker is not None:
            return

        key = id(track)

        if key not in self._track_rows:
            return

        if key in self._edited_tracks:
            return

        self._scan_best[key] = best
        self._scan_note[key] = self._closest_note(
            closest
        )
        self._render_lyrics_cell(track)

    def _on_lyrics_scan_failed(
        self,
        generation: int,
        track,
        message: str,
    ) -> None:
        if generation != self._scan_generation:
            return

        key = id(track)

        if key not in self._track_rows:
            return

        self._scan_best[key] = None
        self._scan_note[key] = f"Error: {message}"
        self._render_lyrics_cell(track)

    @staticmethod
    def _closest_note(closest) -> str:
        if closest is None:
            return "No lyrics candidates found."

        reasons = "; ".join(closest.rejection_reasons)
        result = closest.result

        if (
            "artist does not match" in reasons
            and result.artist_name
        ):
            reasons += (
                f"; provider artist: {result.artist_name}"
            )

        if (
            "title similarity" in reasons
            and result.track_name
        ):
            reasons += (
                f"; provider title: {result.track_name}"
            )

        if reasons:
            return f"Rejected: {reasons}"

        return "No acceptable match."

    def _render_lyrics_cell(self, track) -> None:
        row = self._track_rows.get(id(track))

        if row is None:
            return

        item = self.track_table.item(row, 6)

        if item is None:
            return

        key = id(track)

        if (
            key not in self._scan_best
            and key not in self._scan_note
        ):
            return

        best = self._scan_best.get(key)
        note = self._scan_note.get(key, "")

        if best is None:
            if note.startswith("Error:"):
                text = "Error"
                color = LYRICS_COLORS["error"]
                tooltip = note
            else:
                text = "Not found"
                color = LYRICS_COLORS["not_found"]
                tooltip = note or "No acceptable lyrics match."
        else:
            minimum = self.confidence_combo.currentData()
            meets = confidence_at_least(
                best.confidence,
                minimum,
            )

            text = (
                f"Found ({best.confidence} · "
                f"{best.result.provider})"
            )

            if not meets:
                text += f" · below {minimum}"

            color = (
                LYRICS_COLORS["saved"]
                if meets
                else LYRICS_COLORS["below_threshold"]
            )
            tooltip = "; ".join(best.match_reasons) or text

        item.setText(text)
        item.setForeground(QBrush(color))
        item.setToolTip(tooltip)

    def _render_all_lyrics(self) -> None:
        for track in self._tracks:
            self._render_lyrics_cell(track)

    def _schedule_track_rescan(self, track) -> None:
        """Re-check lyrics after a metadata edit."""

        if not self.lyrics_check.isChecked():
            return

        if (
            self._worker is not None
            or self._load_worker is not None
        ):
            return

        key = id(track)
        self._edited_tracks.add(key)
        self._pending_rescans[key] = track
        self._rescan_timer.start()

    def _run_targeted_rescan(self) -> None:
        if (
            self._targeted_worker is not None
            or not self._pending_rescans
        ):
            return

        tracks = list(self._pending_rescans.values())
        self._pending_rescans.clear()

        worker = LyricsScanWorker(tracks, parent=self)
        worker.scanned.connect(self._on_targeted_scanned)
        worker.failed.connect(self._on_targeted_failed)
        worker.finished.connect(self._on_targeted_finished)

        self._targeted_worker = worker
        self._scan_workers.append(worker)
        worker.start()

    def _on_targeted_scanned(
        self,
        track,
        best,
        closest,
    ) -> None:
        if self._worker is not None:
            return

        key = id(track)

        if key not in self._track_rows:
            return

        self._scan_best[key] = best
        self._scan_note[key] = self._closest_note(closest)
        self._render_lyrics_cell(track)

    def _on_targeted_failed(
        self,
        track,
        message: str,
    ) -> None:
        if self._worker is not None:
            return

        key = id(track)

        if key not in self._track_rows:
            return

        self._scan_best[key] = None
        self._scan_note[key] = f"Error: {message}"
        self._render_lyrics_cell(track)

    def _on_targeted_finished(self) -> None:
        worker = self._targeted_worker
        self._targeted_worker = None

        if worker is not None:
            if worker in self._scan_workers:
                self._scan_workers.remove(worker)
            worker.deleteLater()

        if self._pending_rescans:
            self._run_targeted_rescan()

    def _stop_targeted_scan(self) -> None:
        self._rescan_timer.stop()
        self._pending_rescans.clear()

        if self._targeted_worker is not None:
            self._targeted_worker.cancel()

    def _populate_tracks(
        self,
        tracks: list[Track],
    ) -> None:
        self._tracks = list(tracks)
        self._track_rows = {}
        self._checkboxes.clear()
        self._scan_best.clear()
        self._scan_note.clear()
        self._edited_tracks.clear()
        self._populating = True

        self.track_table.setRowCount(0)
        self.track_table.setRowCount(len(self._tracks))

        for row, track in enumerate(self._tracks):
            self._track_rows[id(track)] = row

            checkbox = QCheckBox()
            checkbox.setChecked(True)

            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )
            container_layout.addWidget(checkbox)

            checkbox.stateChanged.connect(
                lambda _state: self._update_selection_label()
            )

            self.track_table.setCellWidget(row, 0, container)
            self._checkboxes[id(track)] = checkbox

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

                if column in (2, 3, 4, 5):
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

        for track in self._tracks:
            checkbox = self._checkboxes.get(id(track))

            if checkbox is not None and checkbox.isChecked():
                selected.append(track)

        return selected

    def _set_all_checked(self, checked: bool) -> None:
        if not self._tracks:
            return

        self._populating = True

        for track in self._tracks:
            checkbox = self._checkboxes.get(id(track))

            if checkbox is not None:
                checkbox.setChecked(checked)

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
        elif item.column() == 5:
            try:
                seconds = parse_duration(item.text())
            except ValueError as error:
                self._populating = True
                item.setText(
                    format_duration(track.duration)
                )
                self._populating = False

                QMessageBox.warning(
                    self,
                    "Invalid duration",
                    str(error),
                )
                return

            track.duration = seconds

            self._populating = True
            item.setText(format_duration(seconds))
            self._populating = False

        if item.column() in (2, 3, 4, 5):
            key = id(track)
            self._scan_best.pop(key, None)
            self._scan_note.pop(key, None)

            lyrics_item = self.track_table.item(row, 6)

            if lyrics_item is not None:
                if self.lyrics_check.isChecked():
                    lyrics_item.setText("Re-checking…")
                    lyrics_item.setToolTip(
                        "Metadata changed; checking lyrics again…"
                    )
                else:
                    lyrics_item.setText("Off")
                    lyrics_item.setToolTip(
                        "Lyrics download is disabled."
                    )

                lyrics_item.setForeground(
                    QBrush(LYRICS_COLORS["off"])
                )

            self._schedule_track_rescan(track)

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
        self.scan_button.setEnabled(
            not busy
            and has_tracks
            and self._scan_worker is None
            and self.lyrics_check.isChecked()
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
        self.scan_button.setEnabled(
            not busy
            and bool(self._tracks)
            and self._scan_worker is None
            and self.lyrics_check.isChecked()
        )

    # ---------------------------------------------------------
    # Downloading
    # ---------------------------------------------------------

    def _start(self) -> None:
        if self._worker is not None:
            return

        self._stop_lyrics_scan()
        self._stop_targeted_scan()

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

        self._stop_lyrics_scan()
        self._stop_targeted_scan()

        for worker in list(self._scan_workers):
            if worker.isRunning():
                worker.wait(15000)

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
