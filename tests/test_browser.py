from pathlib import Path
from unittest.mock import MagicMock, patch

from ytmusic_dl.browser import (
    BrowserProfile,
    _detect_chromium_profiles,
    _detect_firefox_profiles,
    detect_browser_profiles,
    find_browser,
    find_browser_with_cookies,
    get_browser_path,
    has_youtube_cookies,
)


def test_detect_chromium_profiles(tmp_path: Path) -> None:
    """Detect Chromium profiles containing a Cookies database."""

    default_profile = tmp_path / "Default"
    default_profile.mkdir()
    (default_profile / "Cookies").touch()

    profile_one = tmp_path / "Profile 1"
    profile_one.mkdir()
    (profile_one / "Cookies").touch()

    profile_without_cookies = tmp_path / "Profile 2"
    profile_without_cookies.mkdir()

    profiles = _detect_chromium_profiles(tmp_path)

    assert profiles == [
        default_profile,
        profile_one,
    ]

def test_detect_firefox_profiles(tmp_path: Path) -> None:
    """Detect Firefox profiles containing cookies."""

    profile = tmp_path / "abc123.default-release"
    profile.mkdir()
    (profile / "cookies.sqlite").touch()

    empty_profile = tmp_path / "xyz789.default-release"
    empty_profile.mkdir()

    profiles_ini = tmp_path / "profiles.ini"
    profiles_ini.write_text(
        """\
[Profile0]
Name=default-release
IsRelative=1
Path=abc123.default-release
Default=1

[Profile1]
Name=empty
IsRelative=1
Path=xyz789.default-release
""",
        encoding="utf-8",
    )

    profiles = _detect_firefox_profiles(tmp_path)

    assert profiles == [profile]

def test_get_browser_path_linux(tmp_path: Path) -> None:
    """Return correct browser paths on Linux."""

    with (
        patch("ytmusic_dl.browser.platform.system", return_value="Linux"),
        patch("ytmusic_dl.browser.Path.home", return_value=tmp_path),
    ):
        paths = get_browser_path()

    assert paths["vivaldi"] == tmp_path / ".config" / "vivaldi"
    assert paths["chrome"] == tmp_path / ".config" / "google-chrome"
    assert paths["brave"] == (
        tmp_path / ".config" / "BraveSoftware" / "Brave-Browser"
    )
    assert paths["firefox"] == (
        tmp_path / ".config" / "mozilla" / "firefox"
    )

def test_get_browser_path_macos(tmp_path: Path) -> None:
    """Return correct browser paths on macOS."""

    with (
        patch("ytmusic_dl.browser.platform.system", return_value="Darwin"),
        patch("ytmusic_dl.browser.Path.home", return_value=tmp_path),
    ):
        paths = get_browser_path()

    app_support = (
        tmp_path / "Library" / "Application Support"
    )

    assert paths["chrome"] == app_support / "Google" / "Chrome"
    assert paths["brave"] == (
        app_support / "BraveSoftware" / "Brave-Browser"
    )
    assert paths["vivaldi"] == app_support / "vivaldi"
    assert paths["firefox"] == (
        app_support / "Firefox"
    )

def test_get_browser_path_windows(tmp_path: Path) -> None:
    """Return correct browser paths on Windows."""

    with (
        patch("ytmusic_dl.browser.platform.system", return_value="Windows"),
        patch("ytmusic_dl.browser.Path.home", return_value=tmp_path),
    ):
        paths = get_browser_path()

    local_app_data = (
        tmp_path / "AppData" / "Local"
    )

    roaming_app_data = (
        tmp_path / "AppData" / "Roaming"
    )

    assert paths["chrome"] == (
        local_app_data / "Google" / "Chrome"
    )

    assert paths["brave"] == (
        local_app_data
        / "BraveSoftware"
        / "Brave-Browser"
    )

    assert paths["vivaldi"] == (
        local_app_data / "Vivaldi"
    )

    assert paths["firefox"] == (
        roaming_app_data / "Mozilla" / "Firefox"
    )

def test_detect_browser_profiles(tmp_path: Path) -> None:
    """Detect profiles from multiple installed browsers."""

    config = tmp_path / ".config"

    # Chrome
    chrome_profile = config / "google-chrome" / "Default"
    chrome_profile.mkdir(parents=True)
    (chrome_profile / "Cookies").touch()

    # Firefox
    firefox_root = config / "mozilla" / "firefox"
    firefox_profile = firefox_root / "abc123.default-release"
    firefox_profile.mkdir(parents=True)
    (firefox_profile / "cookies.sqlite").touch()

    (firefox_root / "profiles.ini").write_text(
        """\
[Profile0]
Name=default-release
IsRelative=1
Path=abc123.default-release
Default=1
""",
        encoding="utf-8",
    )

    with (
        patch("ytmusic_dl.browser.platform.system", return_value="Linux"),
        patch("ytmusic_dl.browser.Path.home", return_value=tmp_path),
    ):
        browsers = detect_browser_profiles()

    assert len(browsers) == 2

    assert browsers[0].name == "chrome"
    assert browsers[0].path == chrome_profile

    assert browsers[1].name == "firefox"
    assert browsers[1].path == firefox_profile

