import base64
from pathlib import Path

import pytest
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from mutagen.oggopus import OggOpus
from mutagen.wave import WAVE

from ytmusic_dl.thumbnail import embed_thumbnail


def create_test_mp3(path: Path) -> None:
    """Create a minimal valid MP3 fixture."""

    import subprocess

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-t",
            "0.1",
            "-c:a",
            "libmp3lame",
            str(path),
        ],
        check=True,
        capture_output=True,
    )

def create_test_flac(path: Path) -> None:
    """Create a minimal valid FLAC fixture."""

    import subprocess

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
            "flac",
            str(path),
        ],
        check=True,
        capture_output=True,
    )

def create_test_wav(path: Path) -> None:
    """Create a minimal valid WAV fixture."""

    import subprocess

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-t",
            "0.1",
            "-c:a",
            "pcm_s16le",
            str(path),
        ],
        check=True,
        capture_output=True,
    )

def test_embed_thumbnail_mp3(tmp_path: Path) -> None:
    """Test embedding artwork into MP3."""

    audio_path = tmp_path / "test.mp3"

    create_test_mp3(audio_path)

    thumbnail_data = b"fake-jpeg-data"

    embed_thumbnail(
        audio_path,
        thumbnail_data,
    )

    audio = MP3(audio_path, ID3=ID3)

    assert audio.tags is not None

    covers = audio.tags.getall("APIC")

    assert len(covers) == 1
    assert covers[0].mime == "image/jpeg"
    assert covers[0].type == 3
    assert covers[0].data == thumbnail_data


def test_embed_thumbnail_opus(tmp_path: Path) -> None:
    """Test embedding artwork into Opus."""

    audio_path = tmp_path / "test.opus"

    # A real Ogg Opus file is required.
    # Generate a tiny valid Opus file using ffmpeg.
    import subprocess

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
            "libopus",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
    )

    thumbnail_data = b"fake-jpeg-data"

    embed_thumbnail(
        audio_path,
        thumbnail_data,
    )

    audio = OggOpus(audio_path)

    assert "metadata_block_picture" in audio

    assert len(
        audio["metadata_block_picture"]
    ) == 1

def test_embed_thumbnail_flac(tmp_path: Path) -> None:
    """Test embedding artwork into FLAC."""

    audio_path = tmp_path / "test.flac"

    create_test_flac(audio_path)

    thumbnail_data = b"fake-jpeg-data"

    embed_thumbnail(
        audio_path,
        thumbnail_data,
    )

    audio = FLAC(audio_path)

    assert "metadata_block_picture" in audio

    pictures = audio["metadata_block_picture"]

    assert len(pictures) == 1

    picture = Picture(
        base64.b64decode(pictures[0])
    )

    assert picture.mime == "image/jpeg"
    assert picture.type == 3
    assert picture.desc == "Cover"
    assert picture.data == thumbnail_data

def test_embed_thumbnail_wav(tmp_path: Path) -> None:
    """Test embedding artwork into WAV."""

    audio_path = tmp_path / "test.wav"

    create_test_wav(audio_path)

    thumbnail_data = b"fake-jpeg-data"

    embed_thumbnail(
        audio_path,
        thumbnail_data,
    )

    audio = WAVE(audio_path)

    assert audio.tags is not None

    covers = audio.tags.getall("APIC")

    assert len(covers) == 1
    assert covers[0].mime == "image/jpeg"
    assert covers[0].type == 3
    assert covers[0].data == thumbnail_data

def test_embed_thumbnail_unsupported_format(
    tmp_path: Path,
) -> None:
    """Test rejecting unsupported audio formats."""

    audio_path = tmp_path / "test.aac"

    audio_path.touch()

    with pytest.raises(
        ValueError,
        match="Unsupported audio format",
    ):
        embed_thumbnail(
            audio_path,
            b"fake-jpeg-data",
        )
