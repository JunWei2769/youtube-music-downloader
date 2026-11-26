"""Background worker for music downloads."""

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ytmusic_dl.browser import find_browser
from ytmusic_dl.downloader import (
    extract_playlist,
    extract_single_track,
)
from ytmusic_dl.models import PlaylistResult
from ytmusic_dl.pipeline import process_playlist

class DownloadWorker(QThread):
    """Extract, download, and process a playlist or track."""

    log = Signal(str)
    progress = Signal(object, object, int, int)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        *,
        url: str,
        output_directory: Path,
        audio_format: str,
        browser_name: str | None = None,
        download_lyrics: bool = True,
        download_thumbnails: bool = True,
        lyrics_min_confidence: str = "high",
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._url = url
        self._output_directory = output_directory
        self._audio_format = audio_format
        self._browser_name = browser_name
        self._download_lyrics = download_lyrics
        self._download_thumbnails = download_thumbnails
        self._lyrics_min_confidence = lyrics_min_confidence
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        """Ask the worker to stop."""

        self._cancel_event.set()

    def run(self) -> None:
        try:
            self.log.emit("Extracting track information…")

            if "list=" in self._url:
                tracks = extract_playlist(self._url)
            else:
                tracks = extract_single_track(self._url)

            if not tracks:
                self.failed.emit(
                    "No tracks found for that URL."
                )
                return

            if self._cancel_event.is_set():
                self.log.emit("Download cancelled.")
                self.completed.emit(
                    PlaylistResult(
                        total=0,
                        successful=0,
                        failed=0,
                        lyrics=0,
                        thumbnails=0,
                        output_directory=(
                            self._output_directory
                        ),
                        failed_tracks=[],
                        skipped=0,
                        cancelled=True,
                    )
                )
                return

            browser = None

            if self._browser_name:
                browser = find_browser(self._browser_name)

                if browser is None:
                    self.failed.emit(
                        "No usable YouTube cookies in "
                        f"{self._browser_name}."
                    )
                    return

                self.log.emit(
                    f"Using {browser.name} browser cookies"
                )

            result = process_playlist(
                tracks,
                self._output_directory,
                browser=browser,
                download_lyrics=self._download_lyrics,
                download_thumbnails=self._download_thumbnails,
                audio_format=self._audio_format,
                lyrics_min_confidence=(
                    self._lyrics_min_confidence
                ),
                log=self.log.emit,
                progress=self.progress.emit,
                cancel_event=self._cancel_event,
            )

        except Exception as error:
            self.failed.emit(str(error))
            return

        self.completed.emit(result)
