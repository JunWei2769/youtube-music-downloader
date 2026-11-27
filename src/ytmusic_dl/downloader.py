"""
Purpose: Everything related to yt-dlp

- YouTube Music URL
- Playlist extraction
- Playlist order
- Audio downloading
- Audio format
- Thumbnail downloading
- Basic metadata extraction
- Download progress
- yt-dlp errors/retries

Responsibility: YouTube Music / yt-dlp
"""

import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import cast

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadCancelled

from ytmusic_dl.audio import probe_audio
from ytmusic_dl.browser import (
    BrowserProfile,
    get_ytdlp_cookie_options,
)
from ytmusic_dl.models import (
    AudioFormatInfo,
    AudioFormatReport,
    DownloadInfo,
    DownloadProgress,
    Track,
)
from ytmusic_dl.utils import (
    LogCallback,
    build_track_filename,
    clean_artist_name,
    emit_message,
    ensure_directory,
    strip_artist_prefix,
)

ProgressCallback = Callable[[Track, DownloadProgress], None]

AUDIO_FORMATS = (
    "mp3",
    "opus",
    "flac",
    "wav",
    "m4a",
    "source",
)

# Conversion settings when the source codec does not match the target.
AUDIO_CONVERSION = {
    "mp3": ("libmp3lame", ("-q:a", "0")),
    "opus": ("libopus", ("-b:a", "160k")),
    "m4a": ("aac", ("-b:a", "256k")),
    "flac": ("flac", ()),
    "wav": ("pcm_s16le", ()),
}

AUDIO_CODECS = {
    "mp3": {"mp3"},
    "opus": {"opus"},
    "m4a": {"aac", "mp4a.40.2", "alac"},
    "flac": {"flac"},
}

AUDIO_EXTENSIONS = (
    "m4a",
    "webm",
    "opus",
    "mp3",
    "flac",
    "wav",
    "aac",
    "ogg",
    "mp4",
)

SIDECAR_EXTENSIONS = {
    ".part",
    ".ytdl",
    ".temp",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".lrc",
}


