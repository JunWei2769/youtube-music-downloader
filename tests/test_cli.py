"""
Test the command-line interface.

These tests verify CLI argument parsing and application flow
without downloading anything from YouTube.
"""

from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

import pytest

from ytmusic_dl.browser import BrowserProfile
from ytmusic_dl.cli import build_parser, main
from ytmusic_dl.models import PlaylistResult, Track


def test_build_parser() -> None:
    """Test CLI argument parsing."""
    parser = build_parser()

    args = parser.parse_args(
        [
            "https://music.youtube.com/playlist?list=test",
            "--output",
            "downloads/test",
        ]
    )

    assert args.url == "https://music.youtube.com/playlist?list=test"
    assert args.output == Path("downloads/test")

def test_version(capsys) -> None:
    """Test the CLI version option."""
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])

    assert exc_info.value.code == 0

    captured = capsys.readouterr()

    assert captured.out == (
        f"ytmusic-dl {version('youtube-music-downloader')}\n"
    )

def test_main() -> None:
    """Test the complete CLI flow without real downloads."""

    tracks = [
        Track(
            playlist_index=1,
            title="Test Song",
            artist="Test Artist",
            album=None,
            duration=200,
            video_id="test123",
            webpage_url="https://youtube.com/watch?v=test123",
        )
    ]

    result = PlaylistResult(
        total=1,
        successful=1,
        failed=0,
        lyrics=1,
        thumbnails=1,
        output_directory=Path("downloads/test"),
        failed_tracks=[],
        skipped=0,
    )

    with (
        patch(
            "ytmusic_dl.cli.extract_playlist",
            return_value=tracks,
        ) as mock_extract,
        patch(
            "ytmusic_dl.cli.process_playlist",
            return_value=result,
        ) as mock_process,
        patch(
            "sys.argv",
            [
                "ytmusic-dl",
                "https://music.youtube.com/playlist?list=test",
                "--output",
                "downloads/test",
            ],
        ),
    ):
        main()

    mock_extract.assert_called_once_with(
        "https://music.youtube.com/playlist?list=test"
    )

    mock_process.assert_called_once_with(
        tracks,
        Path("downloads/test"),
        browser=None,
        download_lyrics=True,
        download_thumbnails=True,
        audio_format="mp3",
    )

def test_main_without_lyrics_and_thumbnail() -> None:
    """Test CLI options for disabling lyrics and thumbnails."""

    tracks = [
        Track(
            playlist_index=1,
            title="Test Song",
            artist="Test Artist",
            album=None,
            duration=200,
            video_id="test123",
            webpage_url="https://youtube.com/watch?v=test123",
            playlist_name="Test Playlist",
        )
    ]

    result = PlaylistResult(
        total=1,
        successful=1,
        failed=0,
        lyrics=0,
        thumbnails=0,
        output_directory=Path("downloads/test"),
        failed_tracks=[],
        skipped=0,
    )

    with (
        patch(
            "ytmusic_dl.cli.extract_playlist",
            return_value=tracks,
        ),
        patch(
            "ytmusic_dl.cli.process_playlist",
            return_value=result,
        ) as mock_process,
        patch(
            "sys.argv",
            [
                "ytmusic-dl",
                "https://music.youtube.com/playlist?list=test",
                "--output",
                "downloads/test",
                "--no-lyrics",
                "--no-thumbnail",
            ],
        ),
    ):
        main()

    mock_process.assert_called_once_with(
        tracks,
        Path("downloads/test"),
        browser=None,
        download_lyrics=False,
        download_thumbnails=False,
        audio_format="mp3",
    )

def test_main_extraction_failure(capsys) -> None:
    """Test CLI behavior when playlist extraction fails."""

    with patch(
        "ytmusic_dl.cli.extract_playlist",
        side_effect=RuntimeError("Invalid playlist URL"),
    ) as mock_extract, patch(
        "sys.argv",
        [
            "ytmusic-dl",
            "https://music.youtube.com/playlist?list=invalid",
        ],
    ):
        main()

    mock_extract.assert_called_once_with(
        "https://music.youtube.com/playlist?list=invalid"
    )

    captured = capsys.readouterr()

    assert "Error: Could not extract playlist." in captured.out
    assert "Invalid playlist URL" in captured.out

