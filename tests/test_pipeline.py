import threading
from pathlib import Path
from unittest.mock import patch

from yt_dlp.utils import DownloadCancelled

from ytmusic_dl.browser import BrowserProfile
from ytmusic_dl.models import (
    DownloadInfo,
    DownloadProgress,
    LyricsCandidate,
    LyricsResult,
    Track,
    TrackResult,
)
from ytmusic_dl.pipeline import process_playlist, process_track

TEST_BROWSER = BrowserProfile(
    name="vivaldi",
    path=Path("/fake/vivaldi/Default"),
)

def make_track(index: int) -> Track:
    """Create a test track."""
    return Track(
        playlist_index=index,
        title=f"Test Song {index}",
        artist="Test Artist",
        album="Test Album",
        duration=200,
        video_id=f"video{index}",
        webpage_url=f"https://youtube.com/watch?v=video{index}",
        playlist_name="Test Playlist",
    )

def make_lyrics_candidate(
    confidence: str,
) -> LyricsCandidate:
    """Create a scored lyrics candidate."""

    return LyricsCandidate(
        result=LyricsResult(
            provider="test",
            provider_id="1",
            track_name="Test Song 1",
            artist_name="Test Artist",
            album_name="Test Album",
            duration=200,
            instrumental=False,
            synced_lyrics="[00:01.00] Test lyrics",
            plain_lyrics=None,
        ),
        score=1.0,
        confidence=confidence,
    )

def test_process_playlist() -> None:
    """Test successful playlist processing."""

    tracks = [
        make_track(1),
        make_track(2),
        make_track(3),
    ]

    results = [
        TrackResult(
            audio_path=Path("song1.mp3"),
            lyrics_written=True,
            thumbnail_embedded=True,
        ),
        TrackResult(
            audio_path=Path("song2.mp3"),
            lyrics_written=True,
            thumbnail_embedded=False,
        ),
        TrackResult(
            audio_path=Path("song3.mp3"),
            lyrics_written=False,
            thumbnail_embedded=True,
        ),
    ]

    with (
        patch(
            "ytmusic_dl.pipeline.find_browser_with_cookies",
            return_value=TEST_BROWSER,
        ) as mock_find_browser,
        patch(
            "ytmusic_dl.pipeline.process_track",
            side_effect=results,
        ) as mock_process,
    ):

        result = process_playlist(
            tracks,
            Path("downloads/test"),
        )

    assert result.total == 3
    assert result.successful == 3
    assert result.failed == 0
    assert result.lyrics == 2
    assert result.thumbnails == 2
    assert result.failed_tracks == []

    assert result.output_directory == (
        Path("downloads/test") / "Test Playlist"
    )

    assert mock_find_browser.call_count == 1
    assert mock_process.call_count == 3

    for track in tracks:
        expected_directory = (
            Path("downloads/test") / "Test Playlist"
        )

        mock_process.assert_any_call(
            track,
            expected_directory,
            download_lyrics=True,
            download_thumbnails=True,
            audio_format="mp3",
            lyrics_min_confidence="high",
            progress=None,
            log=None,
            cancel_event=None,
            browser=TEST_BROWSER,
        )


def test_process_playlist_empty() -> None:
    """Test processing an empty playlist."""

    result = process_playlist(
        [],
        Path("downloads/test"),
    )

    assert result.total == 0
    assert result.successful == 0
    assert result.failed == 0
    assert result.lyrics == 0
    assert result.thumbnails == 0
    assert result.failed_tracks == []
    assert result.output_directory == Path("downloads/test")


