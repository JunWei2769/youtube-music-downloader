"""Track review table for the music download tab."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ytmusic_dl.lyrics import confidence_at_least
from ytmusic_dl.models import Track, TrackResult
from ytmusic_dl.utils import format_duration, parse_duration

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

LYRICS_COLUMN = 6

class TrackTable(QTableWidget):
    """Editable track list with selection and lyrics status."""

    selection_changed = Signal()
    metadata_edited = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(TRACK_COLUMNS), parent)

        self._tracks: list[Track] = []
        self._rows: dict[int, int] = {}
        self._checkboxes: dict[int, QCheckBox] = {}
        self._best: dict[int, object] = {}
        self._notes: dict[int, str] = {}
        self._minimum_confidence = "high"
        self._lyrics_enabled = True
        self._populating = False

        self.setHorizontalHeaderLabels(TRACK_COLUMNS)
        self.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed
        )
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)

        header = self.horizontalHeader()
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
        self.setColumnWidth(0, 80)

        duration_header = self.horizontalHeaderItem(5)

        if duration_header is not None:
            duration_header.setToolTip(
                "Video duration from YouTube. Double-click to enter "
                "the track length (for example 3:30); lyrics "
                "matching uses this value."
            )

        self.itemChanged.connect(self._on_item_changed)

    # ---------------------------------------------------------
    # Tracks and selection
    # ---------------------------------------------------------

    @property
    def tracks(self) -> list[Track]:
        """Return the displayed tracks."""

        return list(self._tracks)

    @property
    def checkboxes(self) -> dict[int, QCheckBox]:
        """Return the per-track selection checkboxes."""

        return self._checkboxes

    def set_tracks(self, tracks: list[Track]) -> None:
        """Replace the displayed tracks."""

        self._tracks = list(tracks)
        self._rows = {}
        self._checkboxes.clear()
        self._best.clear()
        self._notes.clear()
        self._populating = True

        self.setRowCount(0)
        self.setRowCount(len(self._tracks))

        for row, track in enumerate(self._tracks):
            self._rows[id(track)] = row

            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(
                lambda _state: self.selection_changed.emit()
            )

            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )
            container_layout.addWidget(checkbox)

            self.setCellWidget(row, 0, container)
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
                self.setItem(row, column, item)

        self._populating = False
        self.selection_changed.emit()

    def selected_tracks(self) -> list[Track]:
        """Return the tracks whose checkbox is checked."""

        selected: list[Track] = []

        for track in self._tracks:
            checkbox = self._checkboxes.get(id(track))

            if checkbox is not None and checkbox.isChecked():
                selected.append(track)

        return selected

    def set_all_checked(self, checked: bool) -> None:
        """Check or uncheck every track."""

        if not self._tracks:
            return

        self._populating = True

        for track in self._tracks:
            checkbox = self._checkboxes.get(id(track))

            if checkbox is not None:
                checkbox.setChecked(checked)

        self._populating = False
        self.selection_changed.emit()

    # ---------------------------------------------------------
    # Metadata edits
    # ---------------------------------------------------------

    def _on_item_changed(
        self,
        item: QTableWidgetItem,
    ) -> None:
        if self._populating:
            return

        row = item.row()

        if not 0 <= row < len(self._tracks):
            return

        track = self._tracks[row]
        column = item.column()

        if column == 2:
            text = item.text().strip()

            if text:
                track.title = text
            else:
                item.setText(track.title)
        elif column == 3:
            track.artist = item.text().strip() or None
        elif column == 4:
            track.album = item.text().strip() or None
        elif column == 5:
            try:
                seconds = parse_duration(item.text())
            except ValueError as error:
                self.set_cell_text(
                    row,
                    5,
                    format_duration(track.duration),
                )

                QMessageBox.warning(
                    self,
                    "Invalid duration",
                    str(error),
                )
                return

            track.duration = seconds
            self.set_cell_text(
                row,
                5,
                format_duration(seconds),
            )

        if column in (2, 3, 4, 5):
            self.clear_lyrics(track)
            self.mark_lyrics_pending(
                track,
                "Re-checking…",
                "Metadata changed; checking lyrics again…",
            )
            self.metadata_edited.emit(track)

    def set_cell_text(
        self,
        row: int,
        column: int,
        text: str,
    ) -> None:
        """Set a cell without treating it as a user edit."""

        item = self.item(row, column)

        if item is None:
            return

        self._populating = True
        item.setText(text)
        self._populating = False

    # ---------------------------------------------------------
    # Lyrics status
    # ---------------------------------------------------------

    def set_lyrics_enabled(self, enabled: bool) -> None:
        """Control how pending lyrics cells are displayed."""

        self._lyrics_enabled = enabled

    def set_minimum_confidence(self, value: str) -> None:
        """Apply a new confidence floor to the lyrics cells."""

        self._minimum_confidence = value
        self.refresh_lyrics()

    def clear_lyrics(self, track: Track) -> None:
        """Forget a scanned result for one track."""

        key = id(track)
        self._best.pop(key, None)
        self._notes.pop(key, None)

    def mark_lyrics_pending(
        self,
        track: Track,
        text: str,
        tooltip: str,
    ) -> None:
        """Show a transient lyrics status for one track."""

        item = self._lyrics_item(track)

        if item is None:
            return

        item.setText(text if self._lyrics_enabled else "Off")
        item.setForeground(QBrush(LYRICS_COLORS["off"]))
        item.setToolTip(
            tooltip
            if self._lyrics_enabled
            else "Lyrics download is disabled."
        )

    def update_lyrics(
        self,
        track: Track,
        best,
        note: str,
    ) -> None:
        """Store and render a lyrics scan result."""

        key = id(track)

        if key not in self._rows:
            return

        self._best[key] = best
        self._notes[key] = note
        self._render_lyrics(track)

    def set_lyrics_off(self) -> None:
        """Mark every lyrics cell as disabled."""

        self._best.clear()
        self._notes.clear()

        for row in range(self.rowCount()):
            item = self.item(row, LYRICS_COLUMN)

            if item is None:
                continue

            item.setText("Off")
            item.setForeground(QBrush(LYRICS_COLORS["off"]))
            item.setToolTip("Lyrics download is disabled.")

    def refresh_lyrics(self) -> None:
        """Re-render every lyrics cell."""

        for track in self._tracks:
            self._render_lyrics(track)

    def show_result(
        self,
        track: Track,
        result: TrackResult,
    ) -> None:
        """Show a per-track lyrics result after downloading."""

        item = self._lyrics_item(track)

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
        elif status == "exists":
            text = "Exists"
        elif status == "no_audio":
            text = "No audio"
        else:
            text = "Off"

        color = LYRICS_COLORS.get(status)

        item.setText(text)
        item.setToolTip(text)

        if color is not None:
            item.setForeground(QBrush(color))

    def _lyrics_item(self, track: Track) -> QTableWidgetItem | None:
        row = self._rows.get(id(track))

        if row is None:
            return None

        return self.item(row, LYRICS_COLUMN)

    def _render_lyrics(self, track: Track) -> None:
        item = self._lyrics_item(track)

        if item is None:
            return

        key = id(track)

        if key not in self._best and key not in self._notes:
            return

        best = self._best.get(key)
        note = self._notes.get(key, "")

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
            meets = confidence_at_least(
                best.confidence,
                self._minimum_confidence,
            )

            text = (
                f"Found ({best.confidence} · "
                f"{best.result.provider})"
            )

            if not meets:
                text += f" · below {self._minimum_confidence}"

            color = (
                LYRICS_COLORS["saved"]
                if meets
                else LYRICS_COLORS["below_threshold"]
            )
            tooltip = "; ".join(best.match_reasons) or text

        item.setText(text)
        item.setForeground(QBrush(color))
        item.setToolTip(tooltip)
