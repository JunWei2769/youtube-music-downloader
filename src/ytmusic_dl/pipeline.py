"""
Purpose: Coordinate the complete download process.

- Download audio
- Write metadata
- Download and embed thumbnail
- Search and write lyrics

Responsibility: Application workflow
"""

from pathlib import Path

from ytmusic_dl.audio import is_lossless
from ytmusic_dl.browser import (
    BrowserProfile,
    find_browser_with_cookies,
)
from ytmusic_dl.downloader import audio_file_exists, download_track
from ytmusic_dl.lyrics import (
    confidence_at_least,
    fetch_missing_lyrics,
    pick_best_candidate,
    search_candidates,
    write_lyrics,
)
from ytmusic_dl.metadata import write_metadata
from ytmusic_dl.models import (
    DownloadInfo,
    PlaylistResult,
    Track,
    TrackResult,
)
from ytmusic_dl.thumbnail import download_thumbnail, embed_thumbnail
from ytmusic_dl.utils import build_playlist_directory_name, ensure_directory


def _describe_stream(
    codec: str | None,
    bitrate: float | None,
    extension: str | None = None,
) -> str:
    """Describe a codec, bitrate, and container for the report."""

    parts = [codec or "unknown"]

    if bitrate is not None:
        parts.append(f"{bitrate:.0f} kbps")

    if extension:
        parts.append(f"({extension})")

    return " ".join(parts)

def _print_audio_report(
    download: DownloadInfo,
    audio_format: str,
) -> None:
    """Report source and output audio details."""

    if download.mode == "skip":
        return

    print(
        "Source: "
        + _describe_stream(
            download.source_codec,
            download.source_bitrate,
            download.source_ext,
        )
    )

    print(
        "Output: "
        + _describe_stream(
            download.output_codec,
            download.output_bitrate,
        )
    )

    print(f"Mode:   {download.mode}")

    if (
        audio_format in {"flac", "wav"}
        and download.source_codec
        and not is_lossless(download.source_codec)
    ):
        print(
            f"Warning: {audio_format.upper()} cannot restore quality "
            f"from a lossy source ({download.source_codec})."
        )

def process_track(
    track: Track,
    output_directory: Path,
    *,
    browser: BrowserProfile | None = None,
    download_lyrics: bool = True,
    download_thumbnails: bool = True,
    audio_format: str = "mp3",
    lyrics_min_confidence: str = "high",
) -> TrackResult:
    """Download and process a single track."""

    thumbnail_embedded = False
    lyrics_written = False

    # download audio
    download = download_track(
        track,
        output_directory,
        audio_format=audio_format,
        browser=browser,
    )

    audio_path = download.path

    _print_audio_report(download, audio_format)

    # write metadata
    try:
        write_metadata(
            audio_path,
            track,
        )
    except Exception as error:
        print(f"Warning: Could not write metadata: {error}")

    # download and embed thumbnail
    if download_thumbnails:
        try:
            thumbnail_data = download_thumbnail(track)

            embed_thumbnail(
                audio_path,
                thumbnail_data,
            )

            thumbnail_embedded = True
        except Exception as error:
            print(f"Warning: Could not add thumbnail: {error}")

    # search and write lyrics
    if download_lyrics:
        try:
            best = pick_best_candidate(
                search_candidates(track)
            )

            if best is None:
                print("No suitable lyrics found.")
            elif not confidence_at_least(
                best.confidence,
                lyrics_min_confidence,
            ):
                print(
                    f"Skipped lyrics: {best.confidence} confidence "
                    f"(minimum: {lyrics_min_confidence})"
                )
            else:
                lyrics_path = output_directory / (
                    f"{audio_path.stem}.lrc"
                )

                write_lyrics(
                    fetch_missing_lyrics(best.result),
                    lyrics_path,
                )

                lyrics_written = True

        except Exception as error:
            print(f"Warning: Could not get lyrics: {error}")

    return TrackResult(
        audio_path=audio_path,
        lyrics_written=lyrics_written,
        thumbnail_embedded=thumbnail_embedded,
    )

def process_playlist(
    tracks: list[Track],
    output_directory: Path,
    *,
    browser: BrowserProfile | None = None,
    download_lyrics: bool = True,
    download_thumbnails: bool = True,
    audio_format: str = "mp3",
    lyrics_min_confidence: str = "high",
) -> PlaylistResult:
    """Process all tracks in a playlist."""

    if not tracks:
        print()
        print("No tracks found in playlist.")

        return PlaylistResult(
            total=0,
            successful=0,
            failed=0,
            lyrics=0,
            thumbnails=0,
            output_directory=output_directory,
            failed_tracks=[],
            skipped=0,
        )

    playlist_name = tracks[0].playlist_name

    playlist_directory = (
        output_directory
        / build_playlist_directory_name(playlist_name)
    )

    ensure_directory(playlist_directory)

    # Only look for cookies once a track actually needs downloading.
    cookie_detection_done = browser is not None

    successful = 0
    failed = 0
    lyrics = 0
    thumbnails = 0
    skipped_count = 0
    failed_tracks = []

    for track in tracks:
        print(f"Processing: {track.title}")
        print(f"Artist:    {track.artist or 'Unknown'}")
        print(f"Duration:  {track.duration or 'Unknown'}")
        print(f"Video ID:  {track.video_id or 'Unknown'}")
        print("-" * 50)

        try:
            track_skipped = audio_file_exists(
                track,
                playlist_directory,
                audio_format,
            )

            if track_skipped:
                print(
                    f"Skipped: {track.title} "
                    f"(audio file already exists)"
                )
                skipped_count += 1
                continue

            if not cookie_detection_done:
                cookie_detection_done = True
                browser = find_browser_with_cookies()

                if browser is None:
                    print(
                        "Warning: no supported browser with usable YouTube "
                        "cookies was found. Continuing without cookies."
                    )
                else:
                    print(f"Using {browser.name} browser cookies")

            result = process_track(
                track,
                playlist_directory,
                browser=browser,
                download_lyrics=download_lyrics,
                download_thumbnails=download_thumbnails,
                audio_format=audio_format,
                lyrics_min_confidence=lyrics_min_confidence,
            )

            if result.lyrics_written:
                lyrics += 1

            if result.thumbnail_embedded:
                thumbnails += 1

            successful += 1

        except Exception as error:
            failed += 1
            failed_tracks.append(
                f"{track.playlist_index:02d} - {track.title}: {error}"
            )

            print(
                f"Failed: {track.title}: {error}"
            )

    return PlaylistResult(
        total=len(tracks),
        successful=successful,
        failed=failed,
        lyrics=lyrics,
        thumbnails=thumbnails,
        output_directory=playlist_directory,
        failed_tracks=failed_tracks,
        skipped=skipped_count,
    )
