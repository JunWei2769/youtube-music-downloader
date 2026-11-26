"""
Regression corpus for lyrics matching.

These cases come from real provider responses captured on 2026-11-26.
They keep the current accepted behaviour visible and pin down the
issues that the remaining Phase 2 work must fix.
"""

from unittest.mock import patch

from ytmusic_dl.lyrics import build_candidate, search_candidates
from ytmusic_dl.models import LyricsResult, LyricsQuery

RICK_QUERY = LyricsQuery(
    title=(
        "Rick Astley - Never Gonna Give You Up "
        "(Official Video) (4K Remaster)"
    ),
    artist="Rick Astley",
    duration=213,
)

RICK_ALIASES = (
    "Rick Astley, 理查德 · 保罗 · 艾斯利, "
    "Richard Paul Astley, RickRoll, Rick Roll"
)

def make_result(
    *,
    provider: str,
    title: str,
    artist: str,
    album: str | None,
    duration: float | None,
    synced: str | None = "[00:01.00] Lyrics",
) -> LyricsResult:
    """Create a lyrics result captured from a provider."""

    return LyricsResult(
        provider=provider,
        provider_id="1",
        track_name=title,
        artist_name=artist,
        album_name=album,
        duration=duration,
        instrumental=False,
        synced_lyrics=synced,
        plain_lyrics=None,
    )

def test_netease_alias_list_does_not_lower_confidence() -> None:
    """A long NetEase alias list must not count as several artists."""

    candidate = build_candidate(
        RICK_QUERY,
        make_result(
            provider="netease",
            title="Never Gonna Give You Up (Remastered 2022)",
            artist=RICK_ALIASES,
            album="Whenever You Need Somebody "
            "(Deluxe Edition / Remastered 2022)",
            duration=213.1,
        ),
    )

    assert candidate.accepted
    assert candidate.confidence == "high"
    assert candidate.score > 0.90

def test_clean_title_matches_noisy_youtube_title() -> None:
    """A clean provider title must match a noisy YouTube title."""

    candidate = build_candidate(
        RICK_QUERY,
        make_result(
            provider="netease",
            title="Never Gonna Give You Up",
            artist=RICK_ALIASES,
            album="Whenever You Need Somebody",
            duration=213.6,
        ),
    )

    assert candidate.accepted
    assert candidate.confidence == "high"

def test_lrclib_video_title_as_album_is_not_rejected() -> None:
    """LRCLIB echoing the video title as album must stay acceptable."""

    candidate = build_candidate(
        RICK_QUERY,
        make_result(
            provider="lrclib",
            title=RICK_QUERY.title,
            artist="Rick Astley",
            album=RICK_QUERY.title,
            duration=214,
        ),
    )

    assert candidate.accepted
    assert candidate.confidence == "high"

def test_remaster_ranks_above_pianoforte() -> None:
    """A remaster is closer to the original than an instrumental cover."""

    remaster = build_candidate(
        RICK_QUERY,
        make_result(
            provider="netease",
            title="Never Gonna Give You Up (Remastered 2022)",
            artist=RICK_ALIASES,
            album="Whenever You Need Somebody",
            duration=213.1,
        ),
    )

    pianoforte = build_candidate(
        RICK_QUERY,
        make_result(
            provider="netease",
            title="Never Gonna Give You Up (Pianoforte)",
            artist=RICK_ALIASES,
            album="Never Gonna Give You Up (Pianoforte)",
            duration=209.6,
        ),
    )

    assert remaster.score > pianoforte.score

def test_missing_duration_stays_medium_confidence() -> None:
    """A correct match without a known duration cannot be high."""

    query = LyricsQuery(
        title="空耳 + 还你茉莉 (Live)",
        artist="单依纯",
    )

    candidate = build_candidate(
        query,
        make_result(
            provider="netease",
            title="空耳+还你茉莉（Live）",
            artist="单依纯",
            album="空耳+还你茉莉",
            duration=538.0,
        ),
    )

    assert candidate.accepted
    assert candidate.confidence == "medium"
    assert "duration not compared" in candidate.match_reasons

def test_same_recording_under_two_albums_is_deduplicated() -> None:
    """One recording listed under two album names should appear once."""

    results = [
        make_result(
            provider="netease",
            title="Never Gonna Give You Up (Remastered 2022)",
            artist=RICK_ALIASES,
            album="Whenever You Need Somebody",
            duration=213.1,
        ),
        make_result(
            provider="netease",
            title="Never Gonna Give You Up (Remastered 2022)",
            artist=RICK_ALIASES,
            album="Never",
            duration=213.1,
        ),
    ]

    with patch(
        "ytmusic_dl.lyrics.service.search_lyrics",
        return_value=results,
    ):
        candidates = [
            candidate
            for candidate in search_candidates(RICK_QUERY)
            if candidate.accepted
        ]

    assert len(candidates) == 1

