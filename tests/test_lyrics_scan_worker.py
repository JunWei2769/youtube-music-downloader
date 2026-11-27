import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from ytmusic_dl.gui.lyrics_scan_worker import LyricsScanWorker
from ytmusic_dl.models import (
    LyricsCandidate,
    LyricsResult,
    Track,
)

def make_track() -> Track:
    return Track(
        playlist_index=1,
        title="Test Song",
        artist="Test Artist",
        duration=200,
    )

def make_candidate() -> LyricsCandidate:
    return LyricsCandidate(
        result=LyricsResult(
            provider="lrclib",
            provider_id="1",
            track_name="Test Song",
            artist_name="Test Artist",
            album_name="Test Album",
            duration=200,
            instrumental=False,
            synced_lyrics="[00:01.00] Test lyrics",
            plain_lyrics=None,
        ),
        score=1.1,
        confidence="high",
    )

def test_scan_reports_best_candidate() -> None:
    """Emit the best candidate for a track."""

    track = make_track()
    candidate = make_candidate()
    worker = LyricsScanWorker([track])

    scanned = []
    worker.scanned.connect(lambda *args: scanned.append(args))

    with patch(
        "ytmusic_dl.gui.lyrics_scan_worker.search_candidates",
        return_value=[candidate],
    ):
        worker.run()

    assert len(scanned) == 1
    assert scanned[0][0] is track
    assert scanned[0][1] is candidate
    assert scanned[0][2] is None

def test_scan_reports_missing_lyrics() -> None:
    """Report a track with no candidates."""

    track = make_track()
    worker = LyricsScanWorker([track])

    scanned = []
    worker.scanned.connect(lambda *args: scanned.append(args))

    with patch(
        "ytmusic_dl.gui.lyrics_scan_worker.search_candidates",
        return_value=[],
    ):
        worker.run()

    assert scanned == [(track, None, None)]

def test_scan_stops_when_cancelled() -> None:
    """Do not search after cancellation."""

    worker = LyricsScanWorker([make_track()])
    worker.cancel()

    scanned = []
    worker.scanned.connect(lambda *args: scanned.append(args))

    with patch(
        "ytmusic_dl.gui.lyrics_scan_worker.search_candidates",
    ) as mock_search:
        worker.run()

    mock_search.assert_not_called()
    assert scanned == []
