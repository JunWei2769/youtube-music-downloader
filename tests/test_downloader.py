import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt_dlp.utils import DownloadCancelled

from ytmusic_dl.audio import AudioStreamInfo
from ytmusic_dl.browser import BrowserProfile
from ytmusic_dl.downloader import (
    _apply_download_metadata,
    audio_file_exists,
    download_track,
    extract_playlist,
    extract_single_track,
    find_existing_audio,
)
from ytmusic_dl.models import DownloadProgress, Track

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

def test_extract_single_track_strips_artist_prefix() -> None:
    """Avoid repeating the artist in single-track titles."""

    info = {
        "title": (
            "Rick Astley - Never Gonna Give You Up "
            "(Official Video) (4K Remaster)"
        ),
        "uploader": "Rick Astley",
        "duration": 213,
        "id": "dQw4w9WgXcQ",
        "webpage_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
    }

    with patch("ytmusic_dl.downloader.YoutubeDL") as mock_ydl:
        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = (
            mock_instance
        )
        mock_instance.extract_info.return_value = info

        tracks = extract_single_track(
            "https://youtube.com/watch?v=dQw4w9WgXcQ"
        )

    assert len(tracks) == 1
    assert tracks[0].title == (
        "Never Gonna Give You Up (Official Video) (4K Remaster)"
    )
    assert tracks[0].artist == "Rick Astley"

def test_extract_single_track_prefers_track_field() -> None:
    """Use yt-dlp's clean track name when it is available."""

    info = {
        "title": "Rick Astley - Never Gonna Give You Up",
        "track": "Never Gonna Give You Up",
        "artist": "Rick Astley",
        "duration": 213,
        "id": "dQw4w9WgXcQ",
    }

    with patch("ytmusic_dl.downloader.YoutubeDL") as mock_ydl:
        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = (
            mock_instance
        )
        mock_instance.extract_info.return_value = info

        tracks = extract_single_track("https://youtube.com/watch")

    assert tracks[0].title == "Never Gonna Give You Up"

def test_extract_playlist_cleans_entry_titles() -> None:
    """Apply the same title cleanup to playlist entries."""

    info = {
        "title": "Test Playlist",
        "entries": [
            {
                "title": "Test Artist - First Song",
                "uploader": "Test Artist",
                "id": "one",
                "duration": 200,
            },
            {
                "title": "Test Artist - Second Song",
                "track": "Second Song",
                "artist": "Test Artist",
                "id": "two",
                "duration": 210,
            },
        ],
    }

    with patch("ytmusic_dl.downloader.YoutubeDL") as mock_ydl:
        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = (
            mock_instance
        )
        mock_instance.extract_info.return_value = info

        tracks = extract_playlist("https://youtube.com/playlist")

    assert tracks[0].title == "First Song"
    assert tracks[1].title == "Second Song"

def test_download_track_reports_progress(
    tmp_path: Path,
) -> None:
    """Forward yt-dlp progress to the callback."""

    track = make_track()
    output_directory = tmp_path / "downloads"

    expected_path = (
        output_directory
        / "01 - Test Artist - Test Song.mp3"
    )

    updates: list[DownloadProgress] = []

    with (
        patch("ytmusic_dl.downloader.YoutubeDL") as mock_ydl,
        patch("ytmusic_dl.downloader.ensure_directory"),
        patch(
            "ytmusic_dl.downloader.probe_audio",
            return_value=AudioStreamInfo(
                codec="mp3",
                bitrate=320.0,
            ),
        ),
    ):
        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = (
            mock_instance
        )

        def fake_extract(url: str, download: bool) -> dict:
            hook = mock_ydl.call_args.args[0][
                "progress_hooks"
            ][0]

            hook(
                {
                    "status": "downloading",
                    "downloaded_bytes": 50,
                    "total_bytes": 100,
                    "speed": 1000.0,
                    "eta": 2,
                }
            )

            expected_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            expected_path.touch()

            return {
                "requested_downloads": [
                    {"filepath": str(expected_path)}
                ]
            }

        mock_instance.extract_info.side_effect = fake_extract

        result = download_track(
            track,
            output_directory,
            audio_format="mp3",
            progress=lambda current, update: updates.append(
                update
            ),
        )

    assert result.path == expected_path
    assert len(updates) == 1
    assert updates[0].percent == 50
    assert updates[0].stage == "download"
    assert updates[0].status == "downloading"

def test_download_track_cancel_raises(
    tmp_path: Path,
) -> None:
    """Raise before starting when cancellation is requested."""

    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(DownloadCancelled):
        download_track(
            make_track(),
            tmp_path / "downloads",
            audio_format="mp3",
            cancel_event=cancel_event,
        )

def test_extract_single_track_cleans_channel_artist() -> None:
    """Use the artist name instead of a VEVO channel name."""

    info = {
        "title": "Adele - Hello",
        "uploader": "AdeleVEVO",
        "duration": 295,
        "id": "x",
    }

    with patch("ytmusic_dl.downloader.YoutubeDL") as mock_ydl:
        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = (
            mock_instance
        )
        mock_instance.extract_info.return_value = info

        tracks = extract_single_track("https://youtube.com/watch")

    assert tracks[0].artist == "Adele"
    assert tracks[0].title == "Hello"

def test_extract_single_track_cleans_official_channel() -> None:
    """Strip the Official suffix from Chinese channel names."""

    info = {
        "title": "【单依纯《空耳》+《还你茉莉》】演唱会官摄",
        "uploader": "单依纯Official",
        "duration": 539,
        "id": "x",
    }

    with patch("ytmusic_dl.downloader.YoutubeDL") as mock_ydl:
        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = (
            mock_instance
        )
        mock_instance.extract_info.return_value = info

        tracks = extract_single_track("https://youtube.com/watch")

    assert tracks[0].artist == "单依纯"

def test_apply_download_metadata_enriches_track() -> None:
    """Use the watch page's artist, duration, and album."""

    track = Track(
        playlist_index=1,
        title="Song",
        artist="Label Channel",
        duration=None,
    )

    _apply_download_metadata(
        track,
        {
            "artist": "Singer",
            "duration": 200.5,
            "album": "Album",
        },
    )

    assert track.artist == "Singer"
    assert track.duration == 200.5
    assert track.album == "Album"

def test_apply_download_metadata_cleans_channel_name() -> None:
    """Clean a channel name when no artist field is available."""

    track = Track(
        playlist_index=1,
        title="Song",
        artist="单依纯Official",
        duration=None,
    )

    _apply_download_metadata(
        track,
        {"uploader": "单依纯Official"},
    )

    assert track.artist == "单依纯"
