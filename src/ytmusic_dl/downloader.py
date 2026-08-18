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

from ytmusic_dl.models import Track
from ytmusic_dl.utils import build_track_filename, ensure_directory


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

def audio_file_exists(
    track: Track,
    output_directory: Path,
    audio_format: str,
) -> bool:
    """Check whether the target audio file already exists."""

    filename = build_track_filename(
        playlist_index=track.playlist_index,
        title=track.title,
        artist=track.artist,
    )

    audio_path = output_directory / f"{filename}.{audio_format}"

    return audio_path.exists()


def get_track_url(track: Track) -> str:
    """Return a YouTube URL for a track."""

    if track.webpage_url:
        return track.webpage_url

    if track.video_id:
        return f"https://www.youtube.com/watch?v={track.video_id}"

    raise ValueError(f"No video ID or URL available for: {track.title}")


def download_track(
    track: Track,
    output_directory: Path,
    audio_format: str = "mp3",
) -> Path:
    """Download a single track in the requested audio format."""

    if audio_format not in {"mp3", "opus"}:
        raise ValueError(f"Unsupported audio format: {audio_format}")

    track_url = get_track_url(track)

    ensure_directory(output_directory)

    filename = build_track_filename(
        playlist_index=track.playlist_index,
        title=track.title,
        artist=track.artist,
    )

    audio_path = output_directory / f"{filename}.{audio_format}"

    if audio_path.exists():
        print(f"Already exists, skipping: {audio_path.name}")
        track.audio_path = audio_path
        return audio_path

    if audio_format == "mp3":
        output_template = str(output_directory / f"{filename}.%(ext)s")

        options = {
            "quiet": False,
            "noplaylist": True,
            "format": "bestaudio/best",
            "outtmpl": output_template,
            # Match the working yt-dlp CLI configuration
            "cookiesfrombrowser": ("vivaldi",),
            "forceipv4": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",
                }
            ],
        }

        expected_path = output_directory / f"{filename}.mp3"

    else:
        output_template = str(output_directory / f"{filename}.%(ext)s")

        options = {
            "quiet": False,
            "noplaylist": True,
            "format": "bestaudio[acodec=opus]",
            "outtmpl": output_template,
            "cookiesfrombrowser": ("vivaldi",),
            "forceipv4": True,
            "postprocessors": [
                {
                    "key": "FFmpegVideoRemuxer",
                    "preferedformat": "opus",
                }
            ],
        }

        expected_path = output_directory / f"{filename}.opus"

    with YoutubeDL(options) as ydl:  # type: ignore[arg-type]
        ydl.download([track_url])

    if not expected_path.exists():
        raise FileNotFoundError(f"Download file was not found: {expected_path}")

    track.audio_path = expected_path

    return expected_path
