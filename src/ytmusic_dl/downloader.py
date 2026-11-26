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

from pathlib import Path
from typing import cast

from yt_dlp import YoutubeDL

from ytmusic_dl.audio import probe_audio
from ytmusic_dl.browser import (
    BrowserProfile,
    get_ytdlp_cookie_options,
)
from ytmusic_dl.models import DownloadInfo, Track
from ytmusic_dl.utils import build_track_filename, ensure_directory

AUDIO_FORMATS = (
    "mp3",
    "opus",
    "flac",
    "wav",
    "m4a",
    "source",
)

# Explicit conversion targets for lossy formats.
AUDIO_QUALITY = {
    "mp3": "0",
    "opus": "160",
    "m4a": "256",
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
        track = Track(
            playlist_index=cast(int | None, entry.get("playlist_index")) or index,
            title=cast(str, entry.get("title", "Unknown")),
            artist=(
                cast(str | None, entry.get("artist"))
                or cast(str | None, entry.get("uploader"))
            ),
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

def _build_postprocessors(
    audio_format: str,
) -> list[dict[str, str]]:
    """Build the FFmpeg postprocessors for an output format."""

    if audio_format == "source":
        return []

    postprocessor = {
        "key": "FFmpegExtractAudio",
        "preferredcodec": audio_format,
    }

    quality = AUDIO_QUALITY.get(audio_format)

    if quality:
        postprocessor["preferredquality"] = quality

    return [postprocessor]

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

def download_track(
    track: Track,
    output_directory: Path,
    audio_format: str = "mp3",
    *,
    browser: BrowserProfile | None = None,
) -> DownloadInfo:
    """Download a single track in the requested audio format."""

    if audio_format not in AUDIO_FORMATS:
        raise ValueError(f"Unsupported audio format: {audio_format}")

    track_url = get_track_url(track)

    ensure_directory(output_directory)

    existing = find_existing_audio(
        track,
        output_directory,
        audio_format,
    )

    if existing is not None:
        print(f"Already exists, skipping: {existing.name}")
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

    options = {
        "quiet": False,
        "noplaylist": True,
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "forceipv4": True,
    }

    postprocessors = _build_postprocessors(audio_format)

    if postprocessors:
        options["postprocessors"] = postprocessors

    if cookies_from_browser:
        options["cookiesfrombrowser"] = cookies_from_browser

    with YoutubeDL(options) as ydl:  # type: ignore[arg-type]
        info = ydl.extract_info(track_url, download=True)

    audio_path = _resolve_downloaded_path(
        info,
        output_directory,
        filename,
        audio_format,
    )

    track.audio_path = audio_path

    source_codec, source_bitrate, source_ext = (
        _source_stream_info(info)
    )

    output = probe_audio(audio_path)

    return DownloadInfo(
        path=audio_path,
        mode=(
            "copy" if audio_format == "source" else "transcode"
        ),
        source_codec=source_codec,
        source_bitrate=source_bitrate,
        source_ext=source_ext,
        output_codec=output.codec,
        output_bitrate=output.bitrate,
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

    track = Track(
        playlist_index=1,
        title=cast(str, info.get("title", "Unknown")),
        artist=(
            cast(str | None, info.get("artist"))
            or cast(str | None, info.get("uploader"))
        ),
        album=cast(str | None, info.get("album")),
        duration=cast(float | None, info.get("duration")),
        video_id=cast(str | None, info.get("id")),
        webpage_url=cast(str | None, info.get("webpage_url")),
        playlist_name=cast(str | None, info.get("title")),
    )

    return [track]
