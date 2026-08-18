"""
Purpose: Manage embedded audio metadata.

- MP3 metadata
- Opus metadata
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
from mutagen.oggopus import OggOpus

from ytmusic_dl.models import Track


def write_metadata(audio_path: Path, track: Track) -> None:
    """Write Track metadata into an audio file."""

    suffix = audio_path.suffix.lower()

    if suffix == ".mp3":
        audio = MP3(audio_path)

        if audio.tags is None:
            audio.add_tags()

        if audio.tags is None:
            raise ValueError(
                f"Unable to initialize ID3 tags: {audio_path}"
            )

        audio.tags["TIT2"] = TIT2(
            encoding=3,
            text=track.title,
        )

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

    elif suffix == ".opus":
        audio = OggOpus(audio_path)

        if audio.tags is None:
            audio.add_tags()

        if audio.tags is None:
            raise ValueError(
                f"Unable to initialize Opus tags: {audio_path}"
            )

        audio.tags["TITLE"] = track.title

        if track.artist:
            audio.tags["ARTIST"] = track.artist

        if track.album:
            audio.tags["ALBUM"] = track.album

        audio.tags["TRACKNUMBER"] = str(
            track.playlist_index
        )

        audio.save()

    else:
        raise ValueError(
            f"Unsupported audio format: {audio_path.suffix}"
        )
