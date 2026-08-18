"""
Purpose: Coordinate the complete download process.

- Download audio
- Write metadata
- Download and embed thumbnail
- Search and write lyrics

Responsibility: Application workflow
"""

from pathlib import Path
from turtle import down

from ytmusic_dl.downloader import audio_file_exists, download_track
from ytmusic_dl.lyrics import (
    find_best_lyrics,
    search_lyrics,
    write_lyrics,
)
from ytmusic_dl.metadata import write_metadata
from ytmusic_dl.models import PlaylistResult, Track, TrackResult
from ytmusic_dl.thumbnail import download_thumbnail, embed_thumbnail
from ytmusic_dl.utils import build_playlist_directory_name, ensure_directory


def process_track(
    track: Track,
    output_directory: Path,
    *,
    download_lyrics: bool = True,
    download_thumbnails: bool = True,
    audio_format: str = "mp3",
) -> TrackResult:
    """Download and process a single track."""

    thumbnail_embedded = False
    lyrics_written = False

    # download audio
    audio_path = download_track(
        track,
        output_directory,
        audio_format=audio_format,
    )

    # write MP3 metadata
    write_metadata(
        audio_path,
        track,
    )

    # download and embed thumbnail
    if download_thumbnails:
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
    if download_lyrics:
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
    *,
    download_lyrics: bool = True,
    download_thumbnails: bool = True,
    audio_format: str = "mp3",
) -> PlaylistResult:
    """Process all tracks in a playlist."""

    if not tracks:
        print()
        print("No tracks found in playlist.")

        return PlaylistResult(
            total=0,
            successful=0,
            failed=0,
            lyrics=0,
            thumbnails=0,
            output_directory=output_directory,
            failed_tracks=[],
            skipped=0,
        )

    playlist_name = tracks[0].playlist_name

    playlist_directory = (
        output_directory
        / build_playlist_directory_name(playlist_name)
    )

    ensure_directory(playlist_directory)

    successful = 0
    failed = 0
    lyrics = 0
    thumbnails = 0
    skipped_count = 0
    failed_tracks = []

    for track in tracks:
        print(f"Processing: {track.title}")
        print(f"Artist:    {track.artist or 'Unknown'}")
        print(f"Duration:  {track.duration or 'Unknown'}")
        print(f"Video ID:  {track.video_id or 'Unknown'}")
        print("-" * 50)

        try:
            track_skipped = audio_file_exists(
                track,
                playlist_directory,
                audio_format,
            )

            if track_skipped:
                print(
                    f"Skipped: {track.title} "
                    f"(audio file already exists)"
                )
                skipped_count += 1
                continue

            result = process_track(
                track,
                playlist_directory,
                download_lyrics=download_lyrics,
                download_thumbnails=download_thumbnails,
                audio_format=audio_format,
            )

            if result.lyrics_written:
                lyrics += 1

            if result.thumbnail_embedded:
                thumbnails += 1

            successful += 1

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
        output_directory=playlist_directory,
        failed_tracks=failed_tracks,
        skipped=skipped_count,
    )
