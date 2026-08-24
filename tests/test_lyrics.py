from pathlib import Path
from unittest.mock import MagicMock, patch

from ytmusic_dl.lyrics import (
    NetEaseProvider,
    _build_netease_search_terms,
    _duration_is_acceptable,
    _normalize_text,
    _parse_netease_result,
    _similarity,
    find_best_lyrics,
    write_lyrics,
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


def test_duration_is_acceptable() -> None:
    assert _duration_is_acceptable(
        200,
        202,
    )

    assert _duration_is_acceptable(
        200,
        210,
    )

    assert not _duration_is_acceptable(
        200,
        211,
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


def test_netease_search_filters_wrong_duration() -> None:
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

    assert len(results) == 1

    result = results[0]

    assert result.provider == "netease"
    assert result.provider_id == "1"
    assert result.duration == 200.0
    assert result.synced_lyrics == "[00:01.00] Test lyrics"

    assert mock_client.get.call_count == 2
    assert mock_client.post.call_count == 1

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
