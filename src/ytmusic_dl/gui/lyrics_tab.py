"""Lyrics-only tab for the desktop application."""

import html
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ytmusic_dl.gui.workers import (
    HydrateWorker,
    LyricsSearchWorker,
    SaveWorker,
)
from ytmusic_dl.models import LyricsCandidate, LyricsQuery
from ytmusic_dl.utils import build_lyrics_filename, format_duration

DEFAULT_OUTPUT = Path("downloads/lyrics")

COLUMNS = (
    "#",
    "Confidence",
    "Provider",
    "Title",
    "Artist",
    "Album",
    "Duration",
    "Score",
)

CONFIDENCE_COLORS = {
    "high": QColor("#2e7d32"),
    "medium": QColor("#b26a00"),
    "low": QColor("#b00020"),
}

REJECTED_COLOR = QColor("#8a8a8a")

class LyricsTab(QWidget):
    """Search providers and save a lyrics candidate."""

    def __init__(
        self,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__()

        self._settings = settings or QSettings()
        self._query: LyricsQuery | None = None
        self._candidates: list[LyricsCandidate] = []
        self._search_worker: LyricsSearchWorker | None = None
        self._hydrate_worker: HydrateWorker | None = None
        self._save_worker: SaveWorker | None = None
        self._hydrating_candidate: LyricsCandidate | None = None

        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        heading = QLabel("Lyrics Only")
        heading.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(heading)

        query_row = QHBoxLayout()

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText(
            "Song title or YouTube Music URL"
        )
        self.query_input.returnPressed.connect(self._search)

        query_row.addWidget(QLabel("Title or URL:"))
        query_row.addWidget(self.query_input, 1)

        layout.addLayout(query_row)

        meta_row = QHBoxLayout()

        self.artist_input = QLineEdit()
        self.artist_input.setPlaceholderText("Artist")

        self.album_input = QLineEdit()
        self.album_input.setPlaceholderText("Album (optional)")

        self.duration_input = QLineEdit()
        self.duration_input.setPlaceholderText("seconds")
        self.duration_input.setFixedWidth(90)

        meta_row.addWidget(QLabel("Artist:"))
        meta_row.addWidget(self.artist_input, 1)
        meta_row.addWidget(QLabel("Album:"))
        meta_row.addWidget(self.album_input, 1)
        meta_row.addWidget(QLabel("Duration:"))
        meta_row.addWidget(self.duration_input)

        layout.addLayout(meta_row)

        search_row = QHBoxLayout()

        self.search_button = QPushButton("Search lyrics")
        self.search_button.clicked.connect(self._search)

        self.status_label = QLabel("")

        search_row.addWidget(self.search_button)
        search_row.addWidget(self.status_label, 1)

        layout.addLayout(search_row)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )

        self.table.itemSelectionChanged.connect(
            self._on_selection_changed
        )

        layout.addWidget(self.table, 2)

        self.detail_label = QLabel(
            "Select a candidate to preview lyrics."
        )
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        layout.addWidget(self.detail_label)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Lyrics preview")
        self.preview.setMinimumHeight(150)

        layout.addWidget(self.preview, 1)

        save_row = QHBoxLayout()

        self.output_input = QLineEdit(str(DEFAULT_OUTPUT))

        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._browse)

        self.save_button = QPushButton("Save selected")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._save_selected)

        save_row.addWidget(QLabel("Output:"))
        save_row.addWidget(self.output_input, 1)
        save_row.addWidget(browse_button)
        save_row.addWidget(self.save_button)

        layout.addLayout(save_row)

    def _load_settings(self) -> None:
        self.output_input.setText(
            str(
                self._settings.value(
                    "lyrics/output",
                    str(DEFAULT_OUTPUT),
                )
            )
        )

    def save_state(self) -> None:
        """Persist the lyrics output directory."""

        self._settings.setValue(
            "lyrics/output",
            self.output_input.text().strip(),
        )

    # ---------------------------------------------------------
    # Search
    # ---------------------------------------------------------

    def _duration_value(self) -> float | None:
        text = self.duration_input.text().strip()

        if not text:
            return None

        try:
            value = float(text)
        except ValueError:
            raise ValueError(
                "Duration must be a number of seconds."
            ) from None

        if value <= 0:
            raise ValueError(
                "Duration must be greater than zero."
            )

        return value

    def _search(self) -> None:
        if self._search_worker is not None:
            return

        try:
            duration = self._duration_value()
        except ValueError as error:
            QMessageBox.warning(
                self,
                "Invalid duration",
                str(error),
            )
            return

        self._clear_results()

        self.search_button.setEnabled(False)
        self.status_label.setText("Searching…")

        worker = LyricsSearchWorker(
            self.query_input.text(),
            artist=self.artist_input.text().strip() or None,
            album=self.album_input.text().strip() or None,
            duration=duration,
            parent=self,
        )

        worker.completed.connect(self._on_search_completed)
        worker.failed.connect(self._on_search_failed)
        worker.finished.connect(self._on_search_finished)

        self._search_worker = worker
        worker.start()

    def _on_search_completed(
        self,
        query: LyricsQuery,
        candidates: list[LyricsCandidate],
    ) -> None:
        self._apply_results(query, candidates)

    def _on_search_failed(self, message: str) -> None:
        self.status_label.setText("Search failed.")
        QMessageBox.warning(
            self,
            "Lyrics search failed",
            message,
        )

    def _on_search_finished(self) -> None:
        self.search_button.setEnabled(True)

        if self._search_worker is not None:
            self._search_worker.deleteLater()

        self._search_worker = None

    def _apply_results(
        self,
        query: LyricsQuery,
        candidates: list[LyricsCandidate],
    ) -> None:
        """Populate the table from a completed search."""

        self._query = query
        self._candidates = sorted(
            candidates,
            key=lambda candidate: candidate.score,
            reverse=True,
        )

        self.table.setRowCount(0)
        self.table.setRowCount(len(self._candidates))

        for row, candidate in enumerate(self._candidates):
            result = candidate.result

            status = (
                candidate.confidence
                if candidate.accepted
                else "rejected"
            )

            values = (
                str(row + 1),
                status,
                result.provider,
                result.track_name,
                result.artist_name,
                result.album_name or "",
                format_duration(result.duration),
                f"{candidate.score:.2f}",
            )

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)

                if column in (6, 7):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )

                if column == 1:
                    color = (
                        CONFIDENCE_COLORS.get(
                            candidate.confidence
                        )
                        if candidate.accepted
                        else REJECTED_COLOR
                    )

                    if color is not None:
                        item.setForeground(QBrush(color))

                self.table.setItem(row, column, item)

        if self._candidates:
            self.status_label.setText(
                f"{len(self._candidates)} candidate(s)."
            )
            self.table.selectRow(0)
        else:
            self.status_label.setText(
                "No lyrics candidates found."
            )

    def _clear_results(self) -> None:
        self._query = None
        self._candidates = []
        self.table.setRowCount(0)
        self.preview.clear()
        self.detail_label.setText(
            "Select a candidate to preview lyrics."
        )
        self.save_button.setEnabled(False)

    # ---------------------------------------------------------
    # Preview
    # ---------------------------------------------------------

    def _selected_index(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()

        if not rows:
            return None

        row = rows[0].row()

        if not 0 <= row < len(self._candidates):
            return None

        return row

    def _selected_candidate(self) -> LyricsCandidate | None:
        index = self._selected_index()

        if index is None:
            return None

        return self._candidates[index]

    def _on_selection_changed(self) -> None:
        candidate = self._selected_candidate()

        if candidate is None:
            self.save_button.setEnabled(False)
            self.detail_label.setText(
                "Select a candidate to preview lyrics."
            )
            self.preview.clear()
            return

        self._show_candidate(candidate)
        self.save_button.setEnabled(candidate.accepted)

        has_lyrics = bool(
            candidate.result.synced_lyrics
            or candidate.result.plain_lyrics
        )

        if (
            candidate.accepted
            and not has_lyrics
            and self._hydrate_worker is None
        ):
            self._start_hydration(candidate)

    def _show_candidate(
        self,
        candidate: LyricsCandidate,
    ) -> None:
        result = candidate.result

        status = (
            candidate.confidence
            if candidate.accepted
            else "rejected"
        )

        details = [
            f"<b>{html.escape(result.provider)}</b> — "
            f"{html.escape(result.track_name)} — "
            f"{html.escape(result.artist_name)}",
            (
                f"Album: {html.escape(result.album_name or 'Unknown')}"
                f" · Duration: {format_duration(result.duration)}"
                f" · Score {candidate.score:.2f}"
                f" · {status}"
            ),
        ]

        if candidate.match_reasons:
            details.append(
                "Matches: "
                + html.escape("; ".join(candidate.match_reasons))
            )

        if candidate.warnings:
            details.append(
                "Notes: "
                + html.escape("; ".join(candidate.warnings))
            )

        if candidate.rejection_reasons:
            details.append(
                "Rejected: "
                + html.escape(
                    "; ".join(candidate.rejection_reasons)
                )
            )

        self.detail_label.setText("<br>".join(details))

        content = (
            result.synced_lyrics
            or result.plain_lyrics
        )

        self.preview.setPlainText(
            content or "Lyrics content not fetched yet."
        )

    # ---------------------------------------------------------
    # Hydration
    # ---------------------------------------------------------

    def _start_hydration(
        self,
        candidate: LyricsCandidate,
    ) -> None:
        self._hydrating_candidate = candidate
        self.preview.setPlainText("Fetching lyrics…")

        worker = HydrateWorker(
            candidate.result,
            parent=self,
        )

        worker.completed.connect(self._on_hydrated)
        worker.failed.connect(self._on_hydrate_failed)
        worker.finished.connect(self._on_hydrate_finished)

        self._hydrate_worker = worker
        worker.start()

    def _on_hydrated(self, hydrated) -> None:
        candidate = self._hydrating_candidate

        if candidate is None:
            return

        candidate.result = hydrated

        if self._selected_candidate() is candidate:
            self._show_candidate(candidate)

    def _on_hydrate_failed(self, message: str) -> None:
        self.preview.setPlainText(
            f"Could not fetch lyrics: {message}"
        )

    def _on_hydrate_finished(self) -> None:
        if self._hydrate_worker is not None:
            self._hydrate_worker.deleteLater()

        self._hydrate_worker = None
        self._hydrating_candidate = None

    # ---------------------------------------------------------
    # Saving
    # ---------------------------------------------------------

    def _browse(self) -> None:
        start = Path(
            self.output_input.text().strip()
            or str(DEFAULT_OUTPUT)
        ).expanduser()

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select lyrics output directory",
            str(start),
        )

        if directory:
            self.output_input.setText(directory)

    def _save_selected(self) -> None:
        if self._save_worker is not None:
            return

        candidate = self._selected_candidate()

        if candidate is None or self._query is None:
            return

        if not candidate.accepted:
            QMessageBox.warning(
                self,
                "Cannot save",
                "Rejected: "
                + "; ".join(candidate.rejection_reasons),
            )
            return

        output_directory = Path(
            self.output_input.text().strip()
            or str(DEFAULT_OUTPUT)
        ).expanduser()

        filename = build_lyrics_filename(
            self._query.title,
            self._query.artist,
        )

        output_path = output_directory / f"{filename}.lrc"

        if output_path.exists():
            answer = QMessageBox.question(
                self,
                "Replace lyrics file?",
                f"{output_path} already exists.\n"
                "Replace it?",
            )

            if answer != QMessageBox.StandardButton.Yes:
                return

        if candidate.confidence != "high":
            answer = QMessageBox.question(
                self,
                "Confirm match",
                f"This is a {candidate.confidence}-confidence "
                "match. Save it?",
            )

            if answer != QMessageBox.StandardButton.Yes:
                return

        self.save_button.setEnabled(False)
        self.status_label.setText("Saving…")

        worker = SaveWorker(
            candidate.result,
            output_path,
            parent=self,
        )

        worker.saved.connect(self._on_saved)
        worker.failed.connect(self._on_save_failed)
        worker.finished.connect(self._on_save_finished)

        self._save_worker = worker
        worker.start()

    def _on_saved(self, path: str) -> None:
        self.status_label.setText(f"Saved: {path}")

    def _on_save_failed(self, message: str) -> None:
        self.status_label.setText("Save failed.")
        QMessageBox.critical(
            self,
            "Could not save lyrics",
            message,
        )

    def _on_save_finished(self) -> None:
        candidate = self._selected_candidate()

        self.save_button.setEnabled(
            candidate is not None and candidate.accepted
        )

        if self._save_worker is not None:
            self._save_worker.deleteLater()

        self._save_worker = None

    # ---------------------------------------------------------
    # Window
    # ---------------------------------------------------------

    def shutdown(self) -> None:
        """Wait for running workers before the window closes."""

        for worker in (
            self._search_worker,
            self._hydrate_worker,
            self._save_worker,
        ):
            if worker is not None and worker.isRunning():
                worker.wait(15000)

    def closeEvent(self, event) -> None:
        """Stop workers when the tab closes."""

        self.shutdown()
        super().closeEvent(event)
