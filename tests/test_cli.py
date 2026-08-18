"""
Test the command-line interface.

These tests verify CLI argument parsing and application flow
without downloading anything from YouTube.
"""

from pathlib import Path
from unittest.mock import patch

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
    )

def test_main_no_tracks() -> None:
    """Test CLI behavior when no tracks are found."""

    with patch(
        "ytmusic_dl.cli.extract_playlist",
        return_value=[],
    ) as mock_extract:
        with patch(
            "sys.argv",
            [
                "ytmusic-dl",
                "https://music.youtube.com/playlist?list=test",
            ]
        ):
            main()

    mock_extract.assert_called_once_with(
        "https://music.youtube.com/playlist?list=test"
    )
