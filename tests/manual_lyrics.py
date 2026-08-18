from pathlib import Path

from ytmusic_dl.lyrics import find_best_lyrics, search_lyrics, write_lyrics
from ytmusic_dl.models import Track

track = Track(
    playlist_index=1,
    title="還有什麼更好的",
    artist="单依纯Official",
    album=None,
    duration=227,
    video_id="yZuPNTlmtTA",
)

results = search_lyrics(track)

best = find_best_lyrics(track, results)

if best is not None:
    lyrics_path = write_lyrics(
        best,
        Path("downloads/test/01 - 還有什麼更好的.lrc"),
    )

    print(f"Lyrics written to: {lyrics_path}")

print("\nBest match:")

if best is None:
    print("No suitable lyrics found.")
else:
    print("Title:    ", best.track_name)
    print("Artist:   ", best.artist_name)
    print("Album:    ", best.album_name)
    print("Duration: ", best.duration)
    print("Synced:   ", bool(best.synced_lyrics))
    print("Plain:    ", bool(best.plain_lyrics))
