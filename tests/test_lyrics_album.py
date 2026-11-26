"""Album-aware scoring and album normalization."""

from unittest.mock import patch

from ytmusic_dl.lyrics import (
    _albums_match,
    build_candidate,
    search_candidates,
)
from ytmusic_dl.models import (
    LyricsQuery,
    LyricsResult,
)

QUERY = LyricsQuery(
    title="Hello",
    artist="Adele",
    album="25",
    duration=295,
)

def make_result(
    *,
    album: str | None = "25",
    title: str = "Hello",
    duration: float | None = 295,
) -> LyricsResult:
    """Create a lyrics result with the given album."""

    return LyricsResult(
        provider="lrclib",
        provider_id="1",
        track_name=title,
        artist_name="Adele",
        album_name=album,
        duration=duration,
        instrumental=False,
        synced_lyrics="[00:01.00] Lyrics",
        plain_lyrics=None,
    )

def test_albums_match_ignores_packaging_details() -> None:
    """Deluxe and remastered packaging still names the same album."""

    assert _albums_match(
        "Whenever You Need Somebody",
        "Whenever You Need Somebody "
        "(Deluxe Edition / Remastered 2022)",
    )

    assert not _albums_match("25", "Hello")

def test_album_match_adds_bonus_and_reason() -> None:
    """A matching album is supporting evidence."""

    matching = build_candidate(
        QUERY,
        make_result(album="25"),
    )

    different = build_candidate(
        QUERY,
        make_result(album="Hello"),
    )

    assert "album matches" in matching.match_reasons
    assert "album matches" not in different.match_reasons

    assert round(matching.score - different.score, 2) == 0.05

def test_album_echoing_video_title_does_not_match() -> None:
    """Do not treat a video title echoed as album as a match."""

    candidate = build_candidate(
        QUERY,
        make_result(
            album="Adele - Hello (Official Video)",
        ),
    )

    assert "album matches" not in candidate.match_reasons

def test_unknown_album_gets_no_bonus() -> None:
    """Only compare albums when the query names one."""

    query = LyricsQuery(
        title="Hello",
        artist="Adele",
    )

    candidate = build_candidate(
        query,
        make_result(album="25"),
    )

    assert "album matches" not in candidate.match_reasons

def test_album_mismatch_is_not_rejected() -> None:
    """Album data is unreliable, so it must never reject a match."""

    candidate = build_candidate(
        QUERY,
        make_result(album="Some Compilation"),
    )

    assert candidate.accepted
    assert candidate.confidence == "high"

def test_album_match_lifts_missing_duration_to_high() -> None:
    """Album evidence can compensate for an unknown duration."""

    query = LyricsQuery(
        title="Hello",
        artist="Adele",
        album="25",
    )

    candidate = build_candidate(
        query,
        make_result(album="25", duration=295),
    )

    assert candidate.confidence == "high"
    assert "album matches" in candidate.match_reasons
    assert "duration not compared" in candidate.match_reasons

def test_missing_duration_without_album_stays_medium() -> None:
    """Without duration or album evidence, confidence stays medium."""

    query = LyricsQuery(
        title="Hello",
        artist="Adele",
    )

    candidate = build_candidate(
        query,
        make_result(album="25", duration=295),
    )

    assert candidate.confidence == "medium"

def test_deduplication_uses_normalized_album() -> None:
    """Prefer the duplicate whose packaged album matches the query."""

    query = LyricsQuery(
        title="Never Gonna Give You Up",
        artist="Rick Astley",
        album="Whenever You Need Somebody",
        duration=213,
    )

    results = [
        make_result(
            album="Never",
            title="Never Gonna Give You Up",
            duration=213,
        ),
        make_result(
            album=(
                "Whenever You Need Somebody "
                "(Deluxe Edition / Remastered 2022)"
            ),
            title="Never Gonna Give You Up",
            duration=213,
        ),
    ]

    with patch(
        "ytmusic_dl.lyrics.service.search_lyrics",
        return_value=results,
    ):
        candidates = search_candidates(query)

    assert len(candidates) == 1
    assert candidates[0].result.album_name == (
        "Whenever You Need Somebody "
        "(Deluxe Edition / Remastered 2022)"
    )
