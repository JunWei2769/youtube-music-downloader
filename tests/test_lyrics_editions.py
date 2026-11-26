"""Edition detection and edition-aware scoring."""

from ytmusic_dl.lyrics import (
    _extract_editions,
    build_candidate,
)
from ytmusic_dl.models import (
    LyricsQuery,
    LyricsResult,
)

QUERY = LyricsQuery(
    title="Test Song",
    artist="Test Artist",
    duration=200,
)

def make_result(
    title: str,
    *,
    artist: str = "Test Artist",
    duration: float | None = 200,
) -> LyricsResult:
    """Create a lyrics result with the given title."""

    return LyricsResult(
        provider="netease",
        provider_id="1",
        track_name=title,
        artist_name=artist,
        album_name="Test Album",
        duration=duration,
        instrumental=False,
        synced_lyrics="[00:01.00] Lyrics",
        plain_lyrics=None,
    )

def test_extract_editions_from_brackets() -> None:
    """Read edition tags from bracketed segments."""

    assert _extract_editions("Song (Live)") == {"live"}
    assert _extract_editions("Song（现场版）") == {"live"}
    assert _extract_editions("Song (Remastered 2022)") == {
        "remaster"
    }
    assert _extract_editions("Song (Pianoforte)") == {
        "instrumental"
    }
    assert _extract_editions("Song (Karaoke)") == {
        "instrumental"
    }
    assert _extract_editions("Song (Acoustic Version)") == {
        "acoustic"
    }
    assert _extract_editions("Song (DJ版)") == {"remix"}

def test_ambiguous_title_words_are_not_editions() -> None:
    """Do not treat ordinary title words as edition tags."""

    assert _extract_editions("Live Forever") == frozenset()
    assert _extract_editions("Piano Man") == frozenset()
    assert _extract_editions("Cover Me") == frozenset()
    assert _extract_editions("Demo") == frozenset()

def test_extract_editions_from_suffixes() -> None:
    """Read edition tags written as a dash suffix."""

    assert _extract_editions("Song - Live") == {"live"}
    assert _extract_editions("Song - Acoustic") == {"acoustic"}

def test_extract_multiple_editions() -> None:
    """Support titles that combine edition tags."""

    assert _extract_editions(
        "Song (Live / Remastered)"
    ) == {"live", "remaster"}

def test_live_result_is_penalized() -> None:
    """Prefer the studio version over a live version."""

    studio = build_candidate(
        QUERY,
        make_result("Test Song"),
    )

    live = build_candidate(
        QUERY,
        make_result("Test Song (Live)"),
    )

    assert live.accepted
    assert live.score < studio.score
    assert live.confidence == "medium"
    assert live.warnings == ["result is the live edition"]

def test_requested_live_edition_is_not_penalized() -> None:
    """Accept a live result when the query asks for live."""

    query = LyricsQuery(
        title="Test Song (Live)",
        artist="Test Artist",
        duration=200,
    )

    candidate = build_candidate(
        query,
        make_result("Test Song (Live)"),
    )

    assert candidate.accepted
    assert candidate.confidence == "high"
    assert candidate.warnings == []
    assert "live edition" in candidate.match_reasons

def test_remaster_is_treated_as_the_same_recording() -> None:
    """Do not penalize remasters in either direction."""

    remaster = build_candidate(
        QUERY,
        make_result("Test Song (Remastered 2022)"),
    )

    assert remaster.accepted
    assert remaster.warnings == []
    assert remaster.confidence == "high"

def test_instrumental_result_is_rejected() -> None:
    """Never auto-select an instrumental arrangement."""

    candidate = build_candidate(
        QUERY,
        make_result("Test Song (Pianoforte)"),
    )

    assert not candidate.accepted
    assert "instrumental arrangement" in (
        candidate.rejection_reasons
    )
