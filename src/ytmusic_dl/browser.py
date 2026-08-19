import os
import platform
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
}

FIREFOX_BROWSERS = {
    "firefox",
}


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

        cookie_file = profile / "Cookies"

        if cookie_file.is_file():
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
            "safari": home / "Library" / "Safari",
        }

    if system == "Windows":
        local_app_data = home / "AppData" / "Local"
        roaming_app_data = home / "AppData" / "Roaming"

        return {
            "chrome": local_app_data / "Google" / "Chrome",
            "chromium": local_app_data / "Chromium",
            "brave": local_app_data / "BraveSoftware" / "Brave-Browser",
            "vivaldi": local_app_data / "Vivaldi",
            "firefox": roaming_app_data / "Mozilla" / "Firefox",
            "edge": local_app_data / "Microsoft" / "Edge",
            "opera": roaming_app_data / "Opera Software" / "Opera Stable",
            "whale": local_app_data / "Naver" / "Whale",
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

def get_ytdlp_cookie_options(
    browser: BrowserProfile,
) -> tuple[str, str]:
    """Return yt-dlp cookies-from-browser arguments."""

    return browser.name, str(browser.path)

def _browser_has_usable_cookies(browser: BrowserProfile) -> bool:
    """Return whether a browser profile has usable YouTube cookies."""

    try:
        with YoutubeDL(
            {
                "quiet": True,
                "no_warnings": True,
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
