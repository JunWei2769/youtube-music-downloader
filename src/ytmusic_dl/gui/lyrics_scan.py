"""Lyrics scan orchestration for the download tab."""

from PySide6.QtCore import QObject, QTimer, Signal

from ytmusic_dl.gui.lyrics_scan_worker import LyricsScanWorker
from ytmusic_dl.models import LyricsResult, Track

class LyricsScanController(QObject):
    """Run availability scans and remember their results."""

    progress = Signal(int, int)
    scanned = Signal(object, object, object)
    failed = Signal(object, str)
    finished = Signal()

    RESCAN_DELAY_MS = 600

    def __init__(
        self,
        parent=None,
        *,
        delay_ms: int | None = None,
    ) -> None:
        super().__init__(parent)

        self._worker: LyricsScanWorker | None = None
        self._targeted_worker: LyricsScanWorker | None = None
        self._workers: list[LyricsScanWorker] = []
        self._generation = 0
        self._tracks: list[Track] = []
        self._results: dict[int, object] = {}
        self._pending_rescans: dict[int, Track] = {}

        self._rescan_timer = QTimer(self)
        self._rescan_timer.setSingleShot(True)
        self._rescan_timer.setInterval(
            self.RESCAN_DELAY_MS if delay_ms is None else delay_ms
        )
        self._rescan_timer.timeout.connect(self._run_rescan)

    # ---------------------------------------------------------
    # State
    # ---------------------------------------------------------

    @property
    def is_scanning(self) -> bool:
        """Return whether a full scan is running."""

        return self._worker is not None

    @property
    def generation(self) -> int:
        """Return the current scan generation."""

        return self._generation

    @property
    def rescan_timer(self) -> QTimer:
        """Return the debounce timer for metadata rescans."""

        return self._rescan_timer

    def is_rescan_pending(self, track: Track) -> bool:
        """Return whether a metadata rescan is queued or running."""

        return (
            id(track) in self._pending_rescans
            or (
                self._targeted_worker is not None
                and track in self._targeted_worker.tracks
            )
        )

    def scan_cache(
        self,
    ) -> dict[tuple[str, str, str, float | None], LyricsResult | None]:
        """Return scanned results keyed by metadata signature."""

        cache: dict[
            tuple[str, str, str, float | None],
            LyricsResult | None,
        ] = {}

        for track in self._tracks:
            if id(track) not in self._results:
                continue

            best = self._results[id(track)]
            cache[track.metadata_signature()] = (
                best.result if best is not None else None
            )

        return cache

    # ---------------------------------------------------------
    # Scanning
    # ---------------------------------------------------------

    def start(self, tracks: list[Track]) -> bool:
        """Start a full scan for the given tracks."""

        self.stop()
        self.stop_rescans()

        tracks = list(tracks)

        if not tracks:
            return False

        self._tracks = tracks
        self._results = {}
        self._generation += 1
        generation = self._generation

        worker = LyricsScanWorker(tracks, parent=self)
        worker.scanned.connect(
            lambda track, best, closest, gen=generation: (
                self._on_scanned(gen, track, best, closest)
            )
        )
        worker.failed.connect(
            lambda track, message, gen=generation: (
                self._on_failed(gen, track, message)
            )
        )
        worker.progress.connect(
            lambda index, total, gen=generation: (
                self._on_progress(gen, index, total)
            )
        )
        worker.finished.connect(
            lambda current=worker: self._on_finished(current)
        )

        self._worker = worker
        self._workers.append(worker)
        worker.start()

        return True

    def stop(self) -> None:
        """Cancel the full scan."""

        if self._worker is not None:
            self._worker.cancel()

        self._worker = None
        self._generation += 1

    def _on_scanned(
        self,
        generation: int,
        track: Track,
        best,
        closest,
    ) -> None:
        if generation != self._generation:
            return

        self._results[id(track)] = best
        self.scanned.emit(track, best, closest)

    def _on_progress(
        self,
        generation: int,
        index: int,
        total: int,
    ) -> None:
        if generation != self._generation:
            return

        self.progress.emit(index, total)

    def _on_failed(
        self,
        generation: int,
        track: Track,
        message: str,
    ) -> None:
        if generation != self._generation:
            return

        self._results[id(track)] = None
        self.failed.emit(track, message)

    def _on_finished(self, worker: LyricsScanWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)

        worker.deleteLater()

        if worker is self._worker:
            self._worker = None
            self.finished.emit()

    # ---------------------------------------------------------
    # Metadata rescans
    # ---------------------------------------------------------

    def forget(self, track: Track) -> None:
        """Drop a cached result, for example after an edit."""

        self._results.pop(id(track), None)

    def schedule_rescan(self, track: Track) -> None:
        """Queue a re-check after a metadata edit."""

        self.forget(track)
        self._pending_rescans[id(track)] = track
        self._rescan_timer.start()

    def stop_rescans(self) -> None:
        """Cancel queued and running metadata rescans."""

        self._rescan_timer.stop()
        self._pending_rescans.clear()

        if self._targeted_worker is not None:
            self._targeted_worker.cancel()
            self._targeted_worker = None

    def _run_rescan(self) -> None:
        if (
            self._targeted_worker is not None
            or not self._pending_rescans
        ):
            return

        tracks = list(self._pending_rescans.values())
        self._pending_rescans.clear()

        worker = LyricsScanWorker(tracks, parent=self)
        worker.scanned.connect(self._on_rescanned)
        worker.failed.connect(self._on_rescan_failed)
        worker.finished.connect(
            lambda current=worker: self._on_rescan_finished(current)
        )

        self._targeted_worker = worker
        self._workers.append(worker)
        worker.start()

    def _on_rescanned(
        self,
        track: Track,
        best,
        closest,
    ) -> None:
        self._results[id(track)] = best
        self.scanned.emit(track, best, closest)

    def _on_rescan_failed(
        self,
        track: Track,
        message: str,
    ) -> None:
        self._results[id(track)] = None
        self.failed.emit(track, message)

    def _on_rescan_finished(self, worker: LyricsScanWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)

        worker.deleteLater()

        if worker is self._targeted_worker:
            self._targeted_worker = None

        if self._pending_rescans:
            self._run_rescan()

    # ---------------------------------------------------------
    # Shutdown
    # ---------------------------------------------------------

    def shutdown(self, timeout_ms: int = 15000) -> None:
        """Cancel and wait for every scan worker."""

        self.stop()
        self.stop_rescans()

        for worker in list(self._workers):
            if worker.isRunning():
                worker.wait(timeout_ms)
