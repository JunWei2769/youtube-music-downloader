from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ytmusic_dl.downloader import download_track
from ytmusic_dl.models import Track

def make_track() -> Track:
    return Track(
        playlist_index=1,
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        duration=200,
        video_id="test123",
        webpage_url="https://youtube.com/watch?v=test123",
        playlist_name="Test Playlist",
    )

def test_download_track_mp3() -> None:
    """Test MP3 download configuration."""

    track = make_track()
    output_directory = Path("downloads/test")

    expected_path = (
        output_directory
        / "01 - Test Artist - Test Song.mp3"
    )

    with (
        patch("ytmusic_dl.downloader.YoutubeDL") as mock_ydl,
        patch("ytmusic_dl.downloader.ensure_directory"),
    ):
        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = mock_instance

        with patch.object(
            Path,
            "exists",
            return_value=True,
        ):
            result = download_track(
                track,
                output_directory,
                audio_format="mp3",
            )

    assert result == expected_path

    options = mock_ydl.call_args.args[0]

    assert options["format"] == "bestaudio/best"

    assert options["postprocessors"] == [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "0",
        }
    ]

    mock_instance.download.assert_called_once_with(
        [track.webpage_url]
    )

def test_download_track_opus() -> None:
    """Test Opus download configuration."""

    track = make_track()
    output_directory = Path("downloads/test")

    expected_path = (
        output_directory
        / "01 - Test Artist - Test Song.opus"
    )

    with (
        patch("ytmusic_dl.downloader.YoutubeDL") as mock_ydl,
        patch("ytmusic_dl.downloader.ensure_directory"),
    ):
        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = mock_instance

        with patch.object(
            Path,
            "exists",
            return_value=True,
        ):
            result = download_track(
                track,
                output_directory,
                audio_format="opus",
            )

    assert result == expected_path

    options = mock_ydl.call_args.args[0]

    assert options["format"] == "bestaudio[acodec=opus]"

    assert options["postprocessors"] == [
        {
            "key": "FFmpegVideoRemuxer",
            "preferedformat": "opus",
        }
    ]

    mock_instance.download.assert_called_once_with(
        [track.webpage_url]
    )

def test_download_track_invalid_format() -> None:
    """Test that unsupported audio formats are rejected."""

    track = make_track()

    with pytest.raises(
        ValueError,
        match="Unsupported audio format",
    ):
        download_track(
            track,
            Path("downloads/test"),
            audio_format="flac",
        )

def test_extract_album_name() -> None:
    """Test extracting album names from playlist titles."""

    from ytmusic_dl.downloader import extract_album_name

    assert extract_album_name("Album - 純妹妹") == "純妹妹"
    assert extract_album_name("Album - The Album") == "The Album"

    assert extract_album_name("My Favorites") is None
    assert extract_album_name("Workout") is None
    assert extract_album_name(None) is None
    assert extract_album_name("Album - ") is None
