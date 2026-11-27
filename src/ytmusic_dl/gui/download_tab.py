"""Music download tab for the desktop application."""

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QDesktopServices
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
from ytmusic_dl.gui.extract_worker import ExtractWorker
from ytmusic_dl.gui.format_audit import (
    FormatAuditDialog,
    FormatAuditWorker,
)
from ytmusic_dl.gui.lyrics_scan import LyricsScanController
from ytmusic_dl.gui.track_table import TRACK_COLUMNS, TrackTable
from ytmusic_dl.models import DownloadProgress, Track

__all__ = ["DownloadTab", "TRACK_COLUMNS"]

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
        self._audit_worker: FormatAuditWorker | None = None
        self._auto_scan_lyrics = auto_scan_lyrics

        self.scan = LyricsScanController(self)
        self.scan.progress.connect(self._on_scan_progress)
        self.scan.scanned.connect(self._on_scan_result)
        self.scan.failed.connect(self._on_scan_failed)
        self.scan.finished.connect(self._on_scan_finished)

        self._build_ui()
        self._load_settings()

    # ---------------------------------------------------------
    # Interface
    # ---------------------------------------------------------

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

        self.formats_button = QPushButton("Formats")
        self.formats_button.setToolTip(
            "Show the audio streams YouTube exposes for this URL."
        )
        self.formats_button.setEnabled(False)
        self.formats_button.clicked.connect(self._show_formats)

        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(self.load_button)
        url_row.addWidget(self.formats_button)

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

        self.force_ipv4_check = QCheckBox("Force IPv4")
        self.force_ipv4_check.setChecked(True)
        self.force_ipv4_check.setToolTip(
            "Disable this if YouTube downloads fail on an "
            "IPv6-only or dual-stack network."
        )

        options_row.addWidget(self.lyrics_check)
        options_row.addWidget(QLabel("Minimum confidence:"))
        options_row.addWidget(self.confidence_combo)
        options_row.addWidget(self.thumbnail_check)
        options_row.addWidget(self.force_ipv4_check)
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
        self.scan_button.setToolTip(
            "Check lyrics availability for the selected tracks."
        )
        self.scan_button.setEnabled(False)
        self.scan_button.clicked.connect(
            self._on_scan_button_clicked
        )

        self.lyrics_only_button = QPushButton("Lyrics for files")
        self.lyrics_only_button.setToolTip(
            "Write missing .lrc files for tracks whose audio has "
            "already been downloaded."
        )
        self.lyrics_only_button.setEnabled(False)
        self.lyrics_only_button.clicked.connect(
            lambda: self._start(lyrics_only=True)
        )

        selection_row.addWidget(self.selection_label, 1)
        selection_row.addWidget(self.select_all_button)
        selection_row.addWidget(self.select_none_button)
        selection_row.addWidget(self.scan_button)
        selection_row.addWidget(self.lyrics_only_button)

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

        self.track_table = TrackTable()
        self.track_table.selection_changed.connect(
            self._update_selection_label
        )
        self.track_table.metadata_edited.connect(
            self._on_metadata_edited
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
            self._on_confidence_changed
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

        self.force_ipv4_check.setChecked(
            self._settings.value(
                "download/force_ipv4",
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

        self.track_table.set_lyrics_enabled(
            self.lyrics_check.isChecked()
        )
        self.track_table.set_minimum_confidence(
            self.confidence_combo.currentData()
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
            "download/force_ipv4",
            self.force_ipv4_check.isChecked(),
        )
        self._settings.setValue(
            "download/confidence",
            self.confidence_combo.currentData(),
        )

    # ---------------------------------------------------------
    # Loading tracks
    # ---------------------------------------------------------

    def _on_url_changed(self, _text: str) -> None:
        has_url = bool(self.url_input.text().strip())
        self.formats_button.setEnabled(
            has_url
            and self._audit_worker is None
            and self._load_worker is None
            and self._worker is None
        )
        self._invalidate_tracks()

    def _invalidate_tracks(self) -> None:
        if self._load_worker is not None or self._worker is not None:
            return

        if not self.track_table.tracks:
            return

        self.scan.stop()
        self.scan.stop_rescans()
        self.track_table.set_tracks([])
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
        self.track_table.set_tracks(tracks)
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
            and self.track_table.tracks
            and not self.scan.is_scanning
        ):
            self._start_lyrics_scan()

    # ---------------------------------------------------------
    # Format audit
    # ---------------------------------------------------------

    def _show_formats(self) -> None:
        if self._audit_worker is not None:
            return

        url = self.url_input.text().strip()

        if not url:
            QMessageBox.warning(
                self,
                "Missing URL",
                "Enter a playlist or track URL.",
            )
            return

        worker = FormatAuditWorker(
            url,
            browser_name=self.browser_combo.currentData(),
            forceipv4=self.force_ipv4_check.isChecked(),
            parent=self,
        )

        worker.completed.connect(self._on_formats_loaded)
        worker.failed.connect(self._on_formats_failed)
        worker.finished.connect(self._on_formats_finished)

        self._audit_worker = worker
        self.formats_button.setEnabled(False)
        self.formats_button.setText("Loading…")
        worker.start()

    def _on_formats_loaded(self, report) -> None:
        dialog = FormatAuditDialog(report, self)
        dialog.exec()

    def _on_formats_failed(self, message: str) -> None:
        QMessageBox.warning(
            self,
            "Could not list formats",
            message,
        )

    def _on_formats_finished(self) -> None:
        worker = self._audit_worker
        self._audit_worker = None

        if worker is not None:
            worker.deleteLater()

        self.formats_button.setText("Formats")
        self.formats_button.setEnabled(
            bool(self.url_input.text().strip())
            and self._load_worker is None
            and self._worker is None
        )

    # ---------------------------------------------------------
    # Lyrics scan
    # ---------------------------------------------------------

    def _on_lyrics_toggled(self, checked: bool) -> None:
        self.confidence_combo.setEnabled(checked)
        self.track_table.set_lyrics_enabled(checked)

        if not checked:
            self.scan.stop()
            self.scan.stop_rescans()
            self.track_table.set_lyrics_off()
            self._reset_scan_button()
        elif self.track_table.tracks:
            self._start_lyrics_scan()

        self._update_selection_label()

    def _on_confidence_changed(self, _index: int) -> None:
        self.track_table.set_minimum_confidence(
            self.confidence_combo.currentData()
        )

    def _start_lyrics_scan(self) -> None:
        self.scan.stop_rescans()
        self.scan.stop()

        tracks = self.track_table.selected_tracks()

        if not tracks or not self.lyrics_check.isChecked():
            return

        if self._worker is not None or self._load_worker is not None:
            return

        for track in tracks:
            self.track_table.mark_lyrics_pending(
                track,
                "Searching…",
                "Searching lyrics providers…",
            )
            self.track_table.clear_lyrics(track)

        if not self.scan.start(tracks):
            return

        self.scan_button.setEnabled(True)
        self.scan_button.setText("Stop scanning…")

    def _on_scan_button_clicked(self) -> None:
        if self.scan.is_scanning:
            self._stop_lyrics_scan()
        else:
            self._start_lyrics_scan()

    def _stop_lyrics_scan(self) -> None:
        self.scan.stop()
        self.scan.stop_rescans()
        self._reset_scan_button()
        self._update_selection_label()

    def _reset_scan_button(self) -> None:
        self.scan_button.setText("Find lyrics")
        self.scan_button.setEnabled(
            bool(self.track_table.tracks)
            and bool(self.track_table.selected_tracks())
            and self._worker is None
            and self._load_worker is None
            and not self.scan.is_scanning
            and self.lyrics_check.isChecked()
        )

    def _on_scan_progress(self, index: int, total: int) -> None:
        self.scan_button.setText(
            f"Stop scanning ({index}/{total})"
        )

    def _on_scan_result(
        self,
        track: Track,
        best,
        closest,
    ) -> None:
        if self._worker is not None:
            return

        self.track_table.update_lyrics(
            track,
            best,
            self._closest_note(closest),
        )

    def _on_scan_failed(
        self,
        track: Track,
        message: str,
    ) -> None:
        if self._worker is not None:
            return

        self.track_table.update_lyrics(
            track,
            None,
            f"Error: {message}",
        )

    def _on_scan_finished(self) -> None:
        self._reset_scan_button()

    def _on_metadata_edited(self, track: Track) -> None:
        if not self.lyrics_check.isChecked():
            return

        if (
            self._worker is not None
            or self._load_worker is not None
        ):
            return

        self.scan.schedule_rescan(track)

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

    # ---------------------------------------------------------
    # Selection
    # ---------------------------------------------------------

    def _selected_tracks(self) -> list[Track]:
        return self.track_table.selected_tracks()

    def _set_all_checked(self, checked: bool) -> None:
        self.track_table.set_all_checked(checked)

    def _update_selection_label(self) -> None:
        count = len(self.track_table.selected_tracks())
        total = len(self.track_table.tracks)

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
        self.lyrics_only_button.setEnabled(
            not busy and count > 0
        )

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
            and (
                self.scan.is_scanning
                or (
                    count > 0
                    and self.lyrics_check.isChecked()
                )
            )
        )

    def _set_busy(self, busy: bool) -> None:
        self.load_button.setEnabled(not busy)
        self.url_input.setEnabled(not busy)
        self.formats_button.setEnabled(
            not busy and bool(self.url_input.text().strip())
        )
        self.cancel_button.setEnabled(
            busy and self._worker is not None
        )

        self.start_button.setEnabled(
            not busy and bool(self._selected_tracks())
        )
        self.lyrics_only_button.setEnabled(
            not busy and bool(self._selected_tracks())
        )

        self.select_all_button.setEnabled(
            not busy and bool(self.track_table.tracks)
        )
        self.select_none_button.setEnabled(
            not busy and bool(self.track_table.tracks)
        )
        self.scan_button.setEnabled(
            not busy
            and bool(self.track_table.tracks)
            and (
                self.scan.is_scanning
                or (
                    bool(self._selected_tracks())
                    and self.lyrics_check.isChecked()
                )
            )
        )

    # ---------------------------------------------------------
    # Downloading
    # ---------------------------------------------------------

    def _start(self, lyrics_only: bool = False) -> None:
        if self._worker is not None:
            return

        self.scan.stop()
        self.scan.stop_rescans()

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
            lyrics_cache=self.scan.scan_cache(),
            lyrics_only=lyrics_only,
            forceipv4=self.force_ipv4_check.isChecked(),
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

        if lyrics_only:
            self.progress_label.setText("Writing lyrics…")
            self.log_view.appendPlainText(
                f"Writing missing lyrics for {len(tracks)} "
                "track(s)…"
            )
        else:
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

    def _on_track_complete(self, track: Track, result) -> None:
        """Show the per-track lyrics result in the table."""

        self.track_table.show_result(track, result)

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

        self.scan.shutdown()

        if self._worker is not None:
            self._worker.cancel()

            if self._worker.isRunning():
                self._worker.wait(15000)

        for worker in (self._load_worker, self._audit_worker):
            if worker is not None and worker.isRunning():
                worker.wait(15000)

    def closeEvent(self, event) -> None:
        self.shutdown()
        super().closeEvent(event)
