"""Background workers for the desktop application."""

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ytmusic_dl.gui.lyrics_query import build_lyrics_query
from ytmusic_dl.lyrics import (
    fetch_missing_lyrics,
    search_candidates,
    write_lyrics,
)
from ytmusic_dl.models import LyricsResult

class LyricsSearchWorker(QThread):
    """Search lyrics providers without blocking the interface."""

    completed = Signal(object, object)
    failed = Signal(str)

    def __init__(
        self,
        text: str,
        *,
        artist: str | None = None,
        album: str | None = None,
        duration: float | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._text = text
        self._artist = artist
        self._album = album
        self._duration = duration

    def run(self) -> None:
        try:
            query = build_lyrics_query(
                self._text,
                artist=self._artist,
                album=self._album,
                duration=self._duration,
            )

            candidates = search_candidates(query)

        except Exception as error:
            self.failed.emit(str(error))
            return

        self.completed.emit(query, candidates)

class HydrateWorker(QThread):
    """Fetch lyrics content for a candidate on demand."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        result: LyricsResult,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._result = result

    def run(self) -> None:
        try:
            hydrated = fetch_missing_lyrics(self._result)
        except Exception as error:
            self.failed.emit(str(error))
            return

        self.completed.emit(hydrated)

class SaveWorker(QThread):
    """Write lyrics without blocking the interface."""

    saved = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        result: LyricsResult,
        output_path: Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._result = result
        self._output_path = output_path

    def run(self) -> None:
        try:
            hydrated = fetch_missing_lyrics(self._result)
            write_lyrics(hydrated, self._output_path)
        except Exception as error:
            self.failed.emit(str(error))
            return

        self.saved.emit(str(self._output_path))
