"""
Purpose: Small reusable helper functions that don't belong specifically to downloading, lyrics, metadata, etc

- Filename sanitization
- Directory creation
- Duration formatting
- File existence

Responsibility: Generic helpers
"""

import re
from pathlib import Path


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
