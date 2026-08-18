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
from ytmusic_dl.models import PlaylistResult, Track, TrackResult
from ytmusic_dl.thumbnail import download_thumbnail, embed_thumbnail


def process_track(
    track: Track,
    output_directory: Path,
) -> TrackResult:
    """Download and process a single track."""

    thumbnail_embedded = False
    lyrics_written = False

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

        thumbnail_embedded = True
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

            lyrics_written = True

    except Exception as error:
        print(f"Warning: Could not get lyrics: {error}")

    return TrackResult(
        audio_path=audio_path,
        lyrics_written=lyrics_written,
        thumbnail_embedded=thumbnail_embedded,
    )

def process_playlist(
    tracks: list[Track],
    output_directory: Path,
) -> PlaylistResult:
    """Process all tracks in a playlist."""

    successful = 0
    failed = 0
    lyrics = 0
    thumbnails = 0
    failed_tracks = []

    for track in tracks:
        print(f"Processing: {track.title}")
        print(f"Artist:    {track.artist or 'Unknown'}")
        print(f"Duration:  {track.duration or 'Unknown'}")
        print(f"Video ID:  {track.video_id or 'Unknown'}")
        print("-" * 50)

        try:
            result = process_track(
                track,
                output_directory,
            )

            successful += 1

            if result.lyrics_written:
                lyrics += 1

            if result.thumbnail_embedded:
                thumbnails += 1

        except Exception as error:
            failed += 1
            failed_tracks.append(
                f"{track.playlist_index:02d} - {track.title}: {error}"
            )

            print(
                f"Failed: {track.title}: {error}"
            )

    return PlaylistResult(
            total=len(tracks),
            successful=successful,
            failed=failed,
            lyrics=lyrics,
            thumbnails=thumbnails,
            output_directory=output_directory,
            failed_tracks=failed_tracks,
        )
