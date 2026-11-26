from pathlib import Path
from unittest.mock import patch

import pytest

from ytmusic_dl.cli_lyrics import (
    build_lyrics_parser,
    run_lyrics_command,
)
from ytmusic_dl.models import (
    LyricsCandidate,
    LyricsResult,
    Track,
)

def make_candidate(
    *,
    provider: str = "lrclib",
    title: str = "Test Song",
    artist: str = "Test Artist",
    score: float = 1.0,
    confidence: str = "high",
    synced: str | None = "[00:01.00] Test lyrics",
    plain: str | None = None,
    match_reasons: list[str] | None = None,
    rejection_reasons: list[str] | None = None,
) -> LyricsCandidate:
    """Create a scored candidate for CLI tests."""

    return LyricsCandidate(
        result=LyricsResult(
            provider=provider,
            provider_id="1",
            track_name=title,
            artist_name=artist,
            album_name="Test Album",
            duration=200,
            instrumental=False,
            synced_lyrics=synced,
            plain_lyrics=plain,
        ),
        score=score,
        confidence=confidence,
        match_reasons=(
            ["title matches", "artist matches"]
            if match_reasons is None
            else match_reasons
        ),
        rejection_reasons=(
            [] if rejection_reasons is None else rejection_reasons
        ),
    )

def test_lyrics_parser_search() -> None:
    """Parse a lyrics search command."""

    args = build_lyrics_parser().parse_args(
        [
            "search",
            "Test Song",
            "--artist",
            "Test Artist",
            "--album",
            "Test Album",
            "--duration",
            "200",
        ]
    )

    assert args.action == "search"
    assert args.query == "Test Song"
    assert args.artist == "Test Artist"
    assert args.album == "Test Album"
    assert args.duration == 200.0

def test_lyrics_parser_download_requires_selection() -> None:
    """Require --best or --select for lyrics download."""

    with pytest.raises(SystemExit):
        build_lyrics_parser().parse_args(
            ["download", "Test Song", "--artist", "Test Artist"]
        )

def test_lyrics_search_requires_artist_for_titles() -> None:
    """Reject title searches that do not name an artist."""

    with pytest.raises(SystemExit):
        run_lyrics_command(["search", "Test Song"])

def test_lyrics_search_prints_candidates(capsys) -> None:
    """Print scored candidates with reasons."""

    candidates = [make_candidate()]

    with patch(
        "ytmusic_dl.cli_lyrics.search_candidates",
        return_value=candidates,
    ):
        exit_code = run_lyrics_command(
            ["search", "Test Song", "--artist", "Test Artist"]
        )

    assert exit_code == 0

    output = capsys.readouterr().out

    assert "1. [high] lrclib" in output
    assert "Score:    1.00" in output
    assert "title matches; artist matches" in output

def test_lyrics_search_uses_url_metadata(capsys) -> None:
    """Extract metadata from a URL without downloading audio."""

    track = Track(
        playlist_index=1,
        title="URL Song",
        artist="URL Artist",
        album="URL Album",
        duration=180,
        video_id="abc123",
        webpage_url="https://music.youtube.com/watch?v=abc123",
        playlist_name="URL Song",
    )

    with (
        patch(
            "ytmusic_dl.cli_lyrics.extract_single_track",
            return_value=[track],
        ) as mock_extract,
        patch(
            "ytmusic_dl.cli_lyrics.search_candidates",
            return_value=[make_candidate(title="URL Song")],
        ) as mock_search,
    ):
        exit_code = run_lyrics_command(
            [
                "search",
                "https://music.youtube.com/watch?v=abc123",
            ]
        )

    assert exit_code == 0

    mock_extract.assert_called_once()

    query = mock_search.call_args.args[0]

    assert query.title == "URL Song"
    assert query.artist == "URL Artist"
    assert query.album == "URL Album"
    assert query.duration == 180

    assert "URL Song" in capsys.readouterr().out

def test_lyrics_download_best_saves_file(
    tmp_path: Path,
    capsys,
) -> None:
    """Save the best candidate as an .lrc file."""

    with patch(
        "ytmusic_dl.cli_lyrics.search_candidates",
        return_value=[make_candidate()],
    ):
        exit_code = run_lyrics_command(
            [
                "download",
                "Test Song",
                "--artist",
                "Test Artist",
                "--best",
                "--output",
                str(tmp_path),
            ]
        )

    assert exit_code == 0

    output_path = tmp_path / "Test Artist - Test Song.lrc"

    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == (
        "[00:01.00] Test lyrics"
    )

    output = capsys.readouterr().out

    assert f"Saved:      {output_path}" in output
    assert "Provider:   lrclib" in output
    assert "Confidence: high" in output

