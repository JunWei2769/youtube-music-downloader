import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ytmusic_dl.gui.environment import (
    ToolStatus,
    detect_tools,
    extend_path_with_tools,
    find_tool,
    install_hint,
)

def test_find_tool_uses_explicit_path(tmp_path: Path) -> None:
    """Find and version an executable at an explicit location."""

    script = tmp_path / "fake-tool"
    script.write_text(
        "#!/bin/sh\necho 'fake-tool 1.2.3'\n",
        encoding="utf-8",
    )
    script.chmod(0o755)

    status = find_tool(
        "fake-tool",
        extra_paths=(script,),
        version_arguments=("-version",),
    )

    assert status.available
    assert status.path == str(script)
    assert status.version == "fake-tool 1.2.3"

def test_find_tool_missing() -> None:
    """Report a tool as unavailable when it cannot be found."""

    status = find_tool("definitely-not-installed-xyz")

    assert not status.available
    assert status.path is None

def test_detect_tools_reports_required_tools() -> None:
    """Always report ffmpeg, ffprobe, and deno."""

    tools = detect_tools()

    assert set(tools) == {"ffmpeg", "ffprobe", "deno"}

    for name, status in tools.items():
        assert status.name == name

def test_extend_path_with_tools(monkeypatch, tmp_path: Path) -> None:
    """Add detected tool directories to PATH once."""

    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()

    tools = {
        "ffmpeg": ToolStatus(
            "ffmpeg",
            str(tools_dir / "ffmpeg"),
            "ffmpeg version test",
        ),
        "ffprobe": ToolStatus(
            "ffprobe",
            str(tools_dir / "ffprobe"),
            "ffprobe version test",
        ),
        "deno": ToolStatus(
            "deno",
            str(tools_dir / "deno"),
            "deno test",
        ),
    }

    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    with patch(
        "ytmusic_dl.gui.environment.detect_tools",
        return_value=tools,
    ):
        extend_path_with_tools()

    entries = os.environ["PATH"].split(os.pathsep)

    assert entries[0] == str(tools_dir)
    assert entries.count(str(tools_dir)) == 1
    assert "/usr/bin" in entries

@pytest.mark.parametrize(
    ("system", "name", "expected"),
    [
        ("Darwin", "ffmpeg", "brew install ffmpeg"),
        ("Darwin", "ffprobe", "brew install ffmpeg"),
        ("Darwin", "deno", "brew install deno"),
        ("Linux", "ffmpeg", "sudo dnf install ffmpeg"),
        ("Windows", "deno", "winget install DenoLand.Deno"),
        ("Darwin", "unknown-tool", None),
    ],
)
def test_install_hint(system, name, expected) -> None:
    """Return platform-specific install commands."""

    with patch(
        "ytmusic_dl.gui.environment.platform.system",
        return_value=system,
    ):
        assert install_hint(name) == expected