def test_process_playlist_failure() -> None:
    """Test that failed tracks are recorded."""

    tracks = [
        make_track(1),
        make_track(2),
    ]

    successful_result = TrackResult(
        audio_path=Path("song1.mp3"),
        lyrics_written=True,
        thumbnail_embedded=True,
    )

    with (
        patch(
            "ytmusic_dl.pipeline.find_browser_with_cookies",
            return_value=TEST_BROWSER,
        ),
        patch(
            "ytmusic_dl.pipeline.process_track",
            side_effect=[
                successful_result,
                RuntimeError("Download failed"),
            ],
        ),
    ):
        result = process_playlist(
            tracks,
            Path("downloads/test"),
        )

    assert result.total == 2
    assert result.successful == 1
    assert result.failed == 1
    assert result.lyrics == 1
    assert result.thumbnails == 1

    assert len(result.failed_tracks) == 1
    assert "Test Song 2" in result.failed_tracks[0]
    assert "Download failed" in result.failed_tracks[0]

def test_process_playlist_without_lyrics_and_thumbnails() -> None:
    """Test disabling lyrics and thumbnails."""

    tracks = [
        make_track(1),
        make_track(2),
    ]

    results = [
        TrackResult(
            audio_path=Path("song1.mp3"),
            lyrics_written=False,
            thumbnail_embedded=False,
        ),
        TrackResult(
            audio_path=Path("song2.mp3"),
            lyrics_written=False,
            thumbnail_embedded=False,
        ),
    ]

    with (
        patch(
            "ytmusic_dl.pipeline.find_browser_with_cookies",
            return_value=TEST_BROWSER,
        ),
        patch(
            "ytmusic_dl.pipeline.process_track",
            side_effect=results,
        ) as mock_process,
    ):

        result = process_playlist(
            tracks,
            Path("downloads/test"),
            download_lyrics=False,
            download_thumbnails=False,
        )

    assert result.total == 2
    assert result.successful == 2
    assert result.failed == 0
    assert result.lyrics == 0
    assert result.thumbnails == 0
    assert result.failed_tracks == []

    expected_directory = (
        Path("downloads/test") / "Test Playlist"
    )

    for track in tracks:
        mock_process.assert_any_call(
            track,
            expected_directory,
            download_lyrics=False,
            download_thumbnails=False,
            audio_format="mp3",
            lyrics_min_confidence="high",
            progress=None,
            log=None,
            cancel_event=None,
            browser=TEST_BROWSER,
        )

def test_process_playlist_with_opus() -> None:
    """Test playlist processing with Opus audio format."""

    tracks = [
        make_track(1),
        make_track(2),
    ]

    results = [
        TrackResult(
            audio_path=Path("song1.opus"),
            lyrics_written=True,
            thumbnail_embedded=True,
        ),
        TrackResult(
            audio_path=Path("song2.opus"),
            lyrics_written=True,
            thumbnail_embedded=True,
        ),
    ]

    with (
        patch(
            "ytmusic_dl.pipeline.find_browser_with_cookies",
            return_value=TEST_BROWSER,
        ),
        patch(
            "ytmusic_dl.pipeline.process_track",
            side_effect=results,
        ) as mock_process,
    ):

        result = process_playlist(
            tracks,
            Path("downloads/test"),
            audio_format="opus",
        )

    assert result.total == 2
    assert result.successful == 2
    assert result.failed == 0
    assert result.lyrics == 2
    assert result.thumbnails == 2

    expected_directory = (
        Path("downloads/test") / "Test Playlist"
    )

    for track in tracks:
        mock_process.assert_any_call(
            track,
            expected_directory,
            download_lyrics=True,
            download_thumbnails=True,
            audio_format="opus",
            lyrics_min_confidence="high",
            progress=None,
            log=None,
            cancel_event=None,
            browser=TEST_BROWSER,
        )

