from ytmusic_dl.downloader import extract_playlist

url = "https://music.youtube.com/playlist?list=OLAK5uy_ljsSnAHNCCZ3tiwKpqRtxdTsR_elPNTdQ&si=0rpDxvQ2wsOWbIdR"

tracks = extract_playlist(url)

print(f"\nFound {len(tracks)} tracks:\n")

for track in tracks:
    print(f"Index:    {track.playlist_index}")
    print(f"Title:    {track.title}")
    print(f"Artist:   {track.artist}")
    print(f"Album:    {track.album}")
    print(f"Duration: {track.duration}")
    print(f"Video ID:  {track.video_id}")
    print(f"URL:      {track.webpage_url}")
    print("-" * 50)