def test_main_no_tracks(capsys) -> None:
    """Test CLI behavior when no tracks are found."""

    with patch(
        "ytmusic_dl.cli.extract_playlist",
        return_value=[],
    ) as mock_extract, patch(
        "sys.argv",
        [
            "ytmusic-dl",
            "https://music.youtube.com/playlist?list=test",
        ],
    ):
        main()

    mock_extract.assert_called_once_with(
        "https://music.youtube.com/playlist?list=test"
    )

    captured = capsys.readouterr()

    assert "No tracks found in playlist." in captured.out

def test_main_with_failed_tracks(capsys) -> None:
    """Test CLI summary when tracks fail."""

    tracks = [
        Track(
            playlist_index=1,
            title="Test Song",
            artist="Test Artist",
            album=None,
            duration=200,
            video_id="test123",
            webpage_url="https://youtube.com/watch?v=test123",
            playlist_name="Test Playlist",
        )
    ]

    result = PlaylistResult(
        total=1,
        successful=0,
        failed=1,
        lyrics=0,
        thumbnails=0,
        output_directory=Path("downloads/test/Test Playlist"),
        failed_tracks=[
            "01 - Test Song: Download failed",
        ],
        skipped=0,
    )

    with (
        patch(
            "ytmusic_dl.cli.extract_playlist",
            return_value=tracks,
        ),
        patch(
            "ytmusic_dl.cli.process_playlist",
            return_value=result,
        ),
        patch(
            "sys.argv",
            [
                "ytmusic-dl",
                "https://music.youtube.com/playlist?list=test",
            ],
        ),
    ):
        main()

    captured = capsys.readouterr()

    assert "Failed:       1" in captured.out
    assert "Failed tracks:" in captured.out
    assert "01 - Test Song: Download failed" in captured.out

def test_main_with_browser() -> None:
    """Test CLI flow with an explicitly selected browser."""

    tracks = [
        Track(
            playlist_index=1,
            title="Test Song",
            artist="Test Artist",
            album=None,
            duration=200,
            video_id="test123",
            webpage_url="https://youtube.com/watch?v=test123",
            playlist_name="Test Playlist",
        )
    ]

    browser = BrowserProfile(
        name="vivaldi",
        path=Path("/fake/vivaldi/Default"),
    )

    result = PlaylistResult(
        total=1,
        successful=1,
        failed=0,
        lyrics=1,
        thumbnails=1,
        output_directory=Path("downloads"),
        failed_tracks=[],
        skipped=0,
    )

    with (
        patch(
            "ytmusic_dl.cli.extract_playlist",
            return_value=tracks,
        ),
        patch(
            "ytmusic_dl.cli.find_browser",
            return_value=browser,
        ) as mock_find_browser,
        patch(
            "ytmusic_dl.cli.process_playlist",
            return_value=result,
        ) as mock_process,
        patch(
            "sys.argv",
            [
                "ytmusic-dl",
                "https://music.youtube.com/playlist?list=test",
                "--browser",
                "vivaldi",
            ],
        ),
    ):
        main()

    mock_find_browser.assert_called_once_with("vivaldi")

    mock_process.assert_called_once_with(
        tracks,
        Path("downloads"),
        browser=browser,
        download_lyrics=True,
        download_thumbnails=True,
        audio_format="mp3",
    )

def test_main_with_unavailable_browser() -> None:
    """Test CLI error when the requested browser has no usable cookies."""

    tracks = [
        Track(
            playlist_index=1,
            title="Test Song",
            artist="Test Artist",
            album=None,
            duration=200,
            video_id="test123",
            webpage_url="https://youtube.com/watch?v=test123",
            playlist_name="Test Playlist",
        )
    ]

    with (
        patch(
            "ytmusic_dl.cli.extract_playlist",
            return_value=tracks,
        ),
        patch(
            "ytmusic_dl.cli.find_browser",
            return_value=None,
        ) as mock_find_browser,
        patch(
            "ytmusic_dl.cli.process_playlist",
        ) as mock_process,
        patch(
            "sys.argv",
            [
                "ytmusic-dl",
                "https://music.youtube.com/playlist?list=test",
                "--browser",
                "chrome",
            ],
        ),
    ):
        main()

    mock_find_browser.assert_called_once_with("chrome")
    mock_process.assert_not_called()

