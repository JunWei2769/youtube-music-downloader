from pathlib import Path

from ytmusic_dl.downloader import extract_playlist
from ytmusic_dl.pipeline import process_playlist

PLAYLIST_URL = "https://music.youtube.com/playlist?list=OLAK5uy_ljsSnAHNCCZ3tiwKpqRtxdTsR_elPNTdQ&si=0rpDxvQ2wsOWbIdR"

OUTPUT_DIRECTORY = Path("downloads/playlist-test")

tracks = extract_playlist(PLAYLIST_URL)

print(f"Found {len(tracks)} tracks")

result = process_playlist(
    tracks,
    OUTPUT_DIRECTORY,
)

print()
print("=" * 60)
print("PLAYLIST COMPLETE")
print("=" * 60)
print(f"Successful downloads: {result.successful}")
