import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QLabel

from ytmusic_dl.downloader import AUDIO_FORMATS
from ytmusic_dl.gui.download_tab import DownloadTab
from ytmusic_dl.gui.environment import ToolStatus
from ytmusic_dl.gui.lyrics_tab import COLUMNS, LyricsTab
from ytmusic_dl.gui.window import SettingsTab
from ytmusic_dl.gui.window import MainWindow
from ytmusic_dl.models import (
    DownloadProgress,
    LyricsCandidate,
    LyricsQuery,
    LyricsResult,
    PlaylistResult,
    Track,
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

@pytest.fixture
def app_settings(tmp_path):
    """Provide an isolated QSettings store."""

    return QSettings(
        str(tmp_path / "settings.ini"),
        QSettings.Format.IniFormat,
    )

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

def test_main_window_has_three_tabs(qt_app, app_settings) -> None:
    """Build the main window with the expected tabs."""

    with patch(
        "ytmusic_dl.gui.window.detect_tools",
        return_value=TOOLS,
    ):
        window = MainWindow(settings=app_settings)

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

def test_lyrics_tab_has_expected_columns(qt_app, app_settings) -> None:
    """Show provider, score, and confidence columns."""

    tab = LyricsTab(settings=app_settings)

    assert tab.table.columnCount() == len(COLUMNS)
    assert tab.table.horizontalHeaderItem(1).text() == (
        "Confidence"
    )
    assert tab.table.horizontalHeaderItem(7).text() == "Score"

    tab.close()

    assert qt_app is not None

def test_lyrics_tab_populates_candidates(qt_app, app_settings) -> None:
    """Populate the table and preview from search results."""

    tab = LyricsTab(settings=app_settings)

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

def test_lyrics_tab_rejects_rejected_candidates(qt_app, app_settings) -> None:
    """Rejected candidates cannot be saved."""

    tab = LyricsTab(settings=app_settings)

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

def test_lyrics_tab_handles_empty_results(qt_app, app_settings) -> None:
    """Report when no candidates were found."""

    tab = LyricsTab(settings=app_settings)

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

def test_download_tab_lists_all_formats(qt_app, app_settings) -> None:
    """Offer every audio format, including source."""

    tab = DownloadTab(settings=app_settings)

    values = [
        tab.format_combo.itemData(index)
        for index in range(tab.format_combo.count())
    ]

    assert values == list(AUDIO_FORMATS)
    assert tab.browser_combo.itemData(0) is None
    assert not tab.cancel_button.isEnabled()

    tab.close()

    assert qt_app is not None

def test_download_tab_reports_progress(qt_app, app_settings) -> None:
    """Update the progress bar and label from worker signals."""

    tab = DownloadTab(settings=app_settings)
    track = Track(
        playlist_index=1,
        title="Test Song",
        artist="Test Artist",
    )

    tab._on_progress(
        track,
        DownloadProgress(percent=42.0, stage="download"),
        1,
        3,
    )

    assert tab.progress_bar.value() == 42
    assert "track 1 of 3" in tab.progress_label.text()

    tab._on_progress(
        track,
        DownloadProgress(stage="postprocess"),
        3,
        3,
    )

    assert tab.progress_bar.maximum() == 0
    assert "Converting" in tab.progress_label.text()

    tab.close()

    assert qt_app is not None

def test_download_tab_summarises_results(qt_app, app_settings) -> None:
    """Show the summary and failed tracks after a run."""

    tab = DownloadTab(settings=app_settings)

    tab._on_log("Processing: Test Song")

    result = PlaylistResult(
        total=2,
        successful=1,
        failed=1,
        lyrics=1,
        thumbnails=1,
        output_directory=Path("downloads/test"),
        failed_tracks=["02 - Other Song: boom"],
        skipped=0,
    )

    tab._on_completed(result)

    summary = tab.summary_label.text()

    assert "Complete" in summary
    assert "1 successful" in summary
    assert "1 failed" in summary
    assert "downloads/test" in summary

    log = tab.log_view.toPlainText()

    assert "Processing: Test Song" in log
    assert "Failed tracks:" in log
    assert "02 - Other Song: boom" in log

    tab.close()

    assert qt_app is not None

def test_download_tab_persists_settings(
    qt_app,
    app_settings,
    tmp_path,
) -> None:
    """Restore download defaults from QSettings."""

    tab = DownloadTab(settings=app_settings)

    tab.output_input.setText(str(tmp_path / "music"))
    tab.format_combo.setCurrentIndex(
        tab.format_combo.findData("m4a")
    )
    tab.browser_combo.setCurrentIndex(
        tab.browser_combo.findData("chrome")
    )
    tab.lyrics_check.setChecked(False)
    tab.thumbnail_check.setChecked(False)
    tab.confidence_combo.setCurrentIndex(
        tab.confidence_combo.findData("medium")
    )

    tab.save_state()

    restored = DownloadTab(settings=app_settings)

    assert restored.output_input.text() == str(
        tmp_path / "music"
    )
    assert restored.format_combo.currentData() == "m4a"
    assert restored.browser_combo.currentData() == "chrome"
    assert not restored.lyrics_check.isChecked()
    assert not restored.thumbnail_check.isChecked()
    assert (
        restored.confidence_combo.currentData() == "medium"
    )

    restored.close()

    assert qt_app is not None

def test_lyrics_tab_persists_output(
    qt_app,
    app_settings,
    tmp_path,
) -> None:
    """Restore the lyrics output directory."""

    tab = LyricsTab(settings=app_settings)
    tab.output_input.setText(str(tmp_path / "lyrics"))
    tab.save_state()

    restored = LyricsTab(settings=app_settings)

    assert restored.output_input.text() == str(
        tmp_path / "lyrics"
    )

    restored.close()

    assert qt_app is not None

def test_settings_tab_shows_install_hint(qt_app) -> None:
    """Show an install command for missing tools."""

    tools = {
        "ffmpeg": ToolStatus(name="ffmpeg"),
        "ffprobe": ToolStatus(name="ffprobe"),
        "deno": ToolStatus(name="deno"),
    }

    with (
        patch(
            "ytmusic_dl.gui.window.detect_tools",
            return_value=tools,
        ),
        patch(
            "ytmusic_dl.gui.window.install_hint",
            return_value="brew install ffmpeg",
        ),
    ):
        tab = SettingsTab()

    texts = [
        label.text()
        for label in tab.findChildren(QLabel)
    ]

    assert any(
        "brew install ffmpeg" in text
        for text in texts
    )

    tab.close()

    assert qt_app is not None