def test_main_without_browser_uses_automatic_detection() -> None:
    """Test CLI flow without explicitly selecting a browser."""

    tracks = [
        Track(
            playlist_index=1,
            title="Test Song",
            artist="Test Artist",
            album=None,
            duration=200,
            video_id="test123",
            webpage_url="https://youtube.com/watch?v=test123",
            playlist_name="Test Playlist",
        )
    ]

    result = PlaylistResult(
        total=1,
        successful=1,
        failed=0,
        lyrics=1,
        thumbnails=1,
        output_directory=Path("downloads"),
        failed_tracks=[],
        skipped=0,
    )

    with (
        patch(
            "ytmusic_dl.cli.extract_playlist",
            return_value=tracks,
        ),
        patch(
            "ytmusic_dl.cli.find_browser",
        ) as mock_find_browser,
        patch(
            "ytmusic_dl.cli.process_playlist",
            return_value=result,
        ) as mock_process,
        patch(
            "sys.argv",
            [
                "ytmusic-dl",
                "https://music.youtube.com/playlist?list=test",
            ],
        ),
    ):
        main()

    mock_find_browser.assert_not_called()

    mock_process.assert_called_once_with(
        tracks,
        Path("downloads"),
        browser=None,
        download_lyrics=True,
        download_thumbnails=True,
        audio_format="mp3",
    )

def test_main_list_browsers() -> None:
    """Test listing detected browsers."""

    browsers = [
        (
            BrowserProfile(
                name="vivaldi",
                path=Path("/fake/vivaldi/Default"),
            ),
            True,
        ),
        (
            BrowserProfile(
                name="firefox",
                path=Path("/fake/firefox/profile"),
            ),
            False,
        ),
    ]

    with (
        patch(
            "ytmusic_dl.cli.list_browsers",
            return_value=browsers,
        ) as mock_list_browsers,
        patch(
            "sys.argv",
            [
                "ytmusic-dl",
                "--list-browsers",
            ],
        ),
    ):
        main()

    mock_list_browsers.assert_called_once()

def test_main_list_browsers_none_detected() -> None:
    """Test browser listing when no browsers are detected."""

    with (
        patch(
            "ytmusic_dl.cli.list_browsers",
            return_value=[],
        ) as mock_list_browsers,
        patch(
            "sys.argv",
            [
                "ytmusic-dl",
                "--list-browsers",
            ],
        ),
    ):
        main()

    mock_list_browsers.assert_called_once()

def test_main_requires_url() -> None:
    """Test that a URL is required without --list-browsers."""

    with patch(
        "sys.argv",
        ["ytmusic-dl"],
    ):
        with pytest.raises(SystemExit):
            main()

def test_build_parser_audio_format() -> None:
    """Test audio format argument."""

    parser = build_parser()

    args = parser.parse_args(
        [
            "https://music.youtube.com/playlist?list=test",
        ]
    )

    assert args.audio_format == "mp3"

    args = parser.parse_args(
        [
            "https://music.youtube.com/playlist?list=test",
            "--audio-format",
            "opus",
        ]
    )

    assert args.audio_format == "opus"

def test_build_parser_invalid_audio_format() -> None:
    """Test invalid audio format is rejected."""

    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "https://music.youtube.com/playlist?list=test",
                "--audio-format",
                "aac",
            ]
        )

def test_main_with_opus_format() -> None:
    """Test CLI flow with Opus audio format."""

    tracks = [
        Track(
            playlist_index=1,
            title="Test Song",
            artist="Test Artist",
            album=None,
            duration=200,
            video_id="test123",
            webpage_url="https://youtube.com/watch?v=test123",
            playlist_name="Test Playlist",
        )
    ]

    result = PlaylistResult(
        total=1,
        successful=1,
        failed=0,
        lyrics=1,
        thumbnails=1,
        output_directory=Path("downloads/test"),
        failed_tracks=[],
        skipped=0
    )

    with (
        patch(
            "ytmusic_dl.cli.extract_playlist",
            return_value=tracks,
        ),
        patch(
            "ytmusic_dl.cli.process_playlist",
            return_value=result,
        ) as mock_process,
        patch(
            "sys.argv",
            [
                "ytmusic-dl",
                "https://music.youtube.com/playlist?list=test",
                "--audio-format",
                "opus",
            ],
        ),
    ):
        main()

    mock_process.assert_called_once_with(
        tracks,
        Path("downloads"),
        browser=None,
        download_lyrics=True,
        download_thumbnails=True,
        audio_format="opus",
    )
