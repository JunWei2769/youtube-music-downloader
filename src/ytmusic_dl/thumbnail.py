"""
Purpose: YouTube thumbnail handling

- Thumbnail URL generation
- Thumbnail downloading
- MP3 album artwork embedding

Responsibility: Thumbnail management
"""

from pathlib import Path

import httpx
from mutagen.id3 import APIC, ID3
from mutagen.mp3 import MP3

from ytmusic_dl.models import Track

def get_thumbnail_url(track: Track) -> str:
    """Return the YouTube thumbnail URL for a track."""

    if not track.video_id:
        raise ValueError(
            f"No video ID available for: {track.title}"
        )

    return (
        f"https://i.ytimg.com/vi/"
        f"{track.video_id}/maxresdefault.jpg"
    )

def embed_thumbnail(
    audio_path: Path,
    thumbnail_data: bytes,
) -> None:
    """Embed thumbnail image dta into an MP3 file."""

    audio = MP3(audio_path, ID3=ID3)

    if audio.tags is None:
        audio.add_tags()

    audio.tags.add(
        APIC(
            encoding=3,
            mime="image/jpeg",
            type=3,
            desc="Cover",
            data=thumbnail_data,
        )
    )

    audio.save()

def download_thumbnail(track: Track) -> bytes:
    """Download a track's YouTube thumbnail."""

    url = get_thumbnail_url(track)

    response = httpx.get(
        url,
        timeout=10.0,
    )

    response.raise_for_status()

    return response.content
