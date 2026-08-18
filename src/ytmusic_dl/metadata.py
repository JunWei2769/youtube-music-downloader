"""
Purpose: Manage embedded audio metadata.

- MP3 metadata
- Title
- Artist
- Album
- Track number
- Album artist
- Metadata updates

Responsibility: Audio metadata / Mutagen
"""

from pathlib import Path

from mutagen.id3 import TALB, TIT2, TPE1, TRCK
from mutagen.mp3 import MP3

from ytmusic_dl.models import Track


def write_metadata(audio_path: Path, track: Track) -> None:
    """Write Track metadata into an MP3 file."""

    audio = MP3(audio_path)

    if audio.tags is None:
        audio.add_tags()

    if audio.tags is None:
        raise ValueError(
            f"Unable to initialize ID3 tags: {audio_path}"
        )

    audio.tags["TIT2"] = TIT2(encoding=3, text=track.title)

    if track.artist:
        audio.tags["TPE1"] = TPE1(
            encoding=3,
            text=track.artist,
        )

    if track.album:
        audio.tags["TALB"] = TALB(
            encoding=3,
            text=track.album,
        )

    audio.tags["TRCK"] = TRCK(
        encoding=3,
        text=str(track.playlist_index),
    )

    audio.save()
