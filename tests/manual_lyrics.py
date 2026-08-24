from ytmusic_dl.lyrics import get_lyrics
from ytmusic_dl.models import Track


tracks = [
    Track(
        playlist_index=1,
        title="变色龙 (Chameleon)",
        artist="裘德",
        duration=None,
    ),
    Track(
        playlist_index=2,
        title="空耳+还你茉莉（Live）",
        artist="单依纯",
        duration=None,
    ),
]


for track in tracks:
    print("=" * 80)
    print(f"Title:  {track.title}")
    print(f"Artist: {track.artist}")
    print("=" * 80)

    result = get_lyrics(track)

    if result is None:
        print("Result: NOT FOUND")
        print()
        continue

    print("Result:")
    print(f"  Provider: {result.provider}")
    print(f"  ID:       {result.provider_id}")
    print(f"  Title:    {result.track_name}")
    print(f"  Artist:   {result.artist_name}")
    print(f"  Album:    {result.album_name}")
    print(f"  Duration: {result.duration}")
    print(f"  Synced:   {bool(result.synced_lyrics)}")
    print(f"  Plain:    {bool(result.plain_lyrics)}")

    if result.synced_lyrics:
        print("\nLyrics preview:")
        print("\n".join(result.synced_lyrics.splitlines()[:20]))

    print()
