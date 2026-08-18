import subprocess
from pathlib import Path

import pytest
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from mutagen.oggopus import OggOpus

from ytmusic_dl.metadata import write_metadata
from ytmusic_dl.models import Track


def create_audio_fixture(
    path: Path,
    codec: str,
) -> None:
    """Create a tiny valid audio file for testing"""

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-t",
            "0.1",
            "-c:a",
            codec,
            str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

def make_track() -> Track:
    return Track(
        playlist_index=3,
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        duration=200,
        video_id="test123",
        webpage_url="https://youtube.com/watch?v=test123",
        playlist_name="Test Playlist",
    )


def test_write_metadata_mp3(tmp_path: Path) -> None:
    """Test writing metadata to an MP3 file."""

    audio_path = tmp_path / "test.mp3"

    create_audio_fixture(
        audio_path,
        "libmp3lame",
    )

    track = make_track()

    write_metadata(audio_path, track)

    audio = MP3(audio_path)

    assert audio.tags is not None

    assert audio.tags["TIT2"].text == ["Test Song"]
    assert audio.tags["TPE1"].text == ["Test Artist"]
    assert audio.tags["TALB"].text == ["Test Album"]
    assert audio.tags["TRCK"].text == ["3"]


def test_write_metadata_opus(tmp_path: Path) -> None:
    """Test writing metadata to an Opus file."""

    audio_path = tmp_path / "test.opus"

    create_audio_fixture(
        audio_path,
        "libopus",
    )

    track = make_track()

    write_metadata(audio_path, track)

    audio = OggOpus(audio_path)

    assert audio.tags is not None

    assert audio.tags["TITLE"] == ["Test Song"]
    assert audio.tags["ARTIST"] == ["Test Artist"]
    assert audio.tags["ALBUM"] == ["Test Album"]
    assert audio.tags["TRACKNUMBER"] == ["3"]


def test_write_metadata_unsupported_format(tmp_path: Path) -> None:
    """Test rejection of unsupported audio formats."""

    audio_path = tmp_path / "test.flac"

    track = make_track()

    with pytest.raises(
        ValueError,
        match="Unsupported audio format",
    ):
        write_metadata(audio_path, track)
