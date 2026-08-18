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

from ytmusic_dl.metadata import write_metadata
from ytmusic_dl.models import Track
from ytmusic_dl.utils import build_track_filename, ensure_directory


def extract_playlist(url: str) -> list[Track]:
    """Extract track information from a YouTube Music playlist."""

    options = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }

    with YoutubeDL(options) as ydl: # type: ignore[arg-type]
        info = ydl.extract_info(url, download=False)

    if info is None:
        return []

    entries = cast(list[dict[str, object]], info.get("entries") or [])

    tracks = []

    for index, entry in enumerate(entries, start=1):
        track = Track(
            playlist_index=cast(int | None, entry.get("playlist_index")) or index,
            title=cast(str, entry.get("title", "Unknown")),
            artist=cast(str | None, entry.get("artist"))
            or cast(str | None, entry.get("uploader")),
            album=cast(str | None, entry.get("album")),
            duration=cast(float | None, entry.get("duration")),
            video_id=cast(str | None, entry.get("id")),
            webpage_url=cast(str | None, entry.get("webpage_url")),
        )

        tracks.append(track)

    return tracks


def get_track_url(track:Track) -> str:
    """Return a YouTube URL for a track."""

    if track.webpage_url:
        return track.webpage_url

    if track.video_id:
        return f"https://www.youtube.com/watch?v={track.video_id}"

    raise ValueError(f"No video ID or URL available for: {track.title}")

def download_track(track: Track, output_directory: Path) -> Path:
    """Download a single track as an MP3 file."""

    track_url = get_track_url(track)

    ensure_directory(output_directory)

    filename = build_track_filename(
        playlist_index=track.playlist_index,
        title=track.title,
        artist=track.artist,
    )

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

    with YoutubeDL(options) as ydl: # type: ignore[arg-type]
        ydl.download([track_url])

    audio_path = output_directory / f"{filename}.mp3"

    if not audio_path.exists():
        raise FileNotFoundError(
            f"Download file was not found: {audio_path}"
        )

    write_metadata(audio_path, track)

    track.audio_path = audio_path

    return audio_path