def test_find_browser_with_cookies_falls_back() -> None:
    """Return the first browser whose cookies can be loaded."""

    chrome = BrowserProfile(
        name="chrome",
        path=Path("/fake/chrome/Default"),
    )

    firefox = BrowserProfile(
        name="firefox",
        path=Path("/fake/firefox/profile"),
    )

    browsers = [chrome, firefox]

    chrome_ydl = MagicMock()
    chrome_ydl.__enter__.return_value = chrome_ydl

    chrome_cookie = MagicMock()
    chrome_cookie.domain = ".google.com"

    chrome_ydl.cookiejar = [chrome_cookie]

    firefox_ydl = MagicMock()
    firefox_ydl.__enter__.return_value = firefox_ydl

    firefox_cookie = MagicMock()
    firefox_cookie.domain = ".youtube.com"

    firefox_ydl.cookiejar = [firefox_cookie]

    def create_ydl(options: dict) -> MagicMock:
        if options["cookiesfrombrowser"][0] == "chrome":
            return chrome_ydl

        return firefox_ydl

    with (
        patch(
            "ytmusic_dl.browser.detect_browser_profiles",
            return_value=browsers,
        ),
        patch(
            "ytmusic_dl.browser.YoutubeDL",
            side_effect=create_ydl,
        ),
    ):
        browser = find_browser_with_cookies()

    assert browser == firefox

def test_find_browser_by_name() -> None:
    """Return a specific browser with usable YouTube cookies."""

    vivaldi = BrowserProfile(
        name="vivaldi",
        path=Path("/fake/vivaldi/Default"),
    )

    firefox = BrowserProfile(
        name="firefox",
        path=Path("/fake/firefox/profile"),
    )

    vivaldi_ydl = MagicMock()
    vivaldi_ydl.__enter__.return_value = vivaldi_ydl
    vivaldi_ydl.cookiejar = [
        MagicMock(domain=".youtube.com"),
    ]

    firefox_ydl = MagicMock()
    firefox_ydl.__enter__.return_value = firefox_ydl
    firefox_ydl.cookiejar = [
        MagicMock(domain=".youtube.com"),
    ]

    def create_ydl(options: dict) -> MagicMock:
        if options["cookiesfrombrowser"][0] == "vivaldi":
            return vivaldi_ydl

        return firefox_ydl

    with (
        patch(
            "ytmusic_dl.browser.detect_browser_profiles",
            return_value=[vivaldi, firefox],
        ),
        patch(
            "ytmusic_dl.browser.YoutubeDL",
            side_effect=create_ydl,
        ),
    ):
        browser = find_browser("vivaldi")

    assert browser == vivaldi

def test_find_browser_returns_none_for_unknown_browser() -> None:
    """Return None when the requested browser is not detected."""

    vivaldi = BrowserProfile(
        name="vivaldi",
        path=Path("/fake/vivaldi/Default"),
    )

    with patch(
        "ytmusic_dl.browser.detect_browser_profiles",
        return_value=[vivaldi],
    ):
        browser = find_browser("chrome")

    assert browser is None

def test_find_browser_returns_none_without_youtube_cookies() -> None:
    """Return None when the requested browser has no YouTube cookies."""

    vivaldi = BrowserProfile(
        name="vivaldi",
        path=Path("/fake/vivaldi/Default"),
    )

    vivaldi_ydl = MagicMock()
    vivaldi_ydl.__enter__.return_value = vivaldi_ydl
    vivaldi_ydl.cookiejar = [
        MagicMock(domain=".google.com"),
    ]

    with (
        patch(
            "ytmusic_dl.browser.detect_browser_profiles",
            return_value=[vivaldi],
        ),
        patch(
            "ytmusic_dl.browser.YoutubeDL",
            return_value=vivaldi_ydl,
        ),
    ):
        browser = find_browser("vivaldi")

    assert browser is None

def test_has_youtube_cookies() -> None:
    """Detect YouTube cookies in a cookie jar."""

    youtube_cookie = MagicMock()
    youtube_cookie.domain = ".youtube.com"

    google_cookie = MagicMock()
    google_cookie.domain = ".google.com"

    cookiejar = [
        google_cookie,
        youtube_cookie,
    ]

    assert has_youtube_cookies(cookiejar) is True

def test_has_youtube_cookies_returns_false() -> None:
    """Reject cookie jars without YouTube cookies."""

    google_cookie = MagicMock()
    google_cookie.domain = ".google.com"

    cookiejar = [google_cookie]

    assert has_youtube_cookies(cookiejar) is False

def test_find_browser_skips_browser_without_youtube_cookies() -> None:
    """Skip browsers without YouTube cookies."""

    chrome = BrowserProfile(
        name="chrome",
        path=Path("/fake/chrome/Default"),
    )

    firefox = BrowserProfile(
        name="firefox",
        path=Path("/fake/firefox/profile"),
    )

    chrome_ydl = MagicMock()
    chrome_ydl.__enter__.return_value = chrome_ydl

    chrome_cookie = MagicMock()
    chrome_cookie.domain = ".google.com"

    chrome_ydl.cookiejar = [chrome_cookie]

    firefox_ydl = MagicMock()
    firefox_ydl.__enter__.return_value = firefox_ydl

    firefox_cookie = MagicMock()
    firefox_cookie.domain = ".youtube.com"

    firefox_ydl.cookiejar = [firefox_cookie]

    def create_ydl(options: dict) -> MagicMock:
        if options["cookiesfrombrowser"][0] == "chrome":
            return chrome_ydl

        return firefox_ydl

    with (
        patch(
            "ytmusic_dl.browser.detect_browser_profiles",
            return_value=[chrome, firefox],
        ),
        patch(
            "ytmusic_dl.browser.YoutubeDL",
            side_effect=create_ydl,
        ),
    ):
        browser = find_browser_with_cookies()

    assert browser == firefox
