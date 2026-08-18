from pathlib import Path
from turtle import down
from unittest.mock import patch

from ytmusic_dl.models import Track, TrackResult
from ytmusic_dl.pipeline import process_playlist

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

    with patch(
        "ytmusic_dl.pipeline.process_track",
        side_effect=results,
    ) as mock_process:

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

    with patch(
        "ytmusic_dl.pipeline.process_track",
        side_effect=[
            successful_result,
            RuntimeError("Download failed"),
        ],
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

    with patch(
        "ytmusic_dl.pipeline.process_track",
        side_effect=results,
    ) as mock_process:

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

    with patch(
        "ytmusic_dl.pipeline.process_track",
        side_effect=results,
    ) as mock_process:

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
        )