def test_process_playlist_with_skipped_tracks() -> None:
    """Test playlist processing when tracks already exist."""

    tracks = [
        make_track(1),
        make_track(2),
    ]

    result = TrackResult(
        audio_path=Path("song2.mp3"),
        lyrics_written=True,
        thumbnail_embedded=True,
    )

    with (
        patch(
            "ytmusic_dl.pipeline.find_browser_with_cookies",
            return_value=TEST_BROWSER,
        ) as mock_find_browser,
        patch(
            "ytmusic_dl.pipeline.audio_file_exists",
            side_effect=[True, False],
        ) as mock_exists,
        patch(
            "ytmusic_dl.pipeline.process_track",
            return_value=result,
        ) as mock_process,
    ):
        playlist_result = process_playlist(
            tracks,
            Path("downloads/test"),
        )

    assert playlist_result.total == 2
    assert playlist_result.successful == 1
    assert playlist_result.failed == 0
    assert playlist_result.skipped == 1
    assert playlist_result.lyrics == 1
    assert playlist_result.thumbnails == 1

    assert mock_exists.call_count == 2
    assert mock_find_browser.call_count == 1
    assert mock_process.call_count == 1
    mock_process.assert_called_once()

def test_process_playlist_detects_existing_track(
    tmp_path: Path,
) -> None:
    """Test that an existing audio file is counted as skipped."""

    tracks = [make_track(1)]

    with (
        patch(
            "ytmusic_dl.pipeline.find_browser_with_cookies",
        ) as mock_find_browser,
        patch(
            "ytmusic_dl.pipeline.audio_file_exists",
            return_value=True,
        ) as mock_exists,
        patch(
            "ytmusic_dl.pipeline.process_track",
        ) as mock_process,
    ):
        playlist_result = process_playlist(
            tracks,
            tmp_path,
            audio_format="mp3",
        )

    assert playlist_result.total == 1
    assert playlist_result.successful == 0
    assert playlist_result.failed == 0
    assert playlist_result.skipped == 1
    assert playlist_result.lyrics == 0
    assert playlist_result.thumbnails == 0

    mock_find_browser.assert_not_called()

    mock_exists.assert_called_once_with(
        tracks[0],
        tmp_path / "Test Playlist",
        "mp3",
    )

    mock_process.assert_not_called()

def test_process_playlist_continues_without_cookies(
    capsys,
) -> None:
    """Test that a missing browser does not abort the playlist."""

    tracks = [make_track(1)]

    result = TrackResult(
        audio_path=Path("song1.mp3"),
        lyrics_written=True,
        thumbnail_embedded=True,
    )

    with (
        patch(
            "ytmusic_dl.pipeline.find_browser_with_cookies",
            return_value=None,
        ) as mock_find_browser,
        patch(
            "ytmusic_dl.pipeline.process_track",
            return_value=result,
        ) as mock_process,
    ):
        playlist_result = process_playlist(
            tracks,
            Path("downloads/test"),
        )

    assert playlist_result.total == 1
    assert playlist_result.successful == 1
    assert playlist_result.failed == 0

    mock_find_browser.assert_called_once()

    mock_process.assert_called_once_with(
        tracks[0],
        Path("downloads/test") / "Test Playlist",
        browser=None,
        download_lyrics=True,
        download_thumbnails=True,
        audio_format="mp3",
        lyrics_min_confidence="high",
        progress=None,
        log=None,
        cancel_event=None,
    )

    output = capsys.readouterr().out

    assert "Continuing without cookies" in output

def test_process_playlist_explicit_browser_skips_detection() -> None:
    """Test that an explicit browser skips automatic detection."""

    tracks = [make_track(1)]

    result = TrackResult(
        audio_path=Path("song1.mp3"),
        lyrics_written=False,
        thumbnail_embedded=False,
    )

    with (
        patch(
            "ytmusic_dl.pipeline.find_browser_with_cookies",
        ) as mock_find_browser,
        patch(
            "ytmusic_dl.pipeline.process_track",
            return_value=result,
        ) as mock_process,
    ):
        process_playlist(
            tracks,
            Path("downloads/test"),
            browser=TEST_BROWSER,
        )

    mock_find_browser.assert_not_called()

    mock_process.assert_called_once_with(
        tracks[0],
        Path("downloads/test") / "Test Playlist",
        browser=TEST_BROWSER,
        download_lyrics=True,
        download_thumbnails=True,
        audio_format="mp3",
        lyrics_min_confidence="high",
        progress=None,
        log=None,
        cancel_event=None,
    )

