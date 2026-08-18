"""
Purpose: Everything related to lyrics.

- LRCLIB API
- Lyrics searching
- Synced lyrics
- Plain lyrics
- Lyrics result parsing

Responsibility: Lyrics / LRCLIB
"""

from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import httpx

from ytmusic_dl.models import LyricsResult, Track

LRCLIB_API_URL = "https://lrclib.net/api/search"

USER_AGENT = "youtube-music-downloader/0.1.0"

def _similarity(first: str, second: str) -> float:
    """Return a similarity score between two strings."""

    return SequenceMatcher(
        None,
        first.casefold(),
        second.casefold(),
    ).ratio()

def _duration_score(
    track_duration: float | None,
    lyrics_duration: float | None,
) -> float:
    """Return a score based on duration difference."""

    if track_duration is None or lyrics_duration is None:
        return 0.0

    difference = abs(track_duration - lyrics_duration)

    if difference <= 2:
        return 1.0

    if difference <= 5:
        return 0.8

    if difference <= 10:
        return 0.5

    return 0.0

def find_best_lyrics(
    track: Track,
    results: list[LyricsResult],
) -> LyricsResult | None:
    """Find the best LRCLIB result for a track."""

    if not results:
        return None

    best_result = None
    best_score = 0.0

    for result in results:
        title_score = _similarity(
            track.title,
            result.track_name,
        )

        artist_score = _similarity(
            track.artist or "",
            result.artist_name,
        )

        duration_score = _duration_score(
            track.duration,
            result.duration,
        )

        score = (
            title_score * 0.60
            + artist_score * 0.20
            + duration_score * 0.20
        )

        if score > best_score:
            best_score = score
            best_result = result

    return best_result

def search_lyrics(track: Track) -> list[LyricsResult]:
    """Search LRCLIB for lyrics matching a track."""

    params = {
        "track_name": track.title,
    }

    headers = {
        "User-Agent": USER_AGENT,
    }

    response = httpx.get(
        LRCLIB_API_URL,
        params=params,
        headers=headers,
        timeout=10.0,
    )

    response.raise_for_status()

    data: list[dict[str, Any]] = response.json()

    results = []

    for item in data:
        result = LyricsResult(
            lrclib_id=int(item["id"]),
            track_name=str(item.get("trackName", "")),
            artist_name=str(item.get("artistName", "")),
            album_name=item.get("albumName"),
            duration=(
                float(item["duration"])
                if item.get("duration") is not None
                else None
            ),
            instrumental=bool(item.get("instrumental", False)),
            synced_lyrics=item.get("syncedLyrics"),
            plain_lyrics=item.get("plainLyrics"),
        )

        results.append(result)

    return results

def write_lyrics(
    lyrics: LyricsResult,
    output_path: Path,
) -> Path:
    """Write lyrics to a file."""

    if lyrics.synced_lyrics:
        content = lyrics.synced_lyrics
    elif lyrics.plain_lyrics:
        content = lyrics.plain_lyrics
    else:
        raise ValueError(
            f"No lyrics available for: {lyrics.track_name}"
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        content,
        encoding="utf-8",
    )

    return output_path