def test_lyrics_download_enforces_min_confidence(
    tmp_path: Path,
    capsys,
) -> None:
    """Refuse --best when confidence is below the floor."""

    candidate = make_candidate(
        score=0.80,
        confidence="medium",
    )

    with patch(
        "ytmusic_dl.cli_lyrics.search_candidates",
        return_value=[candidate],
    ):
        exit_code = run_lyrics_command(
            [
                "download",
                "Test Song",
                "--artist",
                "Test Artist",
                "--best",
                "--min-confidence",
                "high",
                "--output",
                str(tmp_path),
            ]
        )

    assert exit_code == 1
    assert not (tmp_path / "Test Artist - Test Song.lrc").exists()

    assert "below --min-confidence high" in capsys.readouterr().out

def test_lyrics_download_selects_by_index(
    tmp_path: Path,
    capsys,
) -> None:
    """Save a specific candidate with --select."""

    first = make_candidate(
        provider="lrclib",
        score=1.10,
        synced="[00:01.00] First lyrics",
    )

    second = make_candidate(
        provider="netease",
        score=0.95,
        synced="[00:02.00] Second lyrics",
    )

    with patch(
        "ytmusic_dl.cli_lyrics.search_candidates",
        return_value=[second, first],
    ):
        exit_code = run_lyrics_command(
            [
                "download",
                "Test Song",
                "--artist",
                "Test Artist",
                "--select",
                "2",
                "--output",
                str(tmp_path),
            ]
        )

    assert exit_code == 0

    output_path = tmp_path / "Test Artist - Test Song.lrc"

    assert output_path.read_text(encoding="utf-8") == (
        "[00:02.00] Second lyrics"
    )

    assert "Provider:   netease" in capsys.readouterr().out

def test_lyrics_download_rejects_selected_rejected_candidate(
    tmp_path: Path,
    capsys,
) -> None:
    """Refuse to save a candidate that failed the checks."""

    candidate = make_candidate(
        rejection_reasons=["artist does not match"],
    )

    with patch(
        "ytmusic_dl.cli_lyrics.search_candidates",
        return_value=[candidate],
    ):
        exit_code = run_lyrics_command(
            [
                "download",
                "Test Song",
                "--artist",
                "Test Artist",
                "--select",
                "1",
                "--output",
                str(tmp_path),
            ]
        )

    assert exit_code == 1
    assert not (tmp_path / "Test Artist - Test Song.lrc").exists()

    assert "the selected candidate was rejected" in (
        capsys.readouterr().out
    )

def test_lyrics_download_protects_existing_file(
    tmp_path: Path,
    capsys,
) -> None:
    """Do not overwrite an existing lyrics file by default."""

    output_path = tmp_path / "Test Artist - Test Song.lrc"
    output_path.write_text("old lyrics", encoding="utf-8")

    with patch(
        "ytmusic_dl.cli_lyrics.search_candidates",
        return_value=[make_candidate()],
    ):
        exit_code = run_lyrics_command(
            [
                "download",
                "Test Song",
                "--artist",
                "Test Artist",
                "--best",
                "--output",
                str(tmp_path),
            ]
        )

    assert exit_code == 0
    assert output_path.read_text(encoding="utf-8") == "old lyrics"
    assert "Use --overwrite to replace it." in capsys.readouterr().out

def test_lyrics_download_overwrites_when_asked(
    tmp_path: Path,
) -> None:
    """Replace an existing lyrics file with --overwrite."""

    output_path = tmp_path / "Test Artist - Test Song.lrc"
    output_path.write_text("old lyrics", encoding="utf-8")

    with patch(
        "ytmusic_dl.cli_lyrics.search_candidates",
        return_value=[make_candidate()],
    ):
        exit_code = run_lyrics_command(
            [
                "download",
                "Test Song",
                "--artist",
                "Test Artist",
                "--best",
                "--overwrite",
                "--output",
                str(tmp_path),
            ]
        )

    assert exit_code == 0
    assert output_path.read_text(encoding="utf-8") == (
        "[00:01.00] Test lyrics"
    )

def test_lyrics_download_without_candidates(
    tmp_path: Path,
    capsys,
) -> None:
    """Fail cleanly when no provider returns a candidate."""

    with patch(
        "ytmusic_dl.cli_lyrics.search_candidates",
        return_value=[],
    ):
        exit_code = run_lyrics_command(
            [
                "download",
                "Test Song",
                "--artist",
                "Test Artist",
                "--best",
                "--output",
                str(tmp_path),
            ]
        )

    assert exit_code == 1
    assert "No lyrics candidates found." in capsys.readouterr().out
