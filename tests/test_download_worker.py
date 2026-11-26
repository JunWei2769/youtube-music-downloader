import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from ytmusic_dl.gui.download_worker import DownloadWorker
from ytmusic_dl.models import PlaylistResult, Track

def make_track() -> Track:
    return Track(
        playlist_index=1,
        title="Test Song",
        artist="Test Artist",
        duration=200,
        video_id="test123",
        webpage_url="https://youtube.com/watch?v=test123",
        playlist_name="Test Playlist",
    )

def test_worker_runs_pipeline(tmp_path: Path) -> None:
    """Extract tracks and run the download pipeline."""

    track = make_track()

    result = PlaylistResult(
        total=1,
        successful=1,
        failed=0,
        lyrics=0,
        thumbnails=0,
        output_directory=tmp_path,
        failed_tracks=[],
        skipped=0,
    )

    worker = DownloadWorker(
        url="https://music.youtube.com/playlist?list=test",
        output_directory=tmp_path,
        audio_format="m4a",
        download_lyrics=False,
        download_thumbnails=False,
    )

    logs: list[str] = []
    completed: list[PlaylistResult] = []

    worker.log.connect(logs.append)
    worker.completed.connect(completed.append)

    with (
        patch(
            "ytmusic_dl.gui.download_worker.extract_playlist",
            return_value=[track],
        ) as mock_extract,
        patch(
            "ytmusic_dl.gui.download_worker.process_playlist",
            return_value=result,
        ) as mock_process,
    ):
        worker.run()

    assert completed == [result]
    mock_extract.assert_called_once_with(worker._url)

    kwargs = mock_process.call_args.kwargs

    assert kwargs["audio_format"] == "m4a"
    assert kwargs["download_lyrics"] is False
    assert kwargs["download_thumbnails"] is False
    assert kwargs["cancel_event"] is worker._cancel_event

    assert logs[0].startswith("Extracting")

def test_worker_stops_when_cancelled(tmp_path: Path) -> None:
    """Do not run the pipeline after a cancellation request."""

    worker = DownloadWorker(
        url="https://music.youtube.com/watch?v=test123",
        output_directory=tmp_path,
        audio_format="mp3",
    )

    worker.cancel()

    logs: list[str] = []
    completed: list[PlaylistResult] = []

    worker.log.connect(logs.append)
    worker.completed.connect(completed.append)

    with (
        patch(
            "ytmusic_dl.gui.download_worker.extract_single_track",
            return_value=[make_track()],
        ),
        patch(
            "ytmusic_dl.gui.download_worker.process_playlist",
        ) as mock_process,
    ):
        worker.run()

    mock_process.assert_not_called()

    assert any("cancelled" in line.lower() for line in logs)

    assert len(completed) == 1
    assert completed[0].cancelled
    assert completed[0].output_directory == tmp_path
