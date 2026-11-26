"""Scoring helpers that decide how well a lyrics result matches a track."""

import re
from typing import Literal

from ytmusic_dl.lyrics.normalize import (
    _build_title_variants,
    _normalize_text,
    _similarity,
)
from ytmusic_dl.models import (
    LyricsRequest,
    LyricsResult,
)

MIN_MATCH_SCORE = 0.75
MAX_DURATION_DIFFERENCE = 10.0

HIGH_CONFIDENCE_SCORE = 0.90
MEDIUM_CONFIDENCE_SCORE = 0.75

def confidence_for_score(
    score: float,
) -> Literal["high", "medium", "low"]:
    """Map a match score to a confidence label."""

    if score >= HIGH_CONFIDENCE_SCORE:
        return "high"

    if score >= MEDIUM_CONFIDENCE_SCORE:
        return "medium"

    return "low"

def _artist_matches(
    track_artist: str | None,
    lyrics_artist: str | None,
) -> bool:
    """Return whether two artist names refer to the same artist."""
    if not track_artist or not lyrics_artist:
        return False

    def normalize_artists(value: str) -> set[str]:
        value = _normalize_text(value)

        # YouTube Topic channels are not part of the artist name.
        value = re.sub(
            r"\s*-\s*topic$",
            "",
            value,
            flags=re.IGNORECASE,
        )

        parts = re.split(
            r",|&|/|／|、|_aka_|feat\.?|ft\.?",
            value,
        )

        return {
            part.strip()
            for part in parts
            if part.strip()
        }

    def artist_components(value: str) -> set[str]:
        components = {value}

        # Extract Chinese name components.
        chinese_parts = re.findall(
            r"[\u3400-\u4dbf\u4e00-\u9fff]+",
            value,
        )

        components.update(chinese_parts)

        # Extract the first Latin name component only when the
        # artist contains both Latin and Chinese names.
        #
        # Example:
        #   "lala 徐佳莹" -> "lala"
        latin_parts = re.findall(
            r"[a-z][a-z0-9'’.-]*",
            value,
            flags=re.IGNORECASE,
        )

        if chinese_parts and latin_parts:
            components.add(latin_parts[0])

        return {
            component.strip()
            for component in components
            if component.strip()
        }

    track_artists = normalize_artists(track_artist)
    lyrics_artists = normalize_artists(lyrics_artist)

    if not track_artists or not lyrics_artists:
        return False

    for track_name in track_artists:
        track_components = artist_components(track_name)

        for lyrics_name in lyrics_artists:
            lyrics_components = artist_components(lyrics_name)

            if track_components & lyrics_components:
                return True

    return False

def _artist_similarity(
    track_artist: str | None,
    result_artist: str | None,
) -> float:
    """Return an artist similarity score."""

    first = _normalize_text(track_artist)
    second = _normalize_text(result_artist)

    if not first or not second:
        return 0.0

    if first == second:
        return 1.0

    def normalize_artists(value: str) -> set[str]:
        parts = re.split(
            r",|&|/|／|、|_aka_|feat\.?|ft\.?",
            value,
        )

        return {
            part.strip()
            for part in parts
            if part.strip()
        }

    first_artists = normalize_artists(first)
    second_artists = normalize_artists(second)

    if first_artists and second_artists:
        overlap = first_artists & second_artists

        if overlap:
            return len(overlap) / max(
                len(first_artists),
                len(second_artists),
            )

    return _similarity(first, second)

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

def _duration_is_acceptable(
    track_duration: float | None,
    lyrics_duration: float | None,
) -> bool:
    """Return whether two known durations are close enough."""

    if track_duration is None or lyrics_duration is None:
        return True

    return (
        abs(track_duration - lyrics_duration)
        <= MAX_DURATION_DIFFERENCE
    )

def _title_similarity(
    track_title: str | None,
    result_title: str | None,
) -> float:
    """Return the best similarity across title variants."""
    if not track_title or not result_title:
        return 0.0

    track_variants = _build_title_variants(track_title)
    result_variants = _build_title_variants(result_title)

    return max(
        (
            _similarity(track_variant, result_variant)
            for track_variant in track_variants
            for result_variant in result_variants
        ),
        default=0.0,
    )

def _match_score(
    track: LyricsRequest,
    result: LyricsResult,
) -> float:
    """Calculate the overall match score for a lyrics result."""

    title_score = _title_similarity(
        track.title,
        result.track_name,
    )

    artist_score = _artist_similarity(
        track.artist,
        result.artist_name,
    )

    duration_score = _duration_score(
        track.duration,
        result.duration,
    )

    duration_exact = (
        track.duration is not None
        and result.duration is not None
        and abs(track.duration - result.duration) <= 1.0
    )

    # Strong match:
    # - duration is essentially identical
    # - artist has a meaningful match
    # - title has reasonable similarity
    #
    # This is important for YouTube Music titles containing
    # extra metadata such as "Official Music Video", bilingual
    # names, version information, etc.
    if (
        duration_exact
        and title_score >= 0.60
        and artist_score >= 0.50
    ):
        return 1.0

    return (
        title_score * 0.50
        + artist_score * 0.25
        + duration_score * 0.25
    )
