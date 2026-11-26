import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from ytmusic_dl.gui.download_worker import DownloadWorker
from ytmusic_dl.gui.extract_worker import ExtractWorker
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

def make_result(output_directory: Path) -> PlaylistResult:
    return PlaylistResult(
        total=1,
        successful=1,
        failed=0,
        lyrics=0,
        thumbnails=0,
        output_directory=output_directory,
        failed_tracks=[],
        skipped=0,
    )

def test_worker_downloads_reviewed_tracks(
    tmp_path: Path,
) -> None:
    """Run the pipeline for the tracks passed in."""

    track = make_track()
    result = make_result(tmp_path)

    worker = DownloadWorker(
        tracks=[track],
        output_directory=tmp_path,
        audio_format="m4a",
        download_lyrics=False,
        download_thumbnails=False,
    )

    completed: list[PlaylistResult] = []
    worker.completed.connect(completed.append)

    with patch(
        "ytmusic_dl.gui.download_worker.process_playlist",
        return_value=result,
    ) as mock_process:
        worker.run()

    assert completed == [result]

    call = mock_process.call_args

    assert call.args[0] == [track]
    assert call.kwargs["audio_format"] == "m4a"
    assert call.kwargs["download_lyrics"] is False
    assert call.kwargs["download_thumbnails"] is False
    assert call.kwargs["cancel_event"] is worker._cancel_event

def test_worker_propagates_cancel_event(
    tmp_path: Path,
) -> None:
    """Pass the cancellation event to the pipeline."""

    worker = DownloadWorker(
        tracks=[make_track()],
        output_directory=tmp_path,
        audio_format="mp3",
    )

    worker.cancel()

    with patch(
        "ytmusic_dl.gui.download_worker.process_playlist",
        return_value=make_result(tmp_path),
    ) as mock_process:
        worker.run()

    assert mock_process.call_args.kwargs[
        "cancel_event"
    ].is_set()

def test_extract_worker_loads_playlist() -> None:
    """Load playlist entries."""

    track = make_track()
    worker = ExtractWorker(
        "https://music.youtube.com/playlist?list=test"
    )

    completed: list[list[Track]] = []
    worker.completed.connect(completed.append)

    with patch(
        "ytmusic_dl.gui.extract_worker.extract_playlist",
        return_value=[track],
    ) as mock_extract:
        worker.run()

    assert completed == [[track]]
    mock_extract.assert_called_once_with(worker._url)

def test_extract_worker_loads_single_track() -> None:
    """Load a single track when the URL is not a playlist."""

    track = make_track()
    worker = ExtractWorker(
        "https://music.youtube.com/watch?v=test123"
    )

    completed: list[list[Track]] = []
    worker.completed.connect(completed.append)

    with patch(
        "ytmusic_dl.gui.extract_worker.extract_single_track",
        return_value=[track],
    ):
        worker.run()

    assert completed == [[track]]

def test_extract_worker_reports_empty_results() -> None:
    """Report a URL that produced no tracks."""

    worker = ExtractWorker(
        "https://music.youtube.com/playlist?list=empty"
    )

    failed: list[str] = []
    worker.failed.connect(failed.append)

    with patch(
        "ytmusic_dl.gui.extract_worker.extract_playlist",
        return_value=[],
    ):
        worker.run()

    assert failed == ["No tracks found for that URL."]