class _SilentLogger:
    """Suppress yt-dlp output during playlist extraction."""

    def debug(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass


def extract_album_name(playlist_name: str | None) -> str | None:
    """Extract an album name from an album playlist title."""

    if not playlist_name:
        return None

    prefix = "Album - "

    if playlist_name.startswith(prefix):
        album_name = playlist_name[len(prefix) :].strip()

        return album_name or None

    return None


def extract_playlist(url: str) -> list[Track]:
    """Extract track information from a YouTube Music playlist."""

    options = {
        "quiet": True,
        "no_warnings": True,
        "logger": _SilentLogger(),
        "extract_flat": True,
        "skip_download": True,
    }

    with YoutubeDL(options) as ydl:  # type: ignore[arg-type]
        info = ydl.extract_info(url, download=False)

    if info is None:
        return []

    playlist_name = cast(str | None, info.get("title"))

    entries = cast(list[dict[str, object]], info.get("entries") or [])

    tracks = []

    for index, entry in enumerate(entries, start=1):
        artist = clean_artist_name(
            cast(str | None, entry.get("artist"))
            or cast(str | None, entry.get("uploader"))
        )

        title = cast(
            str,
            entry.get("track")
            or entry.get("title", "Unknown"),
        )

        track = Track(
            playlist_index=cast(int | None, entry.get("playlist_index")) or index,
            title=strip_artist_prefix(title, artist),
            artist=artist,
            album=(
                cast(str | None, entry.get("album"))
                or extract_album_name(playlist_name)
            ),
            duration=cast(float | None, entry.get("duration")),
            video_id=cast(str | None, entry.get("id")),
            webpage_url=cast(str | None, entry.get("webpage_url")),
            playlist_name=playlist_name,
        )

        tracks.append(track)

    return tracks

def find_existing_audio(
    track: Track,
    output_directory: Path,
    audio_format: str,
) -> Path | None:
    """Return an existing output file for a track, if any."""

    filename = build_track_filename(
        playlist_index=track.playlist_index,
        title=track.title,
        artist=track.artist,
    )

    if audio_format == "source":
        for extension in AUDIO_EXTENSIONS:
            path = output_directory / f"{filename}.{extension}"

            if path.exists():
                return path

        return None

    audio_path = output_directory / f"{filename}.{audio_format}"

    return audio_path if audio_path.exists() else None

def audio_file_exists(
    track: Track,
    output_directory: Path,
    audio_format: str,
) -> bool:
    """Check whether the target audio file already exists."""

    return (
        find_existing_audio(
            track,
            output_directory,
            audio_format,
        )
        is not None
    )

def get_track_url(track: Track) -> str:
    """Return a YouTube URL for a track."""

    if track.webpage_url:
        return track.webpage_url

    if track.video_id:
        return f"https://www.youtube.com/watch?v={track.video_id}"

    raise ValueError(f"No video ID or URL available for: {track.title}")

def _codec_matches(
    audio_format: str,
    source_codec: str | None,
) -> bool:
    """Return whether the source codec already matches the output."""

    if not source_codec:
        return False

    codec = source_codec.lower()

    if audio_format == "wav":
        return codec.startswith("pcm_")

    return codec in AUDIO_CODECS.get(audio_format, set())

def _conversion_mode(
    audio_format: str,
    source_codec: str | None,
    source_path: Path,
    target_path: Path,
) -> str:
    """Return copy, remux, or transcode for an output request."""

    if source_path == target_path:
        return "copy"

    if _codec_matches(audio_format, source_codec):
        return "remux"

    return "transcode"

def _convert_audio(
    source_path: Path,
    target_path: Path,
    audio_format: str,
    source_codec: str | None,
) -> str:
    """Convert or remux audio and return the applied mode."""

    mode = _conversion_mode(
        audio_format,
        source_codec,
        source_path,
        target_path,
    )

    if mode == "copy":
        return mode

    if mode == "remux":
        codec_arguments = ("-c:a", "copy")
    else:
        codec, options = AUDIO_CONVERSION[audio_format]
        codec_arguments = ("-c:a", codec, *options)

    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source_path),
            "-vn",
            "-map",
            "0:a:0",
            *codec_arguments,
            str(target_path),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        lines = (result.stderr or "").strip().splitlines()
        message = (
            lines[-1]
            if lines
            else "ffmpeg conversion failed"
        )
        raise RuntimeError(message)

    if source_path != target_path and source_path.exists():
        source_path.unlink()

    return mode

