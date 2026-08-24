from pathlib import Path
from unittest.mock import MagicMock, patch

from ytmusic_dl.lyrics import (
    NetEaseProvider,
    _duration_is_acceptable,
    _normalize_text,
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
        "result": {
            "songs": [
                {
                    "id": 1,
                    "name": "Test Song",
                    "artists": [
                        {"name": "Test Artist"}
                    ],
                    "album": {
                        "name": "Test Album"
                    },
                    "duration": 200000,
                },
                {
                    "id": 2,
                    "name": "Test Song",
                    "artists": [
                        {"name": "Test Artist"}
                    ],
                    "album": {
                        "name": "Test Album"
                    },
                    "duration": 350000,
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
    mock_client.get.side_effect = [
        discover_response,
        search_response,
        lyrics_response,
    ]

    with patch(
        "ytmusic_dl.lyrics.httpx.Client",
        return_value=mock_client,
    ):
        provider = NetEaseProvider()

        # Creating the provider must not perform network I/O.
        mock_client.get.assert_not_called()
        assert provider.initialized is False

        results = provider.search(track)

    assert provider.initialized is True

    assert len(results) == 1

    result = results[0]

    assert result.provider == "netease"
    assert result.provider_id == "1"
    assert result.duration == 200.0
    assert result.synced_lyrics == "[00:01.00] Test lyrics"

    assert mock_client.get.call_count == 3

def test_netease_provider_reuses_initialized_session() -> None:
    track = make_track()

    discover_response = MagicMock()
    discover_response.raise_for_status.return_value = None

    search_response = MagicMock()
    search_response.raise_for_status.return_value = None
    search_response.json.return_value = {
        "result": {
            "songs": []
        }
    }

    mock_client = MagicMock()
    mock_client.get.side_effect = (
        lambda *args, **kwargs: (
            discover_response
            if args[0] == "https://music.163.com/discover"
            else search_response
        )
    )

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
    assert mock_client.get.call_count == 5

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
