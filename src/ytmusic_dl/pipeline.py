"""
Purpose: Coordinate the complete download process.

- Download audio
- Write metadata
- Download and embed thumbnail
- Search and write lyrics

Responsibility: Application workflow
"""

from pathlib import Path

from ytmusic_dl.downloader import download_track
from ytmusic_dl.lyrics import (
    find_best_lyrics,
    search_lyrics,
    write_lyrics,
)
from ytmusic_dl.metadata import write_metadata
from ytmusic_dl.models import Track
from ytmusic_dl.thumbnail import download_thumbnail, embed_thumbnail


def process_track(
    track: Track,
    output_directory: Path,
) -> Path:
    """Download and process a single track."""

    # download audio
    audio_path = download_track(
        track,
        output_directory
    )

    # write MP3 metadata
    write_metadata(
        audio_path,
        track,
    )

    # download and embed thumbnail
    try:
        thumbnail_data = download_thumbnail(track)

        embed_thumbnail(
            audio_path,
            thumbnail_data,
        )
    except Exception as error:
        print(f"Warning: Could not add thumbnail: {error}")

    # search and write lyrics
    try:
        lyrics_results = search_lyrics(track)

        best_lyrics = find_best_lyrics(
            track,
            lyrics_results,
        )

        if best_lyrics is not None:
            lyrics_path = output_directory / (
                f"{audio_path.stem}.lrc"
            )

            write_lyrics(
                best_lyrics,
                lyrics_path
            )

    except Exception as error:
        print(f"Warning: Could not get lyrics: {error}")

    return audio_path

def process_playlist(
    tracks: list[Track],
    output_directory: Path,
) -> list[Path]:
    """Process all tracks in a playlist."""

    audio_paths = []

    for index, track in enumerate(tracks, start=1):
        print()
        print("=" * 60)
        print(f"Track {index}/{len(tracks)}")
        print(f"Title:  {track.title}")
        print(f"Artist: {track.artist}")
        print("=" * 60)

        try:
            audio_path = process_track(
                track,
                output_directory,
            )

            audio_paths.append(audio_path)

            print(f"Completed: {audio_path}")

        except Exception as error:
            print(
                f"Failed: {track.title} - {error}"
            )

    return audio_paths
