from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

from ytmusic_dl.lyrics import (
    NetEaseProvider,
    _build_netease_search_terms,
    _duration_is_acceptable,
    _normalize_text,
    _parse_netease_result,
    _similarity,
    _title_similarity,
    build_candidate,
    confidence_for_score,
    fetch_missing_lyrics,
    find_best_lyrics,
    search_candidates,
    write_lyrics,
)
from ytmusic_dl.lyrics.providers.netease import (
    MAX_LYRICS_FETCHES,
    MAX_SEARCH_TERMS,
)
from ytmusic_dl.models import LyricsResult, Track


def make_track() -> Track:
    return Track(
        playlist_index=1,
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        duration=200,
        video_id="test123",
    )


def make_result(
    *,
    provider: str = "test",
    provider_id: str = "1",
    title: str = "Test Song",
    artist: str = "Test Artist",
    duration: float | None = 200,
    synced: str | None = None,
    plain: str | None = None,
) -> LyricsResult:
    return LyricsResult(
        provider=provider,
        provider_id=provider_id,
        track_name=title,
        artist_name=artist,
        album_name="Test Album",
        duration=duration,
        instrumental=False,
        synced_lyrics=synced,
        plain_lyrics=plain,
    )

def make_netease_song(
    song_id: int,
    *,
    title: str = "Test Song",
    artist: str = "Test Artist",
    duration_ms: int = 200000,
) -> dict:
    """Create a NetEase search result song."""

    return {
        "id": song_id,
        "name": title,
        "ar": [{"name": artist}],
        "al": {"name": "Test Album"},
        "dt": duration_ms,
    }

def make_netease_client(
    songs: list[dict],
    *,
    lyrics: str = "[00:01.00] Test lyrics",
) -> MagicMock:
    """Create a mocked NetEase HTTP client."""

    search_response = MagicMock()
    search_response.raise_for_status.return_value = None
    search_response.json.return_value = {
        "code": 200,
        "result": {"songs": songs},
    }

    lyrics_response = MagicMock()
    lyrics_response.raise_for_status.return_value = None
    lyrics_response.json.return_value = {
        "lrc": {"lyric": lyrics},
    }

    discover_response = MagicMock()
    discover_response.raise_for_status.return_value = None

    client = MagicMock()

    def mock_get(url: str, *args, **kwargs):
        if url == "https://music.163.com/discover":
            return discover_response

        if url == "https://music.163.com/api/song/lyric":
            return lyrics_response

        raise AssertionError(f"Unexpected GET URL: {url}")

    client.get.side_effect = mock_get
    client.post.return_value = search_response

    return client


def test_normalize_text() -> None:
    assert (
        _normalize_text(
            "空耳+还你茉莉（Live）"
        )
        == "空耳+还你茉莉(live)"
    )


def test_similarity_exact_match() -> None:
    assert _similarity(
        "Test Song",
        "Test Song",
    ) == 1.0

def test_title_similarity_uses_bracketed_chinese_title() -> None:
    """Use a bracketed song title instead of the upload title."""

    assert _title_similarity(
        "Jonathan Lee李宗盛 [ 山丘 ] Official Music Video",
        "山丘",
    ) >= 0.90

def test_title_similarity_combines_chinese_book_titles() -> None:
    """Combine 《…》 segments from a medley title."""

    assert _title_similarity(
        "【单依纯《空耳》+《还你茉莉》】纯妹妹2.0巡回演唱会官摄",
        "空耳+还你茉莉（Live）",
    ) >= 0.60


def test_duration_is_acceptable() -> None:
    assert _duration_is_acceptable(
        200,
        202,
    )

    assert _duration_is_acceptable(
        200,
        210,
    )

    # Official music videos can be longer than the track.
    assert _duration_is_acceptable(
        210,
        249,
    )

    assert _duration_is_acceptable(
        200,
        245,
    )

    assert not _duration_is_acceptable(
        200,
        260,
    )

    assert not _duration_is_acceptable(
        200,
        350,
    )


