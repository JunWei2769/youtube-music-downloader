"""
Purpose: Small reusable helper functions that don't belong specifically to downloading, lyrics, metadata, etc

- Filename sanitization
- Directory creation
- Duration formatting
- File existence

Responsibility: Generic helpers
"""

import re
from collections.abc import Callable
from pathlib import Path

LogCallback = Callable[[str], None]

def emit_message(
    log: LogCallback | None,
    message: str,
) -> None:
    """Print a message or forward it to a log sink."""

    if log is None:
        print(message)
    else:
        log(message)

def sanitize_filename(name: str) -> str:
    """Remove characters that are unsafe for filenames."""
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = name.strip().rstrip(".")
    return name or "Unknown"

def ensure_directory(path: Path) -> Path:
    """Create a directory if it does not exist and return the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path

def format_duration(seconds: float | None) -> str:
    """Format a duration in seconds as MM:SS or HH:MM:SS."""
    if seconds is None:
        return "Unknown"

    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"

    return f"{minutes}:{seconds:02d}"

def clean_artist_name(
    artist: str | None,
) -> str | None:
    """Remove channel suffixes from an artist name.

    YouTube uploaders are often channels such as "ArtistVEVO",
    "Artist - Topic", or "ArtistOfficial". They are not the artist
    name and must not be used for lyrics lookups.
    """

    if not artist:
        return artist

    name = artist.strip()

    name = re.sub(
        r"\s*-\s*topic$",
        "",
        name,
        flags=re.IGNORECASE,
    )

    name = re.sub(
        r"\s*(?:vevo|official)$",
        "",
        name,
        flags=re.IGNORECASE,
    )

    name = re.sub(r"\s+", " ", name).strip()

    return name or artist

def strip_artist_prefix(
    title: str,
    artist: str | None,
) -> str:
    """Remove a leading "Artist - " when it repeats the artist."""

    if not artist:
        return title

    artist = artist.strip()

    if not artist:
        return title

    pattern = re.compile(
        rf"^\s*{re.escape(artist)}\s*[-–—]\s*",
        re.IGNORECASE,
    )

    stripped = pattern.sub("", title, count=1).strip()

    return stripped or title

def build_track_filename(
    playlist_index: int,
    title: str,
    artist: str | None = None,
) -> str:
    """Build a filename that preserves playlist order."""

    safe_title = sanitize_filename(title)

    if artist:
        safe_artist = sanitize_filename(artist)
        filename = f"{playlist_index:02d} - {safe_artist} - {safe_title}"
    else:
        filename = f"{playlist_index:02d} - {safe_title}"

    return filename

def build_lyrics_filename(
    title: str,
    artist: str | None = None,
) -> str:
    """Build a filename for a standalone lyrics file."""

    safe_title = sanitize_filename(title)

    if artist:
        safe_artist = sanitize_filename(artist)
        return f"{safe_artist} - {safe_title}"

    return safe_title

def build_playlist_directory_name(name: str | None) -> str:
    """Build a safe directory name for a playlist."""

    if not name:
        return "Unknown Playlist"

    name = name.strip()

    invalid_characters = '<>:"/\\|?*'

    for character in invalid_characters:
        name = name.replace(character, "_")

    return name or "Unknown Playlist"