def test_process_track_writes_high_confidence_lyrics(
    tmp_path: Path,
) -> None:
    """Save lyrics that meet the default high-confidence policy."""

    track = make_track(1)
    audio_path = tmp_path / "song.mp3"

    with (
        patch(
            "ytmusic_dl.pipeline.download_track",
            return_value=DownloadInfo(path=audio_path),
        ),
        patch("ytmusic_dl.pipeline.write_metadata"),
        patch(
            "ytmusic_dl.pipeline.search_candidates",
            return_value=[make_lyrics_candidate("high")],
        ),
        patch(
            "ytmusic_dl.pipeline.write_lyrics",
        ) as mock_write,
    ):
        result = process_track(
            track,
            tmp_path,
            download_thumbnails=False,
        )

    assert result.lyrics_written is True
    assert result.lyrics_status == "saved"
    mock_write.assert_called_once()

def test_process_track_skips_medium_lyrics_by_default(
    tmp_path: Path,
    capsys,
) -> None:
    """Do not save medium-confidence lyrics without opt-in."""

    track = make_track(1)
    audio_path = tmp_path / "song.mp3"

    with (
        patch(
            "ytmusic_dl.pipeline.download_track",
            return_value=DownloadInfo(path=audio_path),
        ),
        patch("ytmusic_dl.pipeline.write_metadata"),
        patch(
            "ytmusic_dl.pipeline.search_candidates",
            return_value=[make_lyrics_candidate("medium")],
        ),
        patch(
            "ytmusic_dl.pipeline.write_lyrics",
        ) as mock_write,
    ):
        result = process_track(
            track,
            tmp_path,
            download_thumbnails=False,
        )

    assert result.lyrics_written is False
    assert result.lyrics_status == "below_threshold"
    mock_write.assert_not_called()

    assert "Skipped lyrics: medium confidence" in (
        capsys.readouterr().out
    )

def test_process_track_accepts_medium_when_configured(
    tmp_path: Path,
) -> None:
    """Save medium-confidence lyrics when explicitly allowed."""

    track = make_track(1)
    audio_path = tmp_path / "song.mp3"

    with (
        patch(
            "ytmusic_dl.pipeline.download_track",
            return_value=DownloadInfo(path=audio_path),
        ),
        patch("ytmusic_dl.pipeline.write_metadata"),
        patch(
            "ytmusic_dl.pipeline.search_candidates",
            return_value=[make_lyrics_candidate("medium")],
        ),
        patch(
            "ytmusic_dl.pipeline.write_lyrics",
        ) as mock_write,
    ):
        result = process_track(
            track,
            tmp_path,
            download_thumbnails=False,
            lyrics_min_confidence="medium",
        )

    assert result.lyrics_written is True
    mock_write.assert_called_once()

def test_process_track_reports_missing_lyrics(
    tmp_path: Path,
    capsys,
) -> None:
    """Report when no candidate passes the checks."""

    track = make_track(1)
    audio_path = tmp_path / "song.mp3"

    with (
        patch(
            "ytmusic_dl.pipeline.download_track",
            return_value=DownloadInfo(path=audio_path),
        ),
        patch("ytmusic_dl.pipeline.write_metadata"),
        patch(
            "ytmusic_dl.pipeline.search_candidates",
            return_value=[],
        ),
        patch(
            "ytmusic_dl.pipeline.write_lyrics",
        ) as mock_write,
    ):
        result = process_track(
            track,
            tmp_path,
            download_thumbnails=False,
        )

    assert result.lyrics_written is False
    assert result.lyrics_status == "not_found"
    mock_write.assert_not_called()

    assert "Lyrics: not found." in (
        capsys.readouterr().out
    )