def test_find_best_lyrics_prefers_synced() -> None:
    track = make_track()

    plain = make_result(
        provider="lrclib",
        provider_id="1",
        plain="Plain lyrics",
    )

    synced = make_result(
        provider="netease",
        provider_id="2",
        synced="[00:01.00] Synced lyrics",
    )

    result = find_best_lyrics(
        track,
        [plain, synced],
    )

    assert result is not None
    assert result.provider == "netease"
    assert result.synced_lyrics is not None


def test_find_best_lyrics_rejects_wrong_duration() -> None:
    track = make_track()

    wrong = make_result(
        duration=350,
        synced="[00:01.00] Wrong song",
    )

    result = find_best_lyrics(
        track,
        [wrong],
    )

    assert result is None


def test_find_best_lyrics_rejects_wrong_artist() -> None:
    track = make_track()

    wrong = make_result(
        artist="Completely Different Artist",
        synced="[00:01.00] Wrong song",
    )

    result = find_best_lyrics(
        track,
        [wrong],
    )

    assert result is None


def test_find_best_lyrics_accepts_artist_collaboration() -> None:
    track = Track(
        playlist_index=1,
        title="Test Song",
        artist="Test Artist, Guest Artist",
        album="Test Album",
        duration=200,
    )

    result = make_result(
        artist="Test Artist",
        synced="[00:01.00] Lyrics",
    )

    best = find_best_lyrics(
        track,
        [result],
    )

    assert best is not None

def test_find_best_lyrics_accepts_aka_artist() -> None:
    track = Track(
        playlist_index=1,
        title="Test Song",
        artist="sodagreen_aka_oaeen",
        album="Test Album",
        duration=200,
    )

    result = make_result(
        artist="苏打绿, sodagreen",
        synced="[00:01.00] Lyrics",
    )

    best = find_best_lyrics(
        track,
        [result],
    )

    assert best is not None


def test_find_best_lyrics_accepts_bilingual_youtube_music_title() -> None:
    track = Track(
        playlist_index=1,
        title=(
            "蘇打綠 sodagreen"
            "【博物館 The Museum】"
            "（蘇打綠版）"
            "Official Music Video"
        ),
        artist="sodagreen_aka_oaeen",
        album="冬 未了 (蘇打綠版)",
        duration=276,
    )

    result = make_result(
        provider="netease",
        provider_id="2685528176",
        title=(
            "博物馆 (苏打绿版) "
            "(The Museum (sodagreen Version))"
        ),
        artist="苏打绿, sodagreen",
        duration=275.893,
        synced="[00:01.00] Lyrics",
    )

    best = find_best_lyrics(
        track,
        [result],
    )

    assert best is not None
    assert best.provider == "netease"
    assert best.provider_id == "2685528176"

def test_find_best_lyrics_accepts_featured_artists_in_title() -> None:
    track = Track(
        playlist_index=1,
        title="切歌 feat. ABAO阿爆 & Brandy",
        artist="LaLa 徐佳瑩",
        album="給",
        duration=221,
    )

    result = make_result(
        provider="netease",
        provider_id="1957782394",
        title="切歌",
        artist="徐佳莹, LaLa Hsu, 阿爆 & Brandy",
        duration=220.042,
        synced="[00:01.00] Lyrics",
    )

    best = find_best_lyrics(
        track,
        [result],
    )

    assert best is not None
    assert best.provider_id == "1957782394"

def test_write_synced_lyrics(
    tmp_path: Path,
) -> None:
    lyrics = make_result(
        synced="[00:01.00] Hello",
        plain="Hello",
    )

    output_path = tmp_path / "song.lrc"

    result = write_lyrics(
        lyrics,
        output_path,
    )

    assert result == output_path
    assert output_path.read_text(
        encoding="utf-8"
    ) == "[00:01.00] Hello"


def test_write_plain_lyrics(
    tmp_path: Path,
) -> None:
    lyrics = make_result(
        plain="Hello\nWorld",
    )

    output_path = tmp_path / "song.lrc"

    write_lyrics(
        lyrics,
        output_path,
    )

    assert output_path.read_text(
        encoding="utf-8"
    ) == "Hello\nWorld"


def test_netease_provider_initializes_lazily() -> None:
    discover_response = MagicMock()
    discover_response.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.get.return_value = discover_response

    with patch(
        "ytmusic_dl.lyrics.httpx.Client",
        return_value=mock_client,
    ):
        provider = NetEaseProvider()

    mock_client.get.assert_not_called()
    assert provider.initialized is False


