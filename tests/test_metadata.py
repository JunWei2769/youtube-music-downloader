from pathlib import Path

from mutagen.mp3 import MP3

from ytmusic_dl.metadata import write_metadata
from ytmusic_dl.models import Track

audio_path = Path(
    "downloads/test/01 - 单依纯Official - 還有什麼更好的.mp3"
)

track = Track(
    playlist_index=1,
    title="還有什麼更好的",
    artist="單依纯Official",
    album=None,
    duration=227,
    video_id="yZuPNTlmtTA",
)

write_metadata(audio_path, track)

audio = MP3(audio_path)

print("Metadata written successfully:")
print("Title: ", audio.tags.get("TIT2"))
print("Artist:", audio.tags.get("TPE1"))
print("Album: ", audio.tags.get("TALB"))
print("Track: ", audio.tags.get("TRCK"))
