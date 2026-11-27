"""Audio format audit worker and dialog."""

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ytmusic_dl.browser import find_browser
from ytmusic_dl.downloader import list_audio_formats
from ytmusic_dl.models import AudioFormatReport

AUDIT_COLUMNS = (
    "Format",
    "Codec",
    "Bitrate",
    "Sample rate",
    "Container",
    "Note",
    "Selected",
)

class FormatAuditWorker(QThread):
    """Fetch the available audio streams for a URL."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        url: str,
        *,
        browser_name: str | None = None,
        forceipv4: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._url = url
        self._browser_name = browser_name
        self._forceipv4 = forceipv4

    def run(self) -> None:
        try:
            browser = None

            if self._browser_name:
                browser = find_browser(self._browser_name)

                if browser is None:
                    self.failed.emit(
                        "No usable YouTube cookies in "
                        f"{self._browser_name}."
                    )
                    return

            report = list_audio_formats(
                self._url,
                browser,
                forceipv4=self._forceipv4,
            )

        except Exception as error:
            self.failed.emit(str(error))
            return

        self.completed.emit(report)

class FormatAuditDialog(QDialog):
    """Show available audio streams and the selected one."""

    def __init__(
        self,
        report: AudioFormatReport,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Available audio formats")
        self.resize(760, 380)

        layout = QVBoxLayout(self)

        title = QLabel(report.title or "Unknown track")
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)

        self.table = QTableWidget(
            len(report.formats),
            len(AUDIT_COLUMNS),
        )
        self.table.setHorizontalHeaderLabels(AUDIT_COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        selected_row = None

        for row, audio in enumerate(report.formats):
            is_selected = (
                audio.format_id == report.selected_format_id
            )

            if is_selected:
                selected_row = row

            values = (
                audio.format_id,
                audio.codec or "-",
                (
                    f"{audio.bitrate:.1f} kbps"
                    if audio.bitrate is not None
                    else "-"
                ),
                (
                    f"{audio.sample_rate:.0f} Hz"
                    if audio.sample_rate is not None
                    else "-"
                ),
                audio.extension,
                audio.note or "",
                "yes" if is_selected else "",
            )

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)

                if is_selected:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setToolTip(
                        "This stream is selected by bestaudio."
                    )

                self.table.setItem(row, column, item)

        self.table.setSortingEnabled(False)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table, 1)

        summary = self._summary(report)
        summary_label = QLabel(summary)
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        if selected_row is not None:
            self.table.selectRow(selected_row)

    @staticmethod
    def _summary(report: AudioFormatReport) -> str:
        if not report.formats:
            return "No audio-only formats were reported."

        highest = report.formats[0]
        parts = []

        selected = next(
            (
                audio
                for audio in report.formats
                if audio.format_id == report.selected_format_id
            ),
            None,
        )

        if selected is not None:
            bitrate = (
                f"{selected.bitrate:.1f} kbps"
                if selected.bitrate is not None
                else "unknown bitrate"
            )
            parts.append(
                "bestaudio selects "
                f"{selected.format_id} ({selected.codec}, {bitrate})."
            )

        bitrate = (
            f"{highest.bitrate:.1f} kbps"
            if highest.bitrate is not None
            else "unknown bitrate"
        )
        parts.append(
            f"Highest bitrate: {highest.format_id} "
            f"({highest.codec}, {bitrate})."
        )

        if highest.bitrate is None or highest.bitrate < 200:
            parts.append(
                "No high-bitrate (>= 200 kbps) stream was exposed. "
                "YouTube Music Premium 'High' quality may be required."
            )

        return " ".join(parts)
