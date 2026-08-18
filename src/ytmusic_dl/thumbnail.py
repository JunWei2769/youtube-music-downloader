"""
Purpose: YouTube thumbnail handling

- Thumbnail URL generation
- Thumbnail downloading
- MP3 album artwork embedding
- Opus album artwork embedding

Responsibility: Thumbnail management
"""

import base64
from pathlib import Path

import httpx
from mutagen.flac import Picture
from mutagen.id3 import APIC, ID3
from mutagen.mp3 import MP3
from mutagen.oggopus import OggOpus

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
    """Embed thumbnail image dta into an MP3 or Opus file."""

    suffix = audio_path.suffix.lower()

    if suffix == ".mp3":
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

    elif suffix == ".opus":
        audio = OggOpus(audio_path)

        picture = Picture()
        picture.type = 3
        picture.mime = "image/jpeg"
        picture.desc = "Cover"
        picture.data = thumbnail_data

        encoded_picture = base64.b64encode(
            picture.write()
        ).decode("ascii")

        audio["metadata_block_picture"] = [
            encoded_picture
        ]

        audio.save()

    else:
        raise ValueError(
            f"Unsupported audio format: {audio_path.suffix}"
        )

def download_thumbnail(track: Track) -> bytes:
    """Download a track's YouTube thumbnail."""

    url = get_thumbnail_url(track)

    response = httpx.get(
        url,
        timeout=10.0,
    )

    response.raise_for_status()

    return response.content
