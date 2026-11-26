import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from ytmusic_dl.gui.environment import ToolStatus
from ytmusic_dl.gui.lyrics_tab import COLUMNS, LyricsTab
from ytmusic_dl.gui.window import MainWindow
from ytmusic_dl.models import (
    LyricsCandidate,
    LyricsQuery,
    LyricsResult,
)

TOOLS = {
    "ffmpeg": ToolStatus(
        name="ffmpeg",
        path="/usr/bin/ffmpeg",
        version="ffmpeg version test",
    ),
    "ffprobe": ToolStatus(
        name="ffprobe",
        path="/usr/bin/ffprobe",
        version="ffprobe version test",
    ),
    "deno": ToolStatus(name="deno"),
}

@pytest.fixture(scope="module")
def qt_app():
    """Provide a single offscreen QApplication."""

    app = QApplication.instance() or QApplication([])

    yield app

def make_candidate(
    *,
    confidence: str = "high",
    score: float = 1.15,
    synced: str | None = "[00:01.00] Test lyrics",
    rejection_reasons: list[str] | None = None,
) -> LyricsCandidate:
    """Create a candidate for interface tests."""

    return LyricsCandidate(
        result=LyricsResult(
            provider="lrclib",
            provider_id="1",
            track_name="Test Song",
            artist_name="Test Artist",
            album_name="Test Album",
            duration=200,
            instrumental=False,
            synced_lyrics=synced,
            plain_lyrics=None,
        ),
        score=score,
        confidence=confidence,
        match_reasons=["title matches", "artist matches"],
        rejection_reasons=(
            [] if rejection_reasons is None else rejection_reasons
        ),
    )

def test_main_window_has_three_tabs(qt_app) -> None:
    """Build the main window with the expected tabs."""

    with patch(
        "ytmusic_dl.gui.window.detect_tools",
        return_value=TOOLS,
    ):
        window = MainWindow()

    assert window.tabs.count() == 3

    assert [
        window.tabs.tabText(index)
        for index in range(window.tabs.count())
    ] == [
        "Music Download",
        "Lyrics Only",
        "Settings",
    ]

    window.close()

    assert qt_app is not None

def test_lyrics_tab_has_expected_columns(qt_app) -> None:
    """Show provider, score, and confidence columns."""

    tab = LyricsTab()

    assert tab.table.columnCount() == len(COLUMNS)
    assert tab.table.horizontalHeaderItem(1).text() == (
        "Confidence"
    )
    assert tab.table.horizontalHeaderItem(7).text() == "Score"

    tab.close()

    assert qt_app is not None

def test_lyrics_tab_populates_candidates(qt_app) -> None:
    """Populate the table and preview from search results."""

    tab = LyricsTab()

    query = LyricsQuery(
        title="Test Song",
        artist="Test Artist",
    )

    tab._apply_results(
        query,
        [make_candidate()],
    )

    assert tab.table.rowCount() == 1
    assert tab.table.item(0, 1).text() == "high"
    assert tab.table.item(0, 3).text() == "Test Song"
    assert tab.table.item(0, 7).text() == "1.15"

    assert tab.save_button.isEnabled()
    assert "[00:01.00] Test lyrics" in (
        tab.preview.toPlainText()
    )

    tab.close()

    assert qt_app is not None

def test_lyrics_tab_rejects_rejected_candidates(qt_app) -> None:
    """Rejected candidates cannot be saved."""

    tab = LyricsTab()

    tab._apply_results(
        LyricsQuery(
            title="Test Song",
            artist="Test Artist",
        ),
        [
            make_candidate(
                confidence="low",
                score=0.50,
                rejection_reasons=["artist does not match"],
            )
        ],
    )

    assert tab.table.item(0, 1).text() == "rejected"
    assert not tab.save_button.isEnabled()
    assert "Rejected:" in tab.detail_label.text()

    tab.close()

    assert qt_app is not None

def test_lyrics_tab_handles_empty_results(qt_app) -> None:
    """Report when no candidates were found."""

    tab = LyricsTab()

    tab._apply_results(
        LyricsQuery(
            title="Test Song",
            artist="Test Artist",
        ),
        [],
    )

    assert tab.table.rowCount() == 0
    assert "No lyrics candidates" in tab.status_label.text()
    assert not tab.save_button.isEnabled()

    tab.close()

    assert qt_app is not None
