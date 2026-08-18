from pathlib import Path

from ytmusic_dl.downloader import download_track, extract_playlist

url = "https://music.youtube.com/playlist?list=OLAK5uy_ljsSnAHNCCZ3tiwKpqRtxdTsR_elPNTdQ&si=0rpDxvQ2wsOWbIdR"

tracks = extract_playlist(url)

if not tracks:
    raise RuntimeError("No tracks found.")

track = tracks[0]

print(f"Downloading: {track.title}")
print(f"Artist:      {track.artist}")
print(f"Duration:    {track.duration}")
print(f"Video ID:    {track.video_id}")

output_directory = Path("downloads/test")

audio_path = download_track(track, output_directory)

print(f"\nDownloaded successfully:")
print(audio_path)
