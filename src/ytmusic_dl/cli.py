"""
Purpose: Command-line interface for YouTube Music Downloader.

Responsibility: User interaction and command-line arguments.
"""

import argparse
import sys
from importlib.metadata import version
from pathlib import Path

from ytmusic_dl.browser import (
    find_browser,
    find_browser_with_cookies,
    list_browsers,
)
from ytmusic_dl.cli_lyrics import run_lyrics_command
from ytmusic_dl.downloader import (
    AUDIO_FORMATS,
    extract_playlist,
    extract_single_track,
    list_audio_formats,
)
from ytmusic_dl.log import configure_logging
from ytmusic_dl.pipeline import process_playlist


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""

    parser = argparse.ArgumentParser(
        prog="ytmusic-dl",
        description="Download music from YouTube Music playlists or tracks.",
        epilog=(
            "Lyrics-only commands: "
            "ytmusic-dl lyrics search --help, "
            "ytmusic-dl lyrics download --help"
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version('youtube-music-downloader')}",
    )

    parser.add_argument(
        "url",
        nargs="?",
        help="YouTube Music playlist or track URL",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("downloads"),
        help="Output directory (default: downloads)",
    )

    parser.add_argument(
        "--no-lyrics",
        action="store_true",
        help="Skip lyrics search and download",
    )

    parser.add_argument(
        "--lyrics-confidence",
        choices=("medium", "high"),
        default="high",
        help=(
            "Minimum lyrics match confidence to save "
            "(default: high)"
        ),
    )

    parser.add_argument(
        "--no-thumbnail",
        action="store_true",
        help="Skip thumbnail download and embedding",
    )

    parser.add_argument(
        "--audio-format",
        choices=AUDIO_FORMATS,
        default="mp3",
        help=(
            "Audio format (default: mp3; 'source' keeps the "
            "original stream without re-encoding)"
        ),
    )

    parser.add_argument(
        "--browser",
        choices=(
            "vivaldi",
            "chrome",
            "chromium",
            "brave",
            "firefox",
            "edge",
            "opera",
            "whale",
        ),
        help="Browser to use for YouTube cookies",
    )

    parser.add_argument(
        "--list-browsers",
        action="store_true",
        help="List detected browsers and YouTube cookie availability",
    )

    parser.add_argument(
        "--list-formats",
        action="store_true",
        help=(
            "List available audio formats and the selected "
            "bestaudio format for a URL"
        ),
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show lyrics provider diagnostics",
    )

    return parser

def _print_format_audit(args: argparse.Namespace) -> None:
    """Print available audio formats for a URL."""

    browser = None

    if args.browser:
        browser = find_browser(args.browser)

        if browser is None:
            print(
                "Error: Could not find usable YouTube cookies "
                f"in {args.browser}."
            )
            return
    else:
        browser = find_browser_with_cookies()

        if browser is not None:
            print(f"Using {browser.name} browser cookies")
            print()

    try:
        report = list_audio_formats(args.url, browser)
    except Exception as error:
        print(f"Error: Could not list formats: {error}")
        return

    print("=" * 60)
    print("Available Audio Formats")
    print("=" * 60)
    print(f"Title: {report.title}")
    print()

    if not report.formats:
        print("No audio-only formats were reported.")
        return

    print(
        f"{'Format':<8} {'Codec':<14} {'Bitrate':<10} "
        f"{'Container':<10} {'Note':<24} Selected"
    )

    for audio in report.formats:
        bitrate = (
            f"{audio.bitrate:.1f}"
            if audio.bitrate is not None
            else "-"
        )
        marker = (
            "*"
            if audio.format_id == report.selected_format_id
            else ""
        )

        print(
            f"{audio.format_id:<8} "
            f"{audio.codec or '-':<14} "
            f"{bitrate:<10} "
            f"{audio.extension:<10} "
            f"{audio.note or '':<24} "
            f"{marker}"
        )

    selected = next(
        (
            audio
            for audio in report.formats
            if audio.format_id == report.selected_format_id
        ),
        None,
    )

    if selected is not None:
        bitrate = (
            f"{selected.bitrate:.1f} kbps"
            if selected.bitrate is not None
            else "unknown bitrate"
        )
        print()
        print(
            f"Selected by bestaudio: {selected.format_id} "
            f"({selected.codec}, {bitrate})"
        )

    highest = report.formats[0]

    if highest.bitrate is not None:
        print(
            f"Highest bitrate:       {highest.format_id} "
            f"({highest.codec}, {highest.bitrate:.1f} kbps)"
        )

        if (
            selected is not None
            and selected.format_id != highest.format_id
        ):
            print(
                "Note: bestaudio may prefer a different codec at a "
                "similar bitrate (Opus is more efficient than AAC)."
            )

    if (
        highest.bitrate is None
        or highest.bitrate < 200
    ):
        print()
        print(
            "No high-bitrate (>= 200 kbps) stream was exposed. "
            "YouTube Music Premium 'High' quality may be required."
        )

