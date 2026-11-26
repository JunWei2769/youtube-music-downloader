from ytmusic_dl.utils import (
    build_lyrics_filename,
    sanitize_filename,
)

def test_sanitize_filename_replaces_invalid_characters() -> None:
    """Replace characters that are unsafe for filenames."""

    assert sanitize_filename('a/b:c*?"') == "a_b_c___"

def test_build_lyrics_filename_with_artist() -> None:
    """Prefix standalone lyrics files with the artist."""

    assert build_lyrics_filename(
        "空耳 + 还你茉莉 (Live)",
        "单依纯",
    ) == "单依纯 - 空耳 + 还你茉莉 (Live)"

def test_build_lyrics_filename_without_artist() -> None:
    """Omit the artist prefix when no artist is known."""

    assert build_lyrics_filename("Test/Song") == "Test_Song"