def test_deduplication_prefers_matching_album() -> None:
    """Keep the duplicate whose album matches the query."""

    query = LyricsQuery(
        title="Never Gonna Give You Up",
        artist="Rick Astley",
        album="Whenever You Need Somebody",
        duration=213,
    )

    results = [
        make_result(
            provider="netease",
            title="Never Gonna Give You Up (Remastered 2022)",
            artist=RICK_ALIASES,
            album="Never",
            duration=213.1,
        ),
        make_result(
            provider="netease",
            title="Never Gonna Give You Up (Remastered 2022)",
            artist=RICK_ALIASES,
            album="Whenever You Need Somebody",
            duration=213.1,
        ),
    ]

    with patch(
        "ytmusic_dl.lyrics.service.search_lyrics",
        return_value=results,
    ):
        candidates = search_candidates(query)

    assert len(candidates) == 1
    assert candidates[0].result.album_name == (
        "Whenever You Need Somebody"
    )

def test_deduplication_keeps_cross_provider_copies() -> None:
    """Do not collapse copies from different providers."""

    results = [
        make_result(
            provider="lrclib",
            title="Never Gonna Give You Up (Remastered 2022)",
            artist=RICK_ALIASES,
            album="Whenever You Need Somebody",
            duration=213.1,
        ),
        make_result(
            provider="netease",
            title="Never Gonna Give You Up (Remastered 2022)",
            artist=RICK_ALIASES,
            album="Whenever You Need Somebody",
            duration=213.1,
        ),
    ]

    with patch(
        "ytmusic_dl.lyrics.service.search_lyrics",
        return_value=results,
    ):
        candidates = search_candidates(RICK_QUERY)

    assert len(candidates) == 2

def test_deduplication_keeps_different_durations() -> None:
    """Keep recordings that differ clearly in length."""

    results = [
        make_result(
            provider="netease",
            title="Never Gonna Give You Up",
            artist=RICK_ALIASES,
            album="Whenever You Need Somebody",
            duration=213,
        ),
        make_result(
            provider="netease",
            title="Never Gonna Give You Up",
            artist=RICK_ALIASES,
            album="Whenever You Need Somebody",
            duration=260,
        ),
    ]

    with patch(
        "ytmusic_dl.lyrics.service.search_lyrics",
        return_value=results,
    ):
        candidates = search_candidates(RICK_QUERY)

    assert len(candidates) == 2

def test_deduplication_prefers_candidate_with_lyrics() -> None:
    """Keep the duplicate that actually has lyrics content."""

    results = [
        make_result(
            provider="netease",
            title="Never Gonna Give You Up (Remastered 2022)",
            artist=RICK_ALIASES,
            album="Never",
            duration=213.1,
            synced=None,
        ),
        make_result(
            provider="netease",
            title="Never Gonna Give You Up (Remastered 2022)",
            artist=RICK_ALIASES,
            album="Never",
            duration=213.1,
        ),
    ]

    with patch(
        "ytmusic_dl.lyrics.service.search_lyrics",
        return_value=results,
    ):
        candidates = search_candidates(RICK_QUERY)

    assert len(candidates) == 1
    assert candidates[0].result.synced_lyrics is not None

def test_original_and_remaster_are_deduplicated() -> None:
    """A remaster and its original are the same recording."""

    query = LyricsQuery(
        title="Test Song",
        artist="Test Artist",
        duration=200,
    )

    results = [
        make_result(
            provider="netease",
            title="Test Song",
            artist="Test Artist",
            album="Album A",
            duration=200,
        ),
        make_result(
            provider="netease",
            title="Test Song (Remastered 2022)",
            artist="Test Artist",
            album="Album B",
            duration=200,
        ),
    ]

    with patch(
        "ytmusic_dl.lyrics.service.search_lyrics",
        return_value=results,
    ):
        candidates = search_candidates(query)

    assert len(candidates) == 1

def test_deduplication_prefers_requested_edition() -> None:
    """Keep the copy whose edition the query asks for."""

    query = LyricsQuery(
        title="Test Song (Remastered 2022)",
        artist="Test Artist",
        duration=200,
    )

    results = [
        make_result(
            provider="netease",
            title="Test Song",
            artist="Test Artist",
            album="Album A",
            duration=200,
        ),
        make_result(
            provider="netease",
            title="Test Song (Remastered 2022)",
            artist="Test Artist",
            album="Album B",
            duration=200,
        ),
    ]

    with patch(
        "ytmusic_dl.lyrics.service.search_lyrics",
        return_value=results,
    ):
        candidates = search_candidates(query)

    assert len(candidates) == 1
    assert candidates[0].result.track_name == (
        "Test Song (Remastered 2022)"
    )
