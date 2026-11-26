import subprocess
from pathlib import Path

from ytmusic_dl.audio import (
    AudioStreamInfo,
    is_lossless,
    probe_audio,
)

def create_wav(path: Path) -> None:
    """Create a tiny valid WAV fixture."""

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

def test_probe_audio_wav(tmp_path: Path) -> None:
    """Report the codec and bitrate of a WAV file."""

    audio_path = tmp_path / "test.wav"
    create_wav(audio_path)

    info = probe_audio(audio_path)

    assert info.codec == "pcm_s16le"
    assert info.bitrate is not None
    assert info.bitrate > 0

def test_probe_audio_missing_file(tmp_path: Path) -> None:
    """Return empty information when ffprobe cannot read a file."""

    info = probe_audio(tmp_path / "missing.mp3")

    assert info == AudioStreamInfo()

def test_is_lossless() -> None:
    """Classify lossless and lossy codecs."""

    assert is_lossless("flac")
    assert is_lossless("alac")
    assert is_lossless("pcm_s16le")
    assert is_lossless("pcm_s24le")

    assert not is_lossless("opus")
    assert not is_lossless("aac")
    assert not is_lossless("mp3")
    assert not is_lossless(None)
