"""
Purpose: Locate external tools for the desktop application.

- FFmpeg and FFprobe discovery
- Deno discovery
- PATH-independent fallback locations

Responsibility: Environment detection
"""

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

VERSION_ARGUMENTS = {
    "ffmpeg": ("-version",),
    "ffprobe": ("-version",),
    "deno": ("--version",),
}

@dataclass(frozen=True)
class ToolStatus:
    """Location and version of an external tool."""

    name: str
    path: str | None = None
    version: str | None = None

    @property
    def available(self) -> bool:
        """Return whether the tool was found."""

        return self.path is not None

def _fallback_paths(name: str) -> list[Path]:
    """Return common install locations outside PATH."""

    home = Path.home()
    executable = f"{name}.exe" if os.name == "nt" else name

    if name == "deno":
        paths = [
            home / ".deno" / "bin" / executable,
        ]
    else:
        paths = []

    if os.name == "nt":
        paths.extend(
            [
                Path("C:/ffmpeg/bin") / executable,
                home / "scoop" / "shims" / executable,
            ]
        )
    else:
        paths.extend(
            [
                Path("/opt/homebrew/bin") / executable,
                Path("/usr/local/bin") / executable,
                Path("/usr/bin") / executable,
                Path("/snap/bin") / executable,
            ]
        )

    return paths

def _read_version(
    path: Path,
    arguments: tuple[str, ...],
) -> str | None:
    """Run a tool's version command and return its first line."""

    if not arguments:
        return None

    try:
        result = subprocess.run(
            [str(path), *arguments],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    output = (result.stdout or result.stderr).strip()

    if not output:
        return None

    return output.splitlines()[0]

def find_tool(
    name: str,
    *,
    extra_paths: tuple[Path, ...] = (),
    version_arguments: tuple[str, ...] | None = None,
) -> ToolStatus:
    """Find a tool on PATH, in known locations, or explicitly."""

    candidates: list[Path] = []

    on_path = shutil.which(name)

    if on_path:
        candidates.append(Path(on_path))

    candidates.extend(Path(path) for path in extra_paths)
    candidates.extend(_fallback_paths(name))

    arguments = (
        VERSION_ARGUMENTS.get(name, ())
        if version_arguments is None
        else version_arguments
    )

    for candidate in candidates:
        path = candidate.expanduser()

        if not path.is_file() or not os.access(path, os.X_OK):
            continue

        return ToolStatus(
            name=name,
            path=str(path),
            version=_read_version(path, arguments),
        )

    return ToolStatus(name=name)

def detect_tools() -> dict[str, ToolStatus]:
    """Detect the tools required by the application."""

    return {
        name: find_tool(name)
        for name in ("ffmpeg", "ffprobe", "deno")
    }

def install_hint(name: str) -> str | None:
    """Return a platform-specific install command for a tool."""

    system = platform.system()

    if name in {"ffmpeg", "ffprobe"}:
        if system == "Darwin":
            return "brew install ffmpeg"

        if system == "Linux":
            return "sudo dnf install ffmpeg"

        if system == "Windows":
            return "winget install Gyan.FFmpeg.Shared"

        return None

    if name == "deno":
        if system == "Darwin":
            return "brew install deno"

        if system == "Linux":
            return "sudo dnf install deno"

        if system == "Windows":
            return "winget install DenoLand.Deno"

        return None

    return None

def extend_path_with_tools() -> None:
    """Prepend detected tool directories to PATH.

    Desktop launches, especially from Finder, often do not inherit the
    shell's PATH. Adding the detected directories keeps FFmpeg, FFprobe,
    and Deno available to yt-dlp and the pipeline.
    """

    directories: list[str] = []

    for status in detect_tools().values():
        if not status.path:
            continue

        directory = str(Path(status.path).parent)

        if directory not in directories:
            directories.append(directory)

    if not directories:
        return

    current = os.environ.get("PATH", "")
    existing = current.split(os.pathsep) if current else []
    missing = [
        directory
        for directory in directories
        if directory not in existing
    ]

    if missing:
        os.environ["PATH"] = os.pathsep.join(
            missing + existing
        )
