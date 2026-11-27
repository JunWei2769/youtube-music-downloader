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
from ytmusic_dl.downloader import (
    audio_file_exists,
    download_track,
    find_existing_audio,
)
from ytmusic_dl.lyrics import (
    build_candidate,
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
    LyricsResult,
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

LyricsCache = dict[
    tuple[str, str, str, float | None],
    LyricsResult | None,
]

_NOT_CACHED = object()


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


def _write_track_lyrics(
    track: Track,
    lyrics_path: Path,
    *,
    lyrics_min_confidence: str,
    log: LogCallback | None = None,
    lyrics_cache: LyricsCache | None = None,
) -> tuple[bool, str, str | None]:
    """Select lyrics, write them, and return written/status/note."""

    cached = _NOT_CACHED

    if lyrics_cache is not None:
        cached = lyrics_cache.get(
            track.metadata_signature(),
            _NOT_CACHED,
        )

    if cached is None:
        emit_message(log, "Lyrics: not found (cached).")
        return False, "not_found", "cached: no match"

    if cached is not _NOT_CACHED:
        best = build_candidate(track, cached)
        closest = None
    else:
        candidates = search_candidates(track)
        best = pick_best_candidate(candidates)
        closest = (
            pick_closest_candidate(candidates)
            if best is None
            else None
        )

    if best is None:
        lyrics_note = None

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

        return False, "not_found", lyrics_note

    if not best.accepted:
        reason = "; ".join(best.rejection_reasons)
        emit_message(log, f"Lyrics: not found ({reason})")
        return False, "not_found", f"rejected: {reason}"

    if not confidence_at_least(
        best.confidence,
        lyrics_min_confidence,
    ):
        lyrics_note = (
            f"{best.confidence} < "
            f"{lyrics_min_confidence}"
        )
        emit_message(
            log,
            f"Skipped lyrics: {best.confidence} confidence "
            f"(minimum: {lyrics_min_confidence})",
        )
        return False, "below_threshold", lyrics_note

    write_lyrics(
        fetch_missing_lyrics(best.result),
        lyrics_path,
    )

    lyrics_note = (
        f"{best.confidence} · "
        f"{best.result.provider}"
    )
    emit_message(
        log,
        f"Lyrics: saved ({lyrics_note})",
    )

    return True, "saved", lyrics_note


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
    lyrics_cache: LyricsCache | None = None,
    forceipv4: bool = True,
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
        forceipv4=forceipv4,
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

    lyrics_path = output_directory / (
        f"{audio_path.stem}.lrc"
    )

    # search and write lyrics
    if download_lyrics:
        try:
            (
                lyrics_written,
                lyrics_status,
                lyrics_note,
            ) = _write_track_lyrics(
                track,
                lyrics_path,
                lyrics_min_confidence=(
                    lyrics_min_confidence
                ),
                log=log,
                lyrics_cache=lyrics_cache,
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
    lyrics_cache: LyricsCache | None = None,
    forceipv4: bool = True,
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

            track_options = {}

            if lyrics_cache is not None:
                track_options["lyrics_cache"] = lyrics_cache

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
                forceipv4=forceipv4,
                **track_options,
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


def process_lyrics_only(
    tracks: list[Track],
    output_directory: Path,
    *,
    audio_format: str = "mp3",
    lyrics_min_confidence: str = "high",
    overwrite: bool = False,
    log: LogCallback | None = None,
    cancel_event: threading.Event | None = None,
    on_track_complete: TrackCompleteCallback | None = None,
    lyrics_cache: LyricsCache | None = None,
) -> PlaylistResult:
    """Write missing lyrics for tracks whose audio already exists."""

    if not tracks:
        emit_message(log, "")
        emit_message(log, "No tracks found.")

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

    playlist_directory = (
        output_directory
        / build_playlist_directory_name(
            tracks[0].playlist_name
        )
    )

    ensure_directory(playlist_directory)

    successful = 0
    failed = 0
    lyrics = 0
    skipped = 0
    failed_tracks: list[str] = []
    cancelled = False
    total = len(tracks)

    def report(
        track: Track,
        result: TrackResult,
    ) -> None:
        if on_track_complete is not None:
            on_track_complete(track, result)

    for track in tracks:
        if (
            cancel_event is not None
            and cancel_event.is_set()
        ):
            cancelled = True
            emit_message(log, "Lyrics cancelled.")
            break

        emit_message(log, f"Processing lyrics: {track.title}")

        audio_path = find_existing_audio(
            track,
            playlist_directory,
            audio_format,
        )

        if audio_path is None and audio_format != "source":
            audio_path = find_existing_audio(
                track,
                playlist_directory,
                "source",
            )

        if audio_path is None:
            skipped += 1
            emit_message(
                log,
                f"Skipped lyrics: no audio file for "
                f"{track.title}",
            )
            report(
                track,
                TrackResult(
                    audio_path=playlist_directory,
                    lyrics_written=False,
                    thumbnail_embedded=False,
                    skipped=True,
                    lyrics_status="no_audio",
                    lyrics_note="no audio file",
                ),
            )
            continue

        lyrics_path = audio_path.with_suffix(".lrc")

        if lyrics_path.exists() and not overwrite:
            successful += 1
            emit_message(
                log,
                f"Lyrics already exist: {lyrics_path.name}",
            )
            report(
                track,
                TrackResult(
                    audio_path=audio_path,
                    lyrics_written=False,
                    thumbnail_embedded=False,
                    lyrics_status="exists",
                    lyrics_note="already exists",
                ),
            )
            continue

        try:
            written, status, note = _write_track_lyrics(
                track,
                lyrics_path,
                lyrics_min_confidence=(
                    lyrics_min_confidence
                ),
                log=log,
                lyrics_cache=lyrics_cache,
            )

        except Exception as error:
            failed += 1
            failed_tracks.append(
                f"{track.playlist_index:02d} - "
                f"{track.title}: {error}"
            )
            emit_message(
                log,
                f"Failed lyrics: {track.title}: {error}",
            )
            report(
                track,
                TrackResult(
                    audio_path=audio_path,
                    lyrics_written=False,
                    thumbnail_embedded=False,
                    lyrics_status="error",
                    lyrics_note=str(error),
                ),
            )
            continue

        if written:
            lyrics += 1
            successful += 1
        else:
            skipped += 1

        report(
            track,
            TrackResult(
                audio_path=audio_path,
                lyrics_written=written,
                thumbnail_embedded=False,
                lyrics_status=status,
                lyrics_note=note,
            ),
        )

    return PlaylistResult(
        total=total,
        successful=successful,
        failed=failed,
        lyrics=lyrics,
        thumbnails=0,
        output_directory=playlist_directory,
        failed_tracks=failed_tracks,
        skipped=skipped,
        cancelled=cancelled,
    )
