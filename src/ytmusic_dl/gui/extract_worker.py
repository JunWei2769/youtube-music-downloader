"""Background worker that loads playlist or track metadata."""

from PySide6.QtCore import QThread, Signal

from ytmusic_dl.downloader import (
    extract_playlist,
    extract_single_track,
)

class ExtractWorker(QThread):
    """Load track metadata so it can be reviewed before downloading."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        url: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._url = url

    def run(self) -> None:
        try:
            if "list=" in self._url:
                tracks = extract_playlist(self._url)
            else:
                tracks = extract_single_track(self._url)

        except Exception as error:
            self.failed.emit(str(error))
            return

        if not tracks:
            self.failed.emit(
                "No tracks found for that URL."
            )
            return

        self.completed.emit(tracks)
