from ytmusic_dl.utils import (
    build_lyrics_filename,
    sanitize_filename,
    strip_artist_prefix,
)

def test_sanitize_filename_replaces_invalid_characters() -> None:
    """Replace characters that are unsafe for filenames."""

    assert sanitize_filename('a/b:c*?"') == "a_b_c___"

def test_strip_artist_prefix_removes_duplicate_artist() -> None:
    """Remove a leading artist repeated in a YouTube title."""

    assert strip_artist_prefix(
        "Rick Astley - Never Gonna Give You Up",
        "Rick Astley",
    ) == "Never Gonna Give You Up"

def test_strip_artist_prefix_is_case_insensitive() -> None:
    """Match the artist prefix without case sensitivity."""

    assert strip_artist_prefix(
        "RICK ASTLEY - Never Gonna Give You Up",
        "Rick Astley",
    ) == "Never Gonna Give You Up"

def test_strip_artist_prefix_supports_unicode_dashes() -> None:
    """Handle en and em dashes as separators."""

    assert strip_artist_prefix(
        "單依純 – 空耳",
        "單依純",
    ) == "空耳"

def test_strip_artist_prefix_keeps_clean_titles() -> None:
    """Leave titles that do not repeat the artist alone."""

    assert strip_artist_prefix("Test Song", "Test Artist") == (
        "Test Song"
    )

    assert strip_artist_prefix(
        "Test Artist - Test Song",
        None,
    ) == "Test Artist - Test Song"

def test_build_lyrics_filename_with_artist() -> None:
    """Prefix standalone lyrics files with the artist."""

    assert build_lyrics_filename(
        "空耳 + 还你茉莉 (Live)",
        "单依纯",
    ) == "单依纯 - 空耳 + 还你茉莉 (Live)"

def test_build_lyrics_filename_without_artist() -> None:
    """Omit the artist prefix when no artist is known."""

    assert build_lyrics_filename("Test/Song") == "Test_Song"
