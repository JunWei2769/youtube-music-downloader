"""Background worker that checks lyrics availability for loaded tracks."""

import threading

from PySide6.QtCore import QThread, Signal

from ytmusic_dl.lyrics import (
    pick_best_candidate,
    pick_closest_candidate,
    search_candidates,
)
from ytmusic_dl.models import Track

class LyricsScanWorker(QThread):
    """Search lyrics candidates for each reviewed track."""

    scanned = Signal(object, object, object)
    progress = Signal(int, int)
    failed = Signal(object, str)

    def __init__(
        self,
        tracks: list[Track],
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._tracks = list(tracks)
        self._cancel_event = threading.Event()

    @property
    def tracks(self) -> list[Track]:
        """Return the tracks this worker will scan."""

        return list(self._tracks)

    def cancel(self) -> None:
        """Ask the worker to stop after the current track."""

        self._cancel_event.set()

    def run(self) -> None:
        total = len(self._tracks)

        for index, track in enumerate(
            self._tracks,
            start=1,
        ):
            if self._cancel_event.is_set():
                return

            self.progress.emit(index, total)

            try:
                candidates = search_candidates(track)

            except Exception as error:
                self.failed.emit(track, str(error))
                continue

            best = pick_best_candidate(candidates)
            closest = (
                pick_closest_candidate(candidates)
                if best is None
                else None
            )

            self.scanned.emit(track, best, closest)
