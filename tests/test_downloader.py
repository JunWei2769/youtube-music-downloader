from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ytmusic_dl.audio import AudioStreamInfo
from ytmusic_dl.browser import BrowserProfile
from ytmusic_dl.downloader import (
    audio_file_exists,
    download_track,
    find_existing_audio,
)
from ytmusic_dl.models import Track

TEST_BROWSER = BrowserProfile(
    name="vivaldi",
    path=Path("/fake/vivaldi/Default"),
)

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

def run_download(
    tmp_path: Path,
    audio_format: str,
    extension: str,
) -> tuple:
    """Run download_track against a mocked yt-dlp."""

    track = make_track()
    output_directory = tmp_path / "downloads"

    expected_path = (
        output_directory
        / f"01 - Test Artist - Test Song.{extension}"
    )

    info = {
        "acodec": "opus",
        "abr": 160.0,
        "ext": "webm",
        "requested_downloads": [
            {"filepath": str(expected_path)}
        ],
    }

    with (
        patch("ytmusic_dl.downloader.YoutubeDL") as mock_ydl,
        patch("ytmusic_dl.downloader.ensure_directory"),
        patch(
            "ytmusic_dl.downloader.probe_audio",
            return_value=AudioStreamInfo(
                codec=extension,
                bitrate=128.0,
            ),
        ),
    ):
        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = (
            mock_instance
        )

        def fake_extract(url: str, download: bool) -> dict:
            expected_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            expected_path.touch()
            return info

        mock_instance.extract_info.side_effect = fake_extract

        result = download_track(
            track,
            output_directory,
            audio_format=audio_format,
            browser=TEST_BROWSER,
        )

    return (
        result,
        expected_path,
        mock_ydl,
        mock_instance,
        track,
    )

def test_download_track_mp3(tmp_path: Path) -> None:
    """Test MP3 download configuration."""

    result, expected_path, mock_ydl, mock_instance, track = (
        run_download(tmp_path, "mp3", "mp3")
    )

    assert result.path == expected_path
    assert result.mode == "transcode"

    options = mock_ydl.call_args.args[0]

    assert options["format"] == "bestaudio/best"

    assert options["postprocessors"] == [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "0",
        }
    ]

    mock_instance.extract_info.assert_called_once_with(
        track.webpage_url,
        download=True,
    )

def test_download_track_opus(tmp_path: Path) -> None:
    """Test Opus download configuration."""

    result, expected_path, mock_ydl, _, _ = run_download(
        tmp_path,
        "opus",
        "opus",
    )

    assert result.path == expected_path

    options = mock_ydl.call_args.args[0]

    assert options["postprocessors"] == [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "opus",
            "preferredquality": "160",
        }
    ]

def test_download_track_flac(tmp_path: Path) -> None:
    """Test FLAC download configuration."""

    result, expected_path, mock_ydl, _, _ = run_download(
        tmp_path,
        "flac",
        "flac",
    )

    assert result.path == expected_path

    options = mock_ydl.call_args.args[0]

    assert options["postprocessors"] == [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "flac",
        }
    ]

def test_download_track_wav(tmp_path: Path) -> None:
    """Test WAV download configuration."""

    result, expected_path, mock_ydl, _, _ = run_download(
        tmp_path,
        "wav",
        "wav",
    )

    assert result.path == expected_path

    options = mock_ydl.call_args.args[0]

    assert options["postprocessors"] == [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
        }
    ]

def test_download_track_m4a(tmp_path: Path) -> None:
    """Test M4A download configuration."""

    result, expected_path, mock_ydl, _, _ = run_download(
        tmp_path,
        "m4a",
        "m4a",
    )

    assert result.path == expected_path

    options = mock_ydl.call_args.args[0]

    assert options["postprocessors"] == [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "m4a",
            "preferredquality": "256",
        }
    ]

def test_download_track_source_keeps_native_format(
    tmp_path: Path,
) -> None:
    """Source mode keeps the native stream without re-encoding."""

    result, expected_path, mock_ydl, _, _ = run_download(
        tmp_path,
        "source",
        "webm",
    )

    assert result.path == expected_path
    assert result.mode == "copy"
    assert result.source_codec == "opus"
    assert result.source_bitrate == 160.0
    assert result.source_ext == "webm"

    options = mock_ydl.call_args.args[0]

    assert options["format"] == "bestaudio/best"
    assert "postprocessors" not in options

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
            audio_format="aac",
            browser=TEST_BROWSER,
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

def test_download_track_skips_existing(tmp_path: Path) -> None:
    """Test that an existing audio file is not downloaded again."""

    track = make_track()
    output_directory = tmp_path / "downloads"

    expected_path = (
        output_directory
        / "01 - Test Artist - Test Song.mp3"
    )

    output_directory.mkdir(parents=True)
    expected_path.touch()

    with patch(
        "ytmusic_dl.downloader.YoutubeDL"
    ) as mock_ydl:

        result = download_track(
            track,
            output_directory,
            audio_format="mp3",
            browser=TEST_BROWSER,
        )

    assert result.path == expected_path
    assert result.mode == "skip"
    mock_ydl.assert_not_called()

def test_find_existing_audio_source_any_extension(
    tmp_path: Path,
) -> None:
    """Source mode recognises any native audio extension."""

    track = make_track()

    audio_path = (
        tmp_path / "01 - Test Artist - Test Song.webm"
    )

    audio_path.touch()

    assert find_existing_audio(
        track,
        tmp_path,
        "source",
    ) == audio_path

    assert audio_file_exists(track, tmp_path, "source")

def test_download_track_falls_back_when_info_has_no_path(
    tmp_path: Path,
) -> None:
    """Resolve the output file when yt-dlp returns no path."""

    track = make_track()
    output_directory = tmp_path / "downloads"

    expected_path = (
        output_directory
        / "01 - Test Artist - Test Song.mp3"
    )

    with (
        patch("ytmusic_dl.downloader.YoutubeDL") as mock_ydl,
        patch("ytmusic_dl.downloader.ensure_directory"),
        patch("ytmusic_dl.downloader.probe_audio"),
    ):
        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = (
            mock_instance
        )

        def fake_extract(url: str, download: bool) -> dict:
            expected_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            expected_path.touch()
            return {}

        mock_instance.extract_info.side_effect = fake_extract

        result = download_track(
            track,
            output_directory,
            audio_format="mp3",
        )

    assert result.path == expected_path