def test_netease_search_keeps_wrong_duration_candidate() -> None:
    """Return every candidate and hydrate only plausible ones."""

    track = make_track()

    search_response = MagicMock()
    search_response.raise_for_status.return_value = None
    search_response.json.return_value = {
        "code": 200,
        "result": {
            "songs": [
                {
                    "id": 1,
                    "name": "Test Song",
                    "ar": [
                        {
                            "name": "Test Artist",
                        }
                    ],
                    "al": {
                        "name": "Test Album",
                    },
                    "dt": 200000,
                },
                {
                    "id": 2,
                    "name": "Test Song",
                    "ar": [
                        {
                            "name": "Test Artist",
                        }
                    ],
                    "al": {
                        "name": "Test Album",
                    },
                    "dt": 350000,
                },
            ]
        }
    }

    lyrics_response = MagicMock()
    lyrics_response.raise_for_status.return_value = None
    lyrics_response.json.return_value = {
        "lrc": {
            "lyric": "[00:01.00] Test lyrics"
        }
    }

    discover_response = MagicMock()
    discover_response.raise_for_status.return_value = None

    mock_client = MagicMock()

    def mock_get(url: str, *args, **kwargs):
        if url == "https://music.163.com/discover":
            return discover_response

        if url == "https://music.163.com/api/song/lyric":
            return lyrics_response

        raise AssertionError(f"Unexpected GET URL: {url}")

    mock_client.get.side_effect = mock_get
    mock_client.post.return_value = search_response

    with patch(
        "ytmusic_dl.lyrics.httpx.Client",
        return_value=mock_client,
    ):
        provider = NetEaseProvider()

        mock_client.get.assert_not_called()
        mock_client.post.assert_not_called()

        results = provider.search(track)

    assert provider.initialized is True

    assert len(results) == 2

    by_id = {
        result.provider_id: result
        for result in results
    }

    assert by_id["1"].duration == 200.0
    assert by_id["1"].synced_lyrics == "[00:01.00] Test lyrics"

    # The wrong-duration candidate is still returned, but its
    # lyrics are not fetched eagerly.
    assert by_id["2"].duration == 350.0
    assert by_id["2"].synced_lyrics is None

    assert mock_client.get.call_count == 2

    expected_searches = len(
        _build_netease_search_terms(track)
    )

    assert mock_client.post.call_count == expected_searches

def test_netease_search_accepts_bilingual_youtube_music_title() -> None:
    track = Track(
        playlist_index=1,
        title=(
            "蘇打綠 sodagreen"
            "【博物館 The Museum】"
            "（蘇打綠版）"
            "Official Music Video"
        ),
        artist="sodagreen_aka_oaeen",
        album="冬 未了 (蘇打綠版)",
        duration=276,
    )

    search_response = MagicMock()
    search_response.raise_for_status.return_value = None
    search_response.json.return_value = {
        "code": 200,
        "result": {
            "songs": [
                {
                    "id": 2685528176,
                    "name": (
                        "博物馆 (苏打绿版) "
                        "(The Museum (sodagreen Version))"
                    ),
                    "ar": [
                        {
                            "name": "苏打绿",
                            "alias": ["sodagreen"],
                        }
                    ],
                    "al": {
                        "name": "冬 未了 (苏打绿版)",
                    },
                    "dt": 275893,
                }
            ]
        }
    }

    lyrics_response = MagicMock()
    lyrics_response.raise_for_status.return_value = None
    lyrics_response.json.return_value = {
        "lrc": {
            "lyric": "[00:01.00] Test lyrics"
        }
    }

    discover_response = MagicMock()
    discover_response.raise_for_status.return_value = None

    mock_client = MagicMock()

    def mock_get(url: str, *args, **kwargs):
        if url == "https://music.163.com/discover":
            return discover_response

        if url == "https://music.163.com/api/song/lyric":
            return lyrics_response

        raise AssertionError(
            f"Unexpected GET URL: {url}"
        )

    mock_client.get.side_effect = mock_get

    mock_client.post.return_value = search_response

    with patch(
        "ytmusic_dl.lyrics.httpx.Client",
        return_value=mock_client,
    ):
        provider = NetEaseProvider()

        results = provider.search(track)

    assert len(results) == 1
    assert results[0].provider == "netease"
    assert results[0].provider_id == "2685528176"
    assert results[0].synced_lyrics == (
        "[00:01.00] Test lyrics"
    )