def test_process_track_reports_audio_streams(
    tmp_path: Path,
    capsys,
) -> None:
    """Report source and output codec, bitrate, and mode."""

    track = make_track(1)
    audio_path = tmp_path / "song.mp3"

    download = DownloadInfo(
        path=audio_path,
        mode="transcode",
        source_codec="opus",
        source_bitrate=160.0,
        source_ext="webm",
        output_codec="mp3",
        output_bitrate=245.0,
    )

    with (
        patch(
            "ytmusic_dl.pipeline.download_track",
            return_value=download,
        ),
        patch("ytmusic_dl.pipeline.write_metadata"),
        patch(
            "ytmusic_dl.pipeline.search_candidates",
            return_value=[],
        ),
    ):
        process_track(
            track,
            tmp_path,
            download_thumbnails=False,
        )

    output = capsys.readouterr().out

    assert "Source: opus 160 kbps (webm)" in output
    assert "Output: mp3 245 kbps" in output
    assert "Mode:   transcode" in output

def test_process_track_warns_about_lossy_flac_source(
    tmp_path: Path,
    capsys,
) -> None:
    """Warn when FLAC is produced from a lossy source."""

    track = make_track(1)
    audio_path = tmp_path / "song.flac"

    download = DownloadInfo(
        path=audio_path,
        mode="transcode",
        source_codec="opus",
        source_bitrate=160.0,
        source_ext="webm",
        output_codec="flac",
        output_bitrate=None,
    )

    with (
        patch(
            "ytmusic_dl.pipeline.download_track",
            return_value=download,
        ),
        patch("ytmusic_dl.pipeline.write_metadata"),
        patch(
            "ytmusic_dl.pipeline.search_candidates",
            return_value=[],
        ),
    ):
        process_track(
            track,
            tmp_path,
            download_thumbnails=False,
            audio_format="flac",
        )

    output = capsys.readouterr().out

    assert (
        "Warning: FLAC cannot restore quality from a lossy source"
        in output
    )

def test_process_track_survives_unsupported_metadata(
    tmp_path: Path,
    capsys,
) -> None:
    """Keep a downloaded native file when tags are unsupported."""

    track = make_track(1)
    audio_path = tmp_path / "song.webm"

    with (
        patch(
            "ytmusic_dl.pipeline.download_track",
            return_value=DownloadInfo(
                path=audio_path,
                mode="copy",
                source_codec="opus",
            ),
        ),
        patch(
            "ytmusic_dl.pipeline.write_metadata",
            side_effect=ValueError(
                "Unsupported audio format: .webm"
            ),
        ),
        patch(
            "ytmusic_dl.pipeline.search_candidates",
            return_value=[],
        ),
    ):
        result = process_track(
            track,
            tmp_path,
            download_thumbnails=False,
            audio_format="source",
        )

    assert result.audio_path == audio_path
    assert "Warning: Could not write metadata" in (
        capsys.readouterr().out
    )

def test_process_playlist_reports_track_progress() -> None:
    """Forward per-track progress with index and total."""

    tracks = [make_track(1), make_track(2)]
    captured = []

    def fake_process(
        track,
        directory,
        *,
        progress=None,
        **kwargs,
    ):
        progress(track, DownloadProgress(percent=50.0))

        return TrackResult(
            audio_path=Path("song.mp3"),
            lyrics_written=False,
            thumbnail_embedded=False,
        )

    with (
        patch(
            "ytmusic_dl.pipeline.find_browser_with_cookies",
            return_value=TEST_BROWSER,
        ),
        patch(
            "ytmusic_dl.pipeline.audio_file_exists",
            return_value=False,
        ),
        patch(
            "ytmusic_dl.pipeline.process_track",
            side_effect=fake_process,
        ),
    ):
        process_playlist(
            tracks,
            Path("downloads/test"),
            progress=lambda track, update, index, total: (
                captured.append(
                    (track.title, update.percent, index, total)
                )
            ),
        )

    assert captured == [
        ("Test Song 1", 50.0, 1, 2),
        ("Test Song 2", 50.0, 2, 2),
    ]

