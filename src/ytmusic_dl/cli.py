"""
Purpose: Command-line interface for YouTube Music Downloader.

Responsibility: User interaction and command-line arguments.
"""

import argparse
from pathlib import Path

from ytmusic_dl.pipeline import process_playlist
from ytmusic_dl.downloader import extract_playlist

def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""

    parser = argparse.ArgumentParser(
        prog="ytmusic-dl",
        description="Download music from YouTube Music playlists.",
    )

    parser.add_argument(
        "url",
        help="YouTube Music playlist URL"
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
        "--no-thumbnail",
        action="store_true",
        help="Skip thumbnail download and embedding",
    )

    parser.add_argument(
        "--audio-format",
        choices=("mp3", "opus"),
        default="mp3",
        help="Audio format (default: mp3)",
    )

    return parser

def main() -> None:
    """Run the command-line application."""

    parser = build_parser()
    args = parser.parse_args()

    print("=" * 60)
    print("YouTube Music Downloader")
    print("=" * 60)
    print()

    print(f"URL:    {args.url}")
    print(f"Output: {args.output}")
    print()

    print("Extracting playlist...")

    try:
        tracks = extract_playlist(args.url)
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

    result = process_playlist(
        tracks,
        args.output,
        download_lyrics=not args.no_lyrics,
        download_thumbnails=not args.no_thumbnail,
        audio_format=args.audio_format,
    )

    print()
    print("=" * 60)
    print("PLAYLIST COMPLETE")
    print("=" * 60)
    print()

    print(f"Tracks:       {result.total}")
    print(f"Successful:   {result.successful}")
    print(f"Failed:       {result.failed}")
    print(f"Lyrics:       {result.lyrics}")
    print(f"Thumbnails:   {result.thumbnails}")
    print()

    print(f"Output:       {result.output_directory}")

    if result.failed_tracks:
        print()
        print("Failed tracks:")

        for failed_track in result.failed_tracks:
            print(f"  - {failed_track}")