def test_netease_search_handles_api_error_response() -> None:
    track = make_track()

    discover_response = MagicMock()
    discover_response.raise_for_status.return_value = None

    search_response = MagicMock()
    search_response.raise_for_status.return_value = None
    search_response.json.return_value = {
        "code": -462,
        "msg": "操作频繁，请稍候再试",
    }

    mock_client = MagicMock()
    mock_client.get.return_value = discover_response
    mock_client.post.return_value = search_response

    with patch(
        "ytmusic_dl.lyrics.httpx.Client",
        return_value=mock_client,
    ):
        provider = NetEaseProvider()

        results = provider.search(track)

    assert results == []

    assert mock_client.get.call_count == 1
    assert mock_client.post.call_count == 1

def test_netease_search_keeps_low_score_candidate_without_lyrics() -> None:
    """Return rejected candidates without fetching their lyrics."""
    track = make_track()

    search_response = MagicMock()
    search_response.raise_for_status.return_value = None
    search_response.json.return_value = {
        "code": 200,
        "result": {
            "songs": [
                {
                    "id": 999,
                    "name": "Completely Different Song",
                    "ar": [
                        {
                            "name": "Completely Different Artist",
                        }
                    ],
                    "al": {
                        "name": "Different Album",
                    },
                    "dt": 200000,
                }
            ]
        },
    }

    discover_response = MagicMock()
    discover_response.raise_for_status.return_value = None

    mock_client = MagicMock()

    mock_client.get.return_value = discover_response
    mock_client.post.return_value = search_response

    with patch(
        "ytmusic_dl.lyrics.httpx.Client",
        return_value=mock_client,
    ):
        provider = NetEaseProvider()

        results = provider.search(track)

    assert len(results) == 1

    assert results[0].provider_id == "999"
    assert results[0].synced_lyrics is None

    # Only the initialization GET request should have been made.
    assert mock_client.get.call_count == 1

    # NetEase search should happen, but lyrics should never be fetched.
    assert mock_client.post.call_count >= 1

def test_netease_provider_reuses_initialized_session() -> None:
    track = make_track()

    discover_response = MagicMock()
    discover_response.raise_for_status.return_value = None

    search_response = MagicMock()
    search_response.raise_for_status.return_value = None
    search_response.json.return_value = {
        "code": 200,
        "result": {
            "songs": []
        }
    }

    mock_client = MagicMock()

    mock_client.get.return_value = discover_response
    mock_client.post.return_value = search_response

    with patch(
        "ytmusic_dl.lyrics.httpx.Client",
        return_value=mock_client,
    ):
        provider = NetEaseProvider()

        first_results = provider.search(track)
        second_results = provider.search(track)

    assert first_results == []
    assert second_results == []

    # /discover should only be called once.
    assert mock_client.get.call_count == 1

    expected_searches = len(
        _build_netease_search_terms(track)
    )

    assert mock_client.post.call_count == (
        expected_searches * 2
    )

    discover_calls = [
        call
        for call in mock_client.get.call_args_list
        if call.args[0] == "https://music.163.com/discover"
    ]

    assert len(discover_calls) == 1

    first_call = mock_client.get.call_args_list[0]

    assert first_call.args[0] == (
        "https://music.163.com/discover"
    )


def test_parse_netease_cloudsearch_result() -> None:
    song = {
        "id": 2685528175,
        "name": "痛快的哀艳 (苏打绿版)",
        "tns": [
            "Violently, the Sorrowful Glamour (sodagreen Version)"
        ],
        "ar": [
            {
                "name": "苏打绿",
                "alias": ["sodagreen"],
            }
        ],
        "al": {
            "name": "冬 未了 (苏打绿版)",
        },
        "dt": 365733,
    }

    result = _parse_netease_result(song)

    assert result.provider == "netease"
    assert result.provider_id == "2685528175"
    assert "痛快的哀艳" in result.track_name
    assert "Violently, the Sorrowful Glamour" in result.track_name
    assert "苏打绿" in result.artist_name
    assert "sodagreen" in result.artist_name
    assert result.album_name == "冬 未了 (苏打绿版)"
    assert result.duration == 365.733