def test_process_playlist_cancel_event_stops_immediately() -> None:
    """Stop before the first track when cancellation is set."""

    cancel_event = threading.Event()
    cancel_event.set()

    result = process_playlist(
        [make_track(1), make_track(2)],
        Path("downloads/test"),
        cancel_event=cancel_event,
    )

    assert result.cancelled
    assert result.successful == 0
    assert result.failed == 0
    assert result.failed_tracks == []

def test_process_playlist_marks_download_cancelled() -> None:
    """Treat DownloadCancelled as a cancellation, not a failure."""

    with (
        patch(
            "ytmusic_dl.pipeline.find_browser_with_cookies",
            return_value=TEST_BROWSER,
        ),
        patch(
            "ytmusic_dl.pipeline.audio_file_exists",
            return_value=False,
        ),
        patch(
            "ytmusic_dl.pipeline.process_track",
            side_effect=DownloadCancelled(
                "cancelled by test"
            ),
        ),
    ):
        result = process_playlist(
            [make_track(1), make_track(2)],
            Path("downloads/test"),
        )

    assert result.cancelled
    assert result.successful == 0
    assert result.failed == 0
    assert result.failed_tracks == []

def test_process_track_explains_rejected_lyrics(
    tmp_path: Path,
    capsys,
) -> None:
    """Report the provider artist when artist matching fails."""

    track = make_track(1)
    audio_path = tmp_path / "song.mp3"

    candidate = LyricsCandidate(
        result=LyricsResult(
            provider="netease",
            provider_id="1",
            track_name="山丘",
            artist_name="李宗盛",
            album_name=None,
            duration=406,
            instrumental=False,
            synced_lyrics="[00:01.00] Test lyrics",
            plain_lyrics=None,
        ),
        score=0.77,
        confidence="medium",
        rejection_reasons=["artist does not match"],
    )

    with (
        patch(
            "ytmusic_dl.pipeline.download_track",
            return_value=DownloadInfo(path=audio_path),
        ),
        patch("ytmusic_dl.pipeline.write_metadata"),
        patch(
            "ytmusic_dl.pipeline.search_candidates",
            return_value=[candidate],
        ),
        patch("ytmusic_dl.pipeline.write_lyrics") as mock_write,
    ):
        result = process_track(
            track,
            tmp_path,
            download_thumbnails=False,
        )

    assert result.lyrics_status == "not_found"
    assert result.lyrics_note is not None
    assert "artist does not match" in result.lyrics_note
    assert "provider artist: 李宗盛" in result.lyrics_note
    mock_write.assert_not_called()

    assert "provider artist: 李宗盛" in (
        capsys.readouterr().out
    )

def test_process_playlist_reports_completed_tracks() -> None:
    """Notify the caller after each processed track."""

    tracks = [make_track(1)]

    track_result = TrackResult(
        audio_path=Path("song.mp3"),
        lyrics_written=True,
        thumbnail_embedded=False,
        lyrics_status="saved",
        lyrics_note="high · lrclib",
    )

    completed = []

    with (
        patch(
            "ytmusic_dl.pipeline.find_browser_with_cookies",
            return_value=TEST_BROWSER,
        ),
        patch(
            "ytmusic_dl.pipeline.audio_file_exists",
            return_value=False,
        ),
        patch(
            "ytmusic_dl.pipeline.process_track",
            return_value=track_result,
        ),
    ):
        process_playlist(
            tracks,
            Path("downloads/test"),
            on_track_complete=lambda track, result: (
                completed.append((track, result))
            ),
        )

    assert completed == [(tracks[0], track_result)]
