"""
Purpose: Define the application's data structures

- Define proper Python objects
- Useful when conencting `yt-dlp` and LRCLIB
- All components share the same `Track` model

Responsibility: Application data structures
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol


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

    def metadata_signature(
        self,
    ) -> tuple[str, str, str, float | None]:
        """Return a key for cached lyrics lookups."""

        return (
            self.title.strip().casefold(),
            (self.artist or "").strip().casefold(),
            (self.album or "").strip().casefold(),
            self.duration,
        )

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
class LyricsCandidate:
    """A lyrics result scored against a query."""

    result: LyricsResult
    score: float
    confidence: Literal["high", "medium", "low"]
    match_reasons: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        """Return whether the result passed all rejection checks."""

        return not self.rejection_reasons

class LyricsRequest(Protocol):
    """Metadata needed to search for and score lyrics."""

    title: str
    artist: str | None
    album: str | None
    duration: float | None

@dataclass
class LyricsQuery:
    """Metadata for a lyrics-only search or download."""

    title: str
    artist: str | None = None
    album: str | None = None
    duration: float | None = None
    video_id: str | None = None
    webpage_url: str | None = None

class LyricsProvider(Protocol):
    """Interface implemented by lyrics providers."""

    name: str

    def search(self, request: LyricsRequest) -> list[LyricsResult]:
        """Search the provider for lyrics candidates."""
        ...

    def fetch_lyrics(self, result: LyricsResult) -> LyricsResult:
        """Return a candidate with its lyrics content populated."""
        ...

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
    cancelled: bool = False

@dataclass
class TrackResult:
    """Result of processing a single track."""

    audio_path: Path
    lyrics_written: bool
    thumbnail_embedded: bool
    skipped: bool = False
    lyrics_status: str = "off"
    lyrics_note: str | None = None

@dataclass
class DownloadInfo:
    """Details about a downloaded audio file."""

    path: Path
    mode: str = "transcode"
    source_codec: str | None = None
    source_bitrate: float | None = None
    source_ext: str | None = None
    output_codec: str | None = None
    output_bitrate: float | None = None

@dataclass
class DownloadProgress:
    """Progress reported while downloading or converting audio."""

    status: str = ""
    percent: float | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed: float | None = None
    eta: float | None = None
    stage: str = "download"

@dataclass(frozen=True)
class AudioFormatInfo:
    """One audio-only format reported by yt-dlp."""

    format_id: str
    extension: str
    codec: str | None = None
    bitrate: float | None = None
    sample_rate: float | None = None
    note: str | None = None
    protocol: str | None = None

@dataclass(frozen=True)
class AudioFormatReport:
    """Available audio formats and the one bestaudio selected."""

    title: str
    formats: list[AudioFormatInfo]
    selected_format_id: str | None = None
