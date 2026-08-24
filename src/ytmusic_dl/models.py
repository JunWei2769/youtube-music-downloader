"""
Purpose: Define the application's data structures

- Define proper Python objects
- Useful when conencting `yt-dlp` and LRCLIB
- All components share the same `Track` model

Responsibility: Application data structures
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Track:
    """Represents a track from a YouTube Music playlist."""

    playlist_index: int
    title: str
    artist: str | None = None
    album: str | None = None
    duration: float | None = None
    video_id: str | None = None
    webpage_url: str | None = None
    playlist_name: str | None = None
    audio_path: Path | None = None
    lyrics_path: Path | None = None

@dataclass
class Lyrics:
    """Represents lyrics retrieved from a lyrics provider."""

    plain: str | None = None
    synced: str | None = None

@dataclass
class LyricsResult:
    """Lyrics information returned by a lyrics provider."""

    provider: str
    provider_id: str
    track_name: str
    artist_name: str
    album_name: str | None
    duration: float | None
    instrumental: bool
    synced_lyrics: str | None
    plain_lyrics: str | None

@dataclass
class PlaylistResult:
    """Result of processing a playlist."""

    total: int
    successful: int
    failed: int
    lyrics: int
    thumbnails: int
    output_directory: Path
    failed_tracks: list[str]
    skipped: int

@dataclass
class TrackResult:
    """Result of processing a single track."""

    audio_path: Path
    lyrics_written: bool
    thumbnail_embedded: bool
    skipped: bool = False
