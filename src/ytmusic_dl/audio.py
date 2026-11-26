"""
Purpose: Inspect audio streams with ffprobe.

- Codec and bitrate reporting
- Lossless-source detection

Responsibility: Audio inspection
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

LOSSLESS_CODECS = {
    "alac",
    "flac",
    "wavpack",
    "ape",
    "tta",
}

@dataclass(frozen=True)
class AudioStreamInfo:
    """Codec and bitrate of an audio stream."""

    codec: str | None = None
    bitrate: float | None = None

def probe_audio(path: Path) -> AudioStreamInfo:
    """Return the codec and bitrate reported by ffprobe."""

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name,bit_rate",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            check=True,
            text=True,
            timeout=30,
        )

        data = json.loads(result.stdout)

    except (
        OSError,
        subprocess.SubprocessError,
        ValueError,
    ):
        return AudioStreamInfo()

    streams = data.get("streams") or []

    if not streams:
        return AudioStreamInfo()

    stream = streams[0]

    bit_rate = stream.get("bit_rate")

    try:
        bitrate = float(bit_rate) / 1000 if bit_rate else None
    except (TypeError, ValueError):
        bitrate = None

    return AudioStreamInfo(
        codec=stream.get("codec_name"),
        bitrate=bitrate,
    )

def is_lossless(codec: str | None) -> bool:
    """Return whether a codec preserves lossless audio."""

    if not codec:
        return False

    if codec.startswith("pcm_"):
        return True

    return codec.lower() in LOSSLESS_CODECS
