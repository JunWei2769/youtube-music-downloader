import atexit
import os
import platform
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from yt_dlp import YoutubeDL

CHROMIUM_BROWSERS = {
    "vivaldi",
    "chrome",
    "chromium",
    "brave",
    "edge",
    "opera",
    "whale",
}

FIREFOX_BROWSERS = {
    "firefox",
}

# yt-dlp searches a browser profile recursively for a file named
# "Cookies" and picks the newest one. Chrome extensions keep their own
# cookie databases under Storage/ext, which can be newer than the
# profile database. These caches point yt-dlp at a temporary profile
# that contains only the primary database.
#
# The snapshot is refreshed when the source database changes or when it
# is older than the TTL, so long-running GUI sessions do not keep using
# stale cookies.
_COOKIE_PROFILE_TTL_SECONDS = 300

_CookieCacheEntry = tuple[
    str,
    float,
    int,
    tempfile.TemporaryDirectory,
]

_COOKIE_PROFILE_CACHE: dict[str, _CookieCacheEntry] = {}
_COOKIE_TEMP_DIRS: list[tempfile.TemporaryDirectory] = []


def _cleanup_cookie_temp_dirs() -> None:
    """Remove every temporary cookie profile."""

    for temp_dir in _COOKIE_TEMP_DIRS:
        temp_dir.cleanup()

    _COOKIE_TEMP_DIRS.clear()
    _COOKIE_PROFILE_CACHE.clear()


atexit.register(_cleanup_cookie_temp_dirs)


@dataclass(frozen=True)
class BrowserProfile:
    """Detected browser profile information."""

    name: str
    path: Path


def _detect_chromium_profiles(browser_path: Path) -> list[Path]:
    """Detect Chromium-based browser profiles containing cookies."""

    profiles: list[Path] = []

    candidates = [
        browser_path / "Default",
        *browser_path.glob("Profile *"),
    ]

    for profile in candidates:
        if not profile.is_dir():
            continue

        cookie_files = [
            profile / "Cookies",
            profile / "Network" / "Cookies",
        ]

        if any(cookie_file.is_file() for cookie_file in cookie_files):
            profiles.append(profile)

    return profiles

def _detect_firefox_profiles(browser_path: Path) -> list[Path]:
    """Detect Firefox profiles containing cookies."""

    profiles_ini = browser_path / "profiles.ini"

    if not profiles_ini.is_file():
        return []

    profiles: list[Path] = []
    current_profile: dict[str, str] = {}

    for line in profiles_ini.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line:
            continue

        if line.startswith("["):
            if current_profile:
                profile_path = _get_firefox_profile_path(
                    browser_path,
                    current_profile,
                )

                if profile_path is not None:
                    profiles.append(profile_path)

            current_profile = {}
            continue

        if "=" in line:
            key, value = line.split("=", 1)
            current_profile[key] = value

    if current_profile:
        profile_path = _get_firefox_profile_path(
            browser_path,
            current_profile,
        )

        if profile_path is not None:
            profiles.append(profile_path)

    return profiles

def _get_firefox_profile_path(
    browser_path: Path,
    profile: dict[str, str],
) -> Path | None:
    """Resolve a Firefox profile path from profiles.ini."""

    profile_path = profile.get("Path")

    if not profile_path:
        return None

    if profile.get("IsRelative") == "1":
        path = browser_path / profile_path
    else:
        path = Path(profile_path)

    cookie_file = path / "cookies.sqlite"

    if path.is_dir() and cookie_file.is_file():
        return path

    return None

def get_browser_path() -> dict[str, Path]:
    """Return possible browser profile locations for the current OS."""

    home = Path.home()
    system = platform.system()

    if system == "Linux":
        config = Path(
            os.environ.get("XDG_CONFIG_HOME", home / ".config")
        )

        return {
            "vivaldi": config / "vivaldi",
            "chrome": config / "google-chrome",
            "chromium": config / "chromium",
            "brave": config / "BraveSoftware" / "Brave-Browser",
            "firefox": Path(
                os.environ.get("XDG_CONFIG_HOME", home / ".config")
            ) / "mozilla" / "firefox",
            "edge": config / "microsoft-edge",
            "opera": config / "opera",
            "whale": config / "naver-whale",
        }

    if system == "Darwin":
        config = home / "Library" / "Application Support"

        return {
            "chrome": config / "Google" / "Chrome",
            "chromium": config / "Chromium",
            "brave": config / "BraveSoftware" / "Brave-Browser",
            "vivaldi": config / "vivaldi",
            "firefox": home / "Library" / "Application Support" / "Firefox",
            "edge": config / "Microsoft Edge",
            "opera": config / "com.operasoftware.Opera",
            "whale": config / "Naver" / "Whale",
        }

    if system == "Windows":
        local_app_data = Path(
            os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")
        )
        roaming_app_data = Path(
            os.environ.get("APPDATA", home / "AppData" / "Roaming")
        )

        return {
            "chrome": local_app_data / "Google" / "Chrome" / "User Data",
            "chromium": local_app_data / "Chromium" / "User Data",
            "brave": (
                local_app_data
                / "BraveSoftware"
                / "Brave-Browser"
                / "User Data"
            ),
            "vivaldi": local_app_data / "Vivaldi" / "User Data",
            "firefox": roaming_app_data / "Mozilla" / "Firefox",
            "edge": local_app_data / "Microsoft" / "Edge" / "User Data",
            "opera": (
                roaming_app_data
                / "Opera Software"
                / "Opera Stable"
            ),
            "whale": local_app_data / "Naver" / "Whale" / "User Data",
        }

    raise RuntimeError(f"Unsupported operating system: {system}")

