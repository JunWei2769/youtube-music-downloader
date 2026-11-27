"""Scoring helpers that decide how well a lyrics result matches a track."""

import re
from typing import Literal

from ytmusic_dl.lyrics.normalize import (
    _build_title_variants,
    _extract_editions,
    _normalize_text,
    _similarity,
)
from ytmusic_dl.models import (
    LyricsRequest,
    LyricsResult,
)
from ytmusic_dl.utils import clean_artist_name

MIN_TITLE_SIMILARITY = 0.60
MAX_DURATION_DIFFERENCE = 45.0
MAX_DURATION_RATIO = 0.25

HIGH_CONFIDENCE_SCORE = 0.90
MEDIUM_CONFIDENCE_SCORE = 0.75

CONFIDENCE_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
}

NEUTRAL_EDITIONS = frozenset({"remaster"})
MAJOR_EDITION_PENALTY = 0.25
MAX_EDITION_PENALTY = 0.35
ALBUM_MATCH_BONUS = 0.05

def confidence_at_least(
    confidence: str,
    minimum: str,
) -> bool:
    """Return whether a confidence label meets a minimum."""

    return (
        CONFIDENCE_ORDER[confidence]
        >= CONFIDENCE_ORDER[minimum]
    )

def confidence_for_score(
    score: float,
) -> Literal["high", "medium", "low"]:
    """Map a match score to a confidence label."""

    if score >= HIGH_CONFIDENCE_SCORE:
        return "high"

    if score >= MEDIUM_CONFIDENCE_SCORE:
        return "medium"

    return "low"

def _split_artist_names(value: str) -> set[str]:
    """Split an artist string into separate names."""

    return {
        part.strip()
        for part in re.split(
            r",|&|/|／|、|_aka_|feat\.?|ft\.?",
            value,
        )
        if part.strip()
    }

def _artist_components(value: str) -> set[str]:
    """Return name components for mixed Chinese/Latin artist names."""

    components = {value}

    chinese_parts = re.findall(
        r"[\u3400-\u4dbf\u4e00-\u9fff]+",
        value,
    )

    components.update(chinese_parts)

    latin_parts = re.findall(
        r"[a-z][a-z0-9'’.-]*",
        value,
        flags=re.IGNORECASE,
    )

    if chinese_parts and latin_parts:
        components.add(latin_parts[0])

    if latin_parts:
        components.add(" ".join(latin_parts))

    return {
        component.strip()
        for component in components
        if component.strip()
    }

def _artist_matches(
    track_artist: str | None,
    lyrics_artist: str | None,
) -> bool:
    """Return whether two artist names refer to the same artist."""
    if not track_artist or not lyrics_artist:
        return False

    track_artists = _split_artist_names(
        _normalize_text(
            clean_artist_name(track_artist) or track_artist
        )
    )
    lyrics_artists = _split_artist_names(
        _normalize_text(
            clean_artist_name(lyrics_artist) or lyrics_artist
        )
    )

    if not track_artists or not lyrics_artists:
        return False

    lyrics_components = {
        component
        for lyrics_name in lyrics_artists
        for component in _artist_components(lyrics_name)
    }

    return any(
        _artist_components(track_name) & lyrics_components
        for track_name in track_artists
    )

def _artist_similarity(
    track_artist: str | None,
    result_artist: str | None,
) -> float:
    """Return an artist similarity score."""

    first = _normalize_text(
        clean_artist_name(track_artist)
    )
    second = _normalize_text(
        clean_artist_name(result_artist)
    )

    if not first or not second:
        return 0.0

    if first == second:
        return 1.0

    first_artists = _split_artist_names(first)
    second_artists = _split_artist_names(second)

    if first_artists and second_artists:
        overlap = first_artists & second_artists

        if overlap:
            # Providers, especially NetEase, can list many aliases
            # for one artist. Compare against the shorter list so an
            # alias dump does not dilute a real name match.
            return len(overlap) / min(
                len(first_artists),
                len(second_artists),
            )

        first_components = set().union(
            *(
                _artist_components(name)
                for name in first_artists
            )
        )
        second_components = set().union(
            *(
                _artist_components(name)
                for name in second_artists
            )
        )

        if first_components & second_components:
            # The same name appears in a different script or as one
            # name in a collaboration list.
            return 0.75

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
    """Return whether two known durations are close enough.

    Official music videos often include intros and outros, so the
    video duration can be longer than the track duration used by
    lyrics providers. Allow a small absolute or relative difference.
    """

    if track_duration is None or lyrics_duration is None:
        return True

    difference = abs(track_duration - lyrics_duration)

    if difference <= MAX_DURATION_DIFFERENCE:
        return True

    shortest = min(track_duration, lyrics_duration)

    if shortest <= 0:
        return False

    return (
        difference / shortest
        <= MAX_DURATION_RATIO
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

def _passes_basic_checks(
    request: LyricsRequest,
    result: LyricsResult,
) -> bool:
    """Return whether a result clears the cheap rejection rules."""

    if (
        "instrumental" in _extract_editions(result.track_name)
        and "instrumental"
        not in _extract_editions(request.title)
    ):
        return False

    return (
        _title_similarity(request.title, result.track_name)
        >= MIN_TITLE_SIMILARITY
        and _artist_matches(request.artist, result.artist_name)
        and _duration_is_acceptable(
            request.duration,
            result.duration,
        )
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
