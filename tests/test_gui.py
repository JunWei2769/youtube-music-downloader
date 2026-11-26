import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from ytmusic_dl.gui.environment import ToolStatus
from ytmusic_dl.gui.window import MainWindow

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

def test_main_window_has_three_tabs() -> None:
    """Build the main window with the expected tabs."""

    app = QApplication.instance() or QApplication([])

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

    assert app is not None
