from pathlib import Path

from mutagen.id3 import ID3

from ytmusic_dl.downloader import extract_playlist
from ytmusic_dl.thumbnail import (
    download_thumbnail,
    embed_thumbnail,
)

playlist_url = "https://music.youtube.com/playlist?list=OLAK5uy_ljsSnAHNCCZ3tiwKpqRtxdTsR_elPNTdQ&si=0rpDxvQ2wsOWbIdR"

tracks = extract_playlist(playlist_url)
track = tracks[0]

audio_path = Path(
    "downloads/test/01 - 单依纯Official - 還有什麼更好的.mp3"
)

thumbnail = download_thumbnail(track)

print(f"Downloaded thumbnail: {len(thumbnail)} bytes")

embed_thumbnail(
    audio_path,
    thumbnail,
)

print(f"Thumbnail embedded: {audio_path}")

tags = ID3(audio_path)

apic_tags = tags.getall("APIC")

print(f"Cover images: {len(apic_tags)}")
