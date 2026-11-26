from unittest.mock import patch

import pytest

from ytmusic_dl.gui.lyrics_query import build_lyrics_query
from ytmusic_dl.models import Track

def make_track() -> Track:
    return Track(
        playlist_index=1,
        title="Hello",
        artist="Adele",
        album="25",
        duration=295,
        video_id="abc123",
        webpage_url="https://music.youtube.com/watch?v=abc123",
    )

def test_build_query_from_title() -> None:
    """Build a query from a plain title and artist."""

    query = build_lyrics_query(
        "Hello",
        artist="Adele",
        album="25",
        duration=295,
    )

    assert query.title == "Hello"
    assert query.artist == "Adele"
    assert query.album == "25"
    assert query.duration == 295
    assert query.webpage_url is None

def test_build_query_requires_artist_for_titles() -> None:
    """Require an artist when no URL is given."""

    with pytest.raises(
        ValueError,
        match="Artist is required",
    ):
        build_lyrics_query("Hello")

def test_build_query_rejects_empty_input() -> None:
    """Reject an empty title or URL."""

    with pytest.raises(
        ValueError,
        match="Enter a song title",
    ):
        build_lyrics_query("   ")

def test_build_query_from_url() -> None:
    """Extract metadata from a YouTube Music URL."""

    track = make_track()

    with patch(
        "ytmusic_dl.gui.lyrics_query.extract_single_track",
        return_value=[track],
    ) as mock_extract:
        query = build_lyrics_query(
            "https://music.youtube.com/watch?v=abc123"
        )

    mock_extract.assert_called_once_with(
        "https://music.youtube.com/watch?v=abc123"
    )

    assert query.title == "Hello"
    assert query.artist == "Adele"
    assert query.album == "25"
    assert query.duration == 295
    assert query.video_id == "abc123"

def test_build_query_from_url_allows_overrides() -> None:
    """Prefer explicit values over extracted metadata."""

    track = make_track()

    with patch(
        "ytmusic_dl.gui.lyrics_query.extract_single_track",
        return_value=[track],
    ):
        query = build_lyrics_query(
            "https://music.youtube.com/watch?v=abc123",
            artist="Other Artist",
            album="Other Album",
            duration=300,
        )

    assert query.artist == "Other Artist"
    assert query.album == "Other Album"
    assert query.duration == 300
