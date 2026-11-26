"""
Purpose: Coordinate the complete download process.

- Download audio
- Write metadata
- Download and embed thumbnail
- Search and write lyrics

Responsibility: Application workflow
"""

import threading
from collections.abc import Callable
from pathlib import Path

from yt_dlp.utils import DownloadCancelled

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
    pick_closest_candidate,
    search_candidates,
    write_lyrics,
)
from ytmusic_dl.metadata import write_metadata
from ytmusic_dl.models import (
    DownloadInfo,
    DownloadProgress,
    PlaylistResult,
    Track,
    TrackResult,
)
from ytmusic_dl.thumbnail import download_thumbnail, embed_thumbnail
from ytmusic_dl.utils import (
    LogCallback,
    build_playlist_directory_name,
    emit_message,
    ensure_directory,
)

TrackProgressCallback = Callable[
    [Track, DownloadProgress],
    None,
]

PlaylistProgressCallback = Callable[
    [Track, DownloadProgress, int, int],
    None,
]

TrackCompleteCallback = Callable[
    [Track, TrackResult],
    None,
]


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
    log: LogCallback | None = None,
) -> None:
    """Report source and output audio details."""

    if download.mode == "skip":
        return

    emit_message(
        log,
        "Source: "
        + _describe_stream(
            download.source_codec,
            download.source_bitrate,
            download.source_ext,
        ),
    )

    emit_message(
        log,
        "Output: "
        + _describe_stream(
            download.output_codec,
            download.output_bitrate,
        ),
    )

    emit_message(log, f"Mode:   {download.mode}")

    if (
        audio_format in {"flac", "wav"}
        and download.source_codec
        and not is_lossless(download.source_codec)
    ):
        emit_message(
            log,
            f"Warning: {audio_format.upper()} cannot restore quality "
            f"from a lossy source ({download.source_codec}).",
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
    progress: TrackProgressCallback | None = None,
    log: LogCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> TrackResult:
    """Download and process a single track."""

    thumbnail_embedded = False
    lyrics_written = False
    lyrics_status = "off"
    lyrics_note = None

    # download audio
    download = download_track(
        track,
        output_directory,
        audio_format=audio_format,
        browser=browser,
        progress=progress,
        log=log,
        cancel_event=cancel_event,
    )

    audio_path = download.path

    _print_audio_report(download, audio_format, log)

    # write metadata
    try:
        write_metadata(
            audio_path,
            track,
        )
    except Exception as error:
        emit_message(
            log,
            f"Warning: Could not write metadata: {error}",
        )

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
            emit_message(
                log,
                f"Warning: Could not add thumbnail: {error}",
            )

    # search and write lyrics
    if download_lyrics:
        try:
            candidates = search_candidates(track)
            best = pick_best_candidate(candidates)

            if best is None:
                closest = pick_closest_candidate(candidates)
                lyrics_status = "not_found"

                if (
                    closest is not None
                    and closest.rejection_reasons
                ):
                    reason = "; ".join(
                        closest.rejection_reasons
                    )

                    if "artist does not match" in reason:
                        provider_artist = (
                            closest.result.artist_name
                        )

                        if provider_artist:
                            reason += (
                                "; provider artist: "
                                f"{provider_artist}"
                            )

                    if "title similarity" in reason:
                        provider_title = (
                            closest.result.track_name
                        )

                        if provider_title:
                            reason += (
                                "; provider title: "
                                f"{provider_title}"
                            )

                    lyrics_note = f"rejected: {reason}"
                    emit_message(
                        log,
                        f"Lyrics: not found ({reason})",
                    )
                else:
                    emit_message(log, "Lyrics: not found.")

            elif not confidence_at_least(
                best.confidence,
                lyrics_min_confidence,
            ):
                lyrics_status = "below_threshold"
                lyrics_note = (
                    f"{best.confidence} < "
                    f"{lyrics_min_confidence}"
                )
                emit_message(
                    log,
                    f"Skipped lyrics: {best.confidence} confidence "
                    f"(minimum: {lyrics_min_confidence})",
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
                lyrics_status = "saved"
                lyrics_note = (
                    f"{best.confidence} · "
                    f"{best.result.provider}"
                )
                emit_message(
                    log,
                    f"Lyrics: saved ({lyrics_note})",
                )

        except Exception as error:
            lyrics_status = "error"
            lyrics_note = str(error)
            emit_message(
                log,
                f"Warning: Could not get lyrics: {error}",
            )

    return TrackResult(
        audio_path=audio_path,
        lyrics_written=lyrics_written,
        thumbnail_embedded=thumbnail_embedded,
        lyrics_status=lyrics_status,
        lyrics_note=lyrics_note,
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
    log: LogCallback | None = None,
    progress: PlaylistProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
    on_track_complete: TrackCompleteCallback | None = None,
) -> PlaylistResult:
    """Process all tracks in a playlist."""

    if not tracks:
        emit_message(log, "")
        emit_message(log, "No tracks found in playlist.")

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
    cancelled = False
    total = len(tracks)

    for index, track in enumerate(tracks, start=1):
        if (
            cancel_event is not None
            and cancel_event.is_set()
        ):
            cancelled = True
            emit_message(log, "Download cancelled.")
            break

        emit_message(log, f"Processing: {track.title}")
        emit_message(log, f"Artist:    {track.artist or 'Unknown'}")
        emit_message(log, f"Duration:  {track.duration or 'Unknown'}")
        emit_message(log, f"Video ID:  {track.video_id or 'Unknown'}")
        emit_message(log, "-" * 50)

        try:
            track_skipped = audio_file_exists(
                track,
                playlist_directory,
                audio_format,
            )

            if track_skipped:
                emit_message(
                    log,
                    f"Skipped: {track.title} "
                    f"(audio file already exists)",
                )
                skipped_count += 1
                continue

            if not cookie_detection_done:
                cookie_detection_done = True
                browser = find_browser_with_cookies()

                if browser is None:
                    emit_message(
                        log,
                        "Warning: no supported browser with usable "
                        "YouTube cookies was found. Continuing "
                        "without cookies.",
                    )
                else:
                    emit_message(
                        log,
                        f"Using {browser.name} browser cookies",
                    )

            track_progress = None

            if progress is not None:
                def track_progress(
                    current_track: Track,
                    update: DownloadProgress,
                    track_index: int = index,
                    track_total: int = total,
                ) -> None:
                    progress(
                        current_track,
                        update,
                        track_index,
                        track_total,
                    )

            result = process_track(
                track,
                playlist_directory,
                browser=browser,
                download_lyrics=download_lyrics,
                download_thumbnails=download_thumbnails,
                audio_format=audio_format,
                lyrics_min_confidence=lyrics_min_confidence,
                progress=track_progress,
                log=log,
                cancel_event=cancel_event,
            )

            if result.lyrics_written:
                lyrics += 1

            if result.thumbnail_embedded:
                thumbnails += 1

            successful += 1

            if on_track_complete is not None:
                on_track_complete(track, result)

        except DownloadCancelled:
            cancelled = True
            emit_message(log, "Download cancelled.")
            break

        except Exception as error:
            failed += 1
            failed_tracks.append(
                f"{track.playlist_index:02d} - {track.title}: {error}"
            )

            emit_message(
                log,
                f"Failed: {track.title}: {error}",
            )

    return PlaylistResult(
        total=total,
        successful=successful,
        failed=failed,
        lyrics=lyrics,
        thumbnails=thumbnails,
        output_directory=playlist_directory,
        failed_tracks=failed_tracks,
        skipped=skipped_count,
        cancelled=cancelled,
    )