def _find_output_files(
    output_directory: Path,
    filename: str,
) -> list[Path]:
    """Return downloaded media files for a track, newest first."""

    return sorted(
        (
            path
            for path in output_directory.glob(f"{filename}.*")
            if path.suffix.lower() not in SIDECAR_EXTENSIONS
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

def _resolve_downloaded_path(
    info: object,
    output_directory: Path,
    filename: str,
    audio_format: str,
) -> Path:
    """Resolve the actual file yt-dlp produced."""

    if isinstance(info, dict):
        requested = info.get("requested_downloads") or []

        if requested:
            filepath = requested[0].get("filepath")

            if filepath:
                path = Path(filepath)

                if path.exists():
                    return path

    if audio_format != "source":
        expected = (
            output_directory / f"{filename}.{audio_format}"
        )

        if expected.exists():
            return expected

    candidates = _find_output_files(
        output_directory,
        filename,
    )

    if candidates:
        return candidates[0]

    raise FileNotFoundError(
        f"Downloaded audio file was not found for: {filename}"
    )

def _apply_download_metadata(
    track: Track,
    info: object,
) -> None:
    """Improve track metadata using the downloaded video's info."""

    if not isinstance(info, dict):
        return

    track.artist = clean_artist_name(track.artist)

    info_artist = info.get("artist") or info.get("creator")

    if info_artist:
        track.artist = clean_artist_name(str(info_artist))
    elif not track.artist and info.get("uploader"):
        track.artist = clean_artist_name(
            str(info["uploader"])
        )

    if not track.title or track.title == "Unknown":
        title = info.get("track") or info.get("title")

        if title:
            track.title = strip_artist_prefix(
                str(title),
                track.artist,
            )

    if track.duration is None and info.get("duration") is not None:
        try:
            track.duration = float(info["duration"])
        except (TypeError, ValueError):
            pass

    if not track.album and info.get("album"):
        track.album = str(info["album"])

def _source_stream_info(
    info: object,
) -> tuple[str | None, float | None, str | None]:
    """Read source codec, bitrate, and container from yt-dlp info."""

    if not isinstance(info, dict):
        return None, None, None

    codec = info.get("acodec")
    extension = info.get("ext")

    try:
        bitrate = (
            float(info["abr"])
            if info.get("abr") is not None
            else None
        )
    except (TypeError, ValueError):
        bitrate = None

    return (
        str(codec) if codec else None,
        bitrate,
        str(extension) if extension else None,
    )

def _build_progress_hook(
    track: Track,
    progress: ProgressCallback | None,
    cancel_event: threading.Event | None,
):
    """Build a yt-dlp download progress hook."""

    def hook(data: dict) -> None:
        if (
            cancel_event is not None
            and cancel_event.is_set()
        ):
            raise DownloadCancelled(
                "Download cancelled by the user."
            )

        if progress is None:
            return

        status = str(data.get("status") or "")

        total = (
            data.get("total_bytes")
            or data.get("total_bytes_estimate")
        )

        downloaded = data.get("downloaded_bytes")

        percent = None

        if status == "finished":
            percent = 100.0
        elif total and downloaded is not None:
            percent = min(
                100.0,
                downloaded / total * 100,
            )

        progress(
            track,
            DownloadProgress(
                status=status,
                percent=percent,
                downloaded_bytes=downloaded,
                total_bytes=total,
                speed=data.get("speed"),
                eta=data.get("eta"),
                stage="download",
            ),
        )

    return hook

def download_track(
    track: Track,
    output_directory: Path,
    audio_format: str = "mp3",
    *,
    browser: BrowserProfile | None = None,
    progress: ProgressCallback | None = None,
    log: LogCallback | None = None,
    cancel_event: threading.Event | None = None,
    forceipv4: bool = True,
) -> DownloadInfo:
    """Download a single track in the requested audio format."""

    if audio_format not in AUDIO_FORMATS:
        raise ValueError(f"Unsupported audio format: {audio_format}")

    if (
        cancel_event is not None
        and cancel_event.is_set()
    ):
        raise DownloadCancelled(
            "Download cancelled by the user."
        )

    track_url = get_track_url(track)

    ensure_directory(output_directory)

    existing = find_existing_audio(
        track,
        output_directory,
        audio_format,
    )

    if existing is not None:
        emit_message(
            log,
            f"Already exists, skipping: {existing.name}",
        )
        track.audio_path = existing
        return DownloadInfo(path=existing, mode="skip")

    filename = build_track_filename(
        playlist_index=track.playlist_index,
        title=track.title,
        artist=track.artist,
    )

    cookies_from_browser = None

    if browser is not None:
        cookies_from_browser = get_ytdlp_cookie_options(browser)

    output_template = str(
        output_directory / f"{filename}.%(ext)s"
    )

    detached_ui = progress is not None or log is not None

    options = {
        "quiet": detached_ui,
        "no_warnings": detached_ui,
        "noprogress": detached_ui,
        "noplaylist": True,
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "forceipv4": forceipv4,
    }

    if progress is not None or cancel_event is not None:
        options["progress_hooks"] = [
            _build_progress_hook(
                track,
                progress,
                cancel_event,
            )
        ]
    if cookies_from_browser:
        options["cookiesfrombrowser"] = cookies_from_browser

    with YoutubeDL(options) as ydl:  # type: ignore[arg-type]
        info = ydl.extract_info(track_url, download=True)

    _apply_download_metadata(track, info)

    source_path = _resolve_downloaded_path(
        info,
        output_directory,
        filename,
        audio_format,
    )

    source_codec, source_bitrate, source_ext = (
        _source_stream_info(info)
    )

    if source_codec is None:
        source_codec = probe_audio(source_path).codec

    target_path = source_path
    mode = "copy"

    if audio_format != "source":
        target_path = (
            output_directory / f"{filename}.{audio_format}"
        )

        if target_path != source_path:
            if progress is not None:
                progress(
                    track,
                    DownloadProgress(
                        status="started",
                        stage="postprocess",
                    ),
                )

            mode = _convert_audio(
                source_path,
                target_path,
                audio_format,
                source_codec,
            )

            if progress is not None:
                progress(
                    track,
                    DownloadProgress(
                        status="finished",
                        percent=100.0,
                        stage="postprocess",
                    ),
                )

    track.audio_path = target_path
    output = probe_audio(target_path)

    return DownloadInfo(
        path=target_path,
        mode=mode,
        source_codec=source_codec,
        source_bitrate=source_bitrate,
        source_ext=source_ext,
        output_codec=output.codec,
        output_bitrate=output.bitrate,
    )

def list_audio_formats(
    url: str,
    browser: BrowserProfile | None = None,
    *,
    forceipv4: bool = True,
) -> AudioFormatReport:
    """Return available audio-only formats and the selected one."""

    options: dict[str, object] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "bestaudio/best",
        "extractor_args": {
            "youtube": {
                "formats": ["missing_pot"],
            }
        },
        "forceipv4": forceipv4,
    }

    if browser is not None:
        options["cookiesfrombrowser"] = (
            get_ytdlp_cookie_options(browser)
        )

    with YoutubeDL(options) as ydl:  # type: ignore[arg-type]
        info = ydl.extract_info(url, download=False)

    if not isinstance(info, dict):
        raise ValueError(
            "No track information found for that URL."
        )

    formats: list[AudioFormatInfo] = []

    for item in info.get("formats") or []:
        if item.get("vcodec") not in (None, "none"):
            continue

        if item.get("acodec") in (None, "none"):
            continue

        bitrate = item.get("abr")
        sample_rate = item.get("asr")

        formats.append(
            AudioFormatInfo(
                format_id=str(item.get("format_id", "")),
                extension=str(item.get("ext", "")),
                codec=item.get("acodec"),
                bitrate=(
                    float(bitrate)
                    if bitrate is not None
                    else None
                ),
                sample_rate=(
                    float(sample_rate)
                    if sample_rate is not None
                    else None
                ),
                note=item.get("format_note"),
                protocol=item.get("protocol"),
            )
        )

    formats.sort(
        key=lambda audio: audio.bitrate or 0,
        reverse=True,
    )

    selected = info.get("format_id")

    return AudioFormatReport(
        title=str(info.get("title", "")),
        formats=formats,
        selected_format_id=(
            str(selected) if selected else None
        ),
    )

def extract_single_track(url: str) -> list[Track]:
    """Extract track information from a single YouTube Music URL."""

    options = {
        "quiet": True,
        "no_warnings": True,
        "logger": _SilentLogger(),
        "skip_download": True,
    }

    with YoutubeDL(options) as ydl:  # type: ignore[arg-type]
        info = ydl.extract_info(url, download=False)

    if info is None:
        return []

    artist = clean_artist_name(
        cast(str | None, info.get("artist"))
        or cast(str | None, info.get("uploader"))
    )

    title = cast(
        str,
        info.get("track")
        or info.get("title", "Unknown"),
    )

    track = Track(
        playlist_index=1,
        title=strip_artist_prefix(title, artist),
        artist=artist,
        album=cast(str | None, info.get("album")),
        duration=cast(float | None, info.get("duration")),
        video_id=cast(str | None, info.get("id")),
        webpage_url=cast(str | None, info.get("webpage_url")),
        playlist_name=cast(str | None, info.get("title")),
    )

    return [track]
