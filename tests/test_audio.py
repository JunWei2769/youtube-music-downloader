import subprocess
from pathlib import Path

from ytmusic_dl.audio import (
    AudioStreamInfo,
    is_lossless,
    probe_audio,
)
from ytmusic_dl.downloader import (
    _codec_matches,
    _conversion_mode,
    _convert_audio,
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

def create_opus_webm(path: Path) -> None:
    """Create a tiny Opus-in-WebM fixture."""

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
            str(path),
        ],
        check=True,
        capture_output=True,
    )

def test_codec_matches() -> None:
    """Recognise matching codecs for remuxing."""

    assert _codec_matches("opus", "opus")
    assert _codec_matches("m4a", "mp4a.40.2")
    assert _codec_matches("m4a", "aac")
    assert _codec_matches("wav", "pcm_s16le")
    assert _codec_matches("flac", "flac")

    assert not _codec_matches("mp3", "opus")
    assert not _codec_matches("opus", None)

def test_conversion_mode() -> None:
    """Choose copy, remux, or transcode."""

    same = Path("song.m4a")
    assert _conversion_mode("m4a", "mp4a.40.2", same, same) == "copy"

    assert (
        _conversion_mode(
            "opus",
            "opus",
            Path("song.webm"),
            Path("song.opus"),
        )
        == "remux"
    )

    assert (
        _conversion_mode(
            "m4a",
            "mp4a.40.2",
            Path("song.webm"),
            Path("song.m4a"),
        )
        == "remux"
    )

    assert (
        _conversion_mode(
            "mp3",
            "opus",
            Path("song.webm"),
            Path("song.mp3"),
        )
        == "transcode"
    )

def test_convert_audio_remuxes_without_reencoding(
    tmp_path: Path,
) -> None:
    """Remux Opus/WebM to Opus losslessly."""

    source = tmp_path / "source.webm"
    target = tmp_path / "target.opus"

    create_opus_webm(source)

    mode = _convert_audio(
        source,
        target,
        "opus",
        "opus",
    )

    assert mode == "remux"
    assert target.exists()
    assert not source.exists()
    assert probe_audio(target).codec == "opus"

def test_convert_audio_transcodes_when_codecs_differ(
    tmp_path: Path,
) -> None:
    """Transcode Opus to MP3 when the codecs differ."""

    source = tmp_path / "source.webm"
    target = tmp_path / "target.mp3"

    create_opus_webm(source)

    mode = _convert_audio(
        source,
        target,
        "mp3",
        "opus",
    )

    assert mode == "transcode"
    assert target.exists()
    assert not source.exists()
    assert probe_audio(target).codec == "mp3"
