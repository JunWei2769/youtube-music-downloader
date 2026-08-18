from pathlib import Path

from ytmusic_dl.downloader import extract_playlist
from ytmusic_dl.pipeline import process_track

PLAYLIST_URL = "https://music.youtube.com/playlist?list=OLAK5uy_ljsSnAHNCCZ3tiwKpqRtxdTsR_elPNTdQ&si=0rpDxvQ2wsOWbIdR"

OUTPUT_DIRECTORY = Path("downloads/pipeline-test")

tracks = extract_playlist(PLAYLIST_URL)

if not tracks:
    raise RuntimeError("No tracks found")

track = tracks[0]

print(f"Processing: {track.title}")
print(f"Artist:    {track.artist}")
print(f"Duration:  {track.duration}")
print(f"Video ID:  {track.video_id}")
print("-" * 50)

audio_path = process_track(
    track,
    OUTPUT_DIRECTORY,
)

print()
print("Track processed successfully")
print(audio_path)