def test_build_candidate_explains_strong_match() -> None:
    """Explain why a strong candidate was accepted."""

    candidate = build_candidate(
        make_track(),
        make_result(synced="[00:01.00] Test lyrics"),
    )

    assert candidate.accepted
    assert candidate.confidence == "high"
    assert round(candidate.score, 2) == 1.15

    assert "title matches" in candidate.match_reasons
    assert "artist matches" in candidate.match_reasons
    assert "duration within 0.0s" in candidate.match_reasons
    assert "album matches" in candidate.match_reasons

    assert (
        "synchronized lyrics available"
        in candidate.match_reasons
    )

def test_build_candidate_rejects_artist_mismatch() -> None:
    """Reject a candidate with a different artist."""

    candidate = build_candidate(
        make_track(),
        make_result(artist="Other Artist", synced="lyrics"),
    )

    assert not candidate.accepted
    assert "artist does not match" in (
        candidate.rejection_reasons
    )

def test_build_candidate_rejects_duration_mismatch() -> None:
    """Reject a candidate whose duration is clearly different."""

    candidate = build_candidate(
        make_track(),
        make_result(duration=260, synced="lyrics"),
    )

    assert not candidate.accepted
    assert any(
        "duration differs" in reason
        for reason in candidate.rejection_reasons
    )

def test_build_candidate_tolerates_music_video_duration() -> None:
    """Accept a longer official video as the same song."""

    result = make_result(duration=239, synced="lyrics")
    result.album_name = None

    candidate = build_candidate(
        make_track(),
        result,
    )

    assert candidate.accepted
    assert candidate.confidence == "medium"
    assert any(
        "duration differs" in warning
        for warning in candidate.warnings
    )

def test_build_candidate_rejects_unrelated_title() -> None:
    """Reject a candidate with a clearly different title."""

    candidate = build_candidate(
        make_track(),
        make_result(
            title="Completely Different Song",
            synced="lyrics",
        ),
    )

    assert not candidate.accepted
    assert any(
        "title similarity" in reason
        for reason in candidate.rejection_reasons
    )

def test_confidence_for_score() -> None:
    """Map scores to confidence labels."""

    assert confidence_for_score(1.10) == "high"
    assert confidence_for_score(0.80) == "medium"
    assert confidence_for_score(0.50) == "low"

def test_search_candidates_scores_every_result() -> None:
    """Return one scored candidate per provider result."""

    track = make_track()

    results = [
        make_result(synced="first"),
        make_result(provider="netease", synced="second"),
    ]

    with patch(
        "ytmusic_dl.lyrics.service.search_lyrics",
        return_value=results,
    ):
        candidates = search_candidates(track)

    assert len(candidates) == 2
    assert all(candidate.accepted for candidate in candidates)

    assert {
        candidate.result.provider
        for candidate in candidates
    } == {"test", "netease"}

def test_netease_search_hydrates_multiple_plausible_candidates() -> None:
    """Fetch lyrics for every plausible candidate, not only the first."""

    track = make_track()

    songs = [
        make_netease_song(song_id)
        for song_id in (1, 2, 3)
    ]

    client = make_netease_client(songs)

    with patch(
        "ytmusic_dl.lyrics.httpx.Client",
        return_value=client,
    ):
        provider = NetEaseProvider()

        results = provider.search(track)

    assert len(results) == 3

    assert all(
        result.synced_lyrics == "[00:01.00] Test lyrics"
        for result in results
    )

    # One discovery request plus one lyrics request per candidate.
    assert client.get.call_count == 1 + len(songs)

def test_netease_search_caps_eager_lyrics_fetches() -> None:
    """Return every candidate but hydrate at most the fetch cap."""

    track = make_track()

    songs = [
        make_netease_song(song_id)
        for song_id in range(1, MAX_LYRICS_FETCHES + 3)
    ]

    client = make_netease_client(songs)

    with patch(
        "ytmusic_dl.lyrics.httpx.Client",
        return_value=client,
    ):
        provider = NetEaseProvider()

        results = provider.search(track)

    assert len(results) == len(songs)

    hydrated = [
        result
        for result in results
        if result.synced_lyrics
    ]

    assert len(hydrated) == MAX_LYRICS_FETCHES

    assert client.get.call_count == (
        1 + MAX_LYRICS_FETCHES
    )