def detect_browser_profiles() -> list[BrowserProfile]:
    """Detect browsers with existing browser profiles."""

    browser_paths = get_browser_path()

    detected: list[BrowserProfile] = []

    for name, path in browser_paths.items():
        if not path.exists() or not path.is_dir():
            continue

        if name in FIREFOX_BROWSERS:
            profiles = _detect_firefox_profiles(path)
        elif name in CHROMIUM_BROWSERS:
            profiles = _detect_chromium_profiles(path)
        else:
            profiles = []

        for profile in profiles:
            detected.append(
                BrowserProfile(
                    name=name,
                    path=profile,
                )
            )

    return detected

def list_browsers() -> list[tuple[BrowserProfile, bool]]:
    """Return detected browser profiles and cookie availability."""

    browsers: list[tuple[BrowserProfile, bool]] = []

    for browser in detect_browser_profiles():
        browsers.append(
            (
                browser,
                _browser_has_usable_cookies(browser),
            )
        )

    return browsers

def _primary_cookie_database(
    profile_path: Path,
) -> Path | None:
    """Return the primary Chromium cookie database for a profile."""

    for relative in ("Network/Cookies", "Cookies"):
        candidate = profile_path / relative

        if candidate.is_file():
            return candidate

    return None

def _prepare_cookie_profile(
    browser: BrowserProfile,
) -> str:
    """Return a profile path containing only the primary cookie DB."""

    cache_key = str(browser.path)
    database = _primary_cookie_database(browser.path)

    if database is None:
        return str(browser.path)

    try:
        database_mtime = database.stat().st_mtime_ns
    except OSError:
        return str(browser.path)

    cached = _COOKIE_PROFILE_CACHE.get(cache_key)

    if cached is not None:
        cached_path, created_at, mtime, cached_temp_dir = cached
        is_fresh = (
            time.monotonic() - created_at
            < _COOKIE_PROFILE_TTL_SECONDS
        )

        if is_fresh and mtime == database_mtime:
            return cached_path

        _COOKIE_PROFILE_CACHE.pop(cache_key, None)

        if cached_temp_dir in _COOKIE_TEMP_DIRS:
            _COOKIE_TEMP_DIRS.remove(cached_temp_dir)

        cached_temp_dir.cleanup()

    temp_dir = tempfile.TemporaryDirectory(
        prefix="ytmusic_dl_cookies_"
    )

    root = Path(temp_dir.name)
    profile = root / browser.path.name
    profile.mkdir()

    shutil.copy2(database, profile / "Cookies")

    # Windows decrypts the cookie key from Local State next to the
    # profile directory, so the temporary layout mirrors Chrome's.
    if platform.system() == "Windows":
        local_state = browser.path.parent / "Local State"

        if local_state.is_file():
            shutil.copy2(
                local_state,
                root / "Local State",
            )

    _COOKIE_TEMP_DIRS.append(temp_dir)
    _COOKIE_PROFILE_CACHE[cache_key] = (
        str(profile),
        time.monotonic(),
        database_mtime,
        temp_dir,
    )

    return str(profile)

def get_ytdlp_cookie_options(
    browser: BrowserProfile,
) -> tuple[str, str]:
    """Return yt-dlp cookies-from-browser arguments."""

    if browser.name in CHROMIUM_BROWSERS:
        return browser.name, _prepare_cookie_profile(browser)

    return browser.name, str(browser.path)

class _QuietYTDLPLogger:
    """Suppress yt-dlp output during browser cookie checks."""

    def debug(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        pass


def _browser_has_usable_cookies(browser: BrowserProfile) -> bool:
    """Return whether a browser profile has usable YouTube cookies."""

    try:
        with YoutubeDL(
            {
                "quiet": True,
                "no_warnings": True,
                "logger": _QuietYTDLPLogger(),
                "cookiesfrombrowser": get_ytdlp_cookie_options(browser),
            }
        ) as ydl:
            cookiejar = ydl.cookiejar

            return (
                cookiejar is not None
                and has_youtube_cookies(cookiejar)
            )

    except Exception:
        return False

def find_browser_with_cookies() -> BrowserProfile | None:
    """Return the first browser profile whose cookies can be loaded."""

    for browser in detect_browser_profiles():
        if _browser_has_usable_cookies(browser):
            return browser

    return None

def find_browser(browser_name: str) -> BrowserProfile | None:
    """Find a specific browser profile with usable YouTube cookies."""

    browser_name = browser_name.lower()

    for browser in detect_browser_profiles():
        if browser.name != browser_name:
            continue

        if _browser_has_usable_cookies(browser):
            return browser

    return None

def has_youtube_cookies(cookiejar) -> bool:
    """Return whether a cookie jar contains YouTube cookies."""

    return any(
        cookie.domain.lower().lstrip(".") == "youtube.com"
        for cookie in cookiejar
    )