def main() -> None:
    """Run the command-line application."""

    if len(sys.argv) > 1 and sys.argv[1] == "lyrics":
        sys.exit(run_lyrics_command(sys.argv[2:]))

    parser = build_parser()
    args = parser.parse_args()

    configure_logging(args.verbose)

    if args.list_browsers:
        print("=" * 60)
        print("Detected Browsers")
        print("=" * 60)
        print()

        browsers = list_browsers()

        if not browsers:
            print("No browser profiles detected.")
            return

        for browser, has_cookies in browsers:
            status = "YouTube cookies available" if has_cookies else "No usable YouTube cookies"

            print(f"Browser: {browser.name}")
            print(f"Profile: {browser.path}")
            print(f"Status:  {status}")
            print()

        return

    if not args.url:
        parser.error("the following arguments are required: url")

    if args.list_formats:
        _print_format_audit(args)
        return

    print("=" * 60)
    print("YouTube Music Downloader")
    print("=" * 60)
    print()

    print(f"URL:    {args.url}")
    print(f"Output: {args.output}")
    print()

    if "list=" in args.url:
        print("Extracting playlist...")
        extractor = extract_playlist
    else:
        print("Extracting single track...")
        extractor = extract_single_track

    try:
        tracks = extractor(args.url)
    except Exception as error:
        print()
        print("Error: Could not extract playlist.")
        print(f"Reason: {error}")
        return

    if not tracks:
        print()
        print("No tracks found in playlist.")
        return

    print(f"Found {len(tracks)} tracks.")
    print()

    for track in tracks:
        print(
            f"{track.playlist_index:02d}. "
            f"{track.title} - "
            f"{track.artist or 'Unknown Artist'}"
        )

    print()
    print("=" * 60)
    print("Starting download...")
    print("=" * 60)
    print()

    if args.browser:
        browser = find_browser(args.browser)

        if browser is None:
            print()
            print(
                f"Error: Could not find usable YouTube cookies "
                f"in {args.browser}."
            )
            return

    else:
        browser = None

    result = process_playlist(
        tracks,
        args.output,
        browser=browser,
        download_lyrics=not args.no_lyrics,
        download_thumbnails=not args.no_thumbnail,
        audio_format=args.audio_format,
        lyrics_min_confidence=args.lyrics_confidence,
    )

    print()
    print("=" * 60)
    print("DOWNLOAD COMPLETE")
    print("=" * 60)
    print()

    print(f"Tracks:       {result.total}")
    print(f"Successful:   {result.successful}")
    print(f"Failed:       {result.failed}")
    print(f"Skipped:      {result.skipped}")
    print(f"Lyrics:       {result.lyrics}")
    print(f"Thumbnails:   {result.thumbnails}")
    print()

    print(f"Output:       {result.output_directory}")

    if result.failed_tracks:
        print()
        print("Failed tracks:")

        for failed_track in result.failed_tracks:
            print(f"  - {failed_track}")