def test_netease_fetch_lyrics_populates_content() -> None:
    """Fetch lyrics on demand for an unhydrated candidate."""

    result = make_result(provider="netease")
    client = make_netease_client([])

    with patch(
        "ytmusic_dl.lyrics.httpx.Client",
        return_value=client,
    ):
        provider = NetEaseProvider()

    hydrated = provider.fetch_lyrics(result)

    assert hydrated.synced_lyrics == "[00:01.00] Test lyrics"

    # The original candidate is left untouched.
    assert result.synced_lyrics is None

def test_netease_fetch_lyrics_keeps_existing_content() -> None:
    """Do not request lyrics that are already present."""

    result = make_result(
        provider="netease",
        synced="[00:01.00] Existing",
    )

    client = make_netease_client([])

    with patch(
        "ytmusic_dl.lyrics.httpx.Client",
        return_value=client,
    ):
        provider = NetEaseProvider()

    hydrated = provider.fetch_lyrics(result)

    assert hydrated is result
    client.get.assert_not_called()

class _HydratingProvider:
    """Provider stub that hydrates candidates on demand."""

    name = "netease"

    def fetch_lyrics(self, result: LyricsResult) -> LyricsResult:
        return replace(
            result,
            synced_lyrics="[00:01.00] Lazy lyrics",
        )

def test_find_best_lyrics_hydrates_selected_candidate() -> None:
    """Fetch lyrics for the winner when providers return metadata only."""

    result = make_result(provider="netease")

    with patch(
        "ytmusic_dl.lyrics.service.PROVIDERS",
        (_HydratingProvider(),),
    ):
        best = find_best_lyrics(
            make_track(),
            [result],
        )

    assert best is not None
    assert best.synced_lyrics == "[00:01.00] Lazy lyrics"

    # The original metadata-only result is not mutated.
    assert result.synced_lyrics is None

def test_fetch_missing_lyrics_keeps_existing_content() -> None:
    """Skip hydration when the result already has lyrics."""

    result = make_result(
        synced="[00:01.00] Existing",
    )

    with patch(
        "ytmusic_dl.lyrics.service.PROVIDERS",
        (_HydratingProvider(),),
    ):
        hydrated = fetch_missing_lyrics(result)

    assert hydrated is result

def test_build_netease_search_terms_strips_video_noise() -> None:
    """Remove video and remaster noise from NetEase searches."""

    track = Track(
        playlist_index=1,
        title=(
            "Rick Astley - Never Gonna Give You Up "
            "(Official Video) (4K Remaster)"
        ),
        artist="Rick Astley",
        duration=213,
    )

    terms = _build_netease_search_terms(track)

    assert "Rick Astley - Never Gonna Give You Up" in terms
    assert "Never Gonna Give You Up" in terms

    for term in terms:
        lowered = term.lower()

        assert "official" not in lowered
        assert "4k" not in lowered
        assert "()" not in term

def test_build_netease_search_terms_keeps_bilingual_brackets() -> None:
    """Keep meaningful bracket content while removing noise."""

    track = Track(
        playlist_index=1,
        title=(
            "蘇打綠 sodagreen"
            "【博物館 The Museum】"
            "（蘇打綠版）"
            "Official Music Video"
        ),
        artist="sodagreen",
        duration=276,
    )

    terms = _build_netease_search_terms(track)

    assert "博物館 The Museum" in terms

    for term in terms:
        assert "official" not in term.lower()

def test_build_netease_search_terms_caps_requests() -> None:
    """Never build more than the request cap."""

    track = Track(
        playlist_index=1,
        title="A - B (C) [D] 【E】 F (G)",
        artist="A",
    )

    terms = _build_netease_search_terms(track)

    assert 0 < len(terms) <= MAX_SEARCH_TERMS

def test_build_netease_search_terms_empty_title() -> None:
    """Return no search terms for an empty title."""

    track = Track(playlist_index=1, title="   ")

    assert _build_netease_search_terms(track) == []
