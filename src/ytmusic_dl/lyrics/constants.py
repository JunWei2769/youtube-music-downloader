"""Constants shared by the lyrics providers."""

from importlib.metadata import version as package_version

LRCLIB_API_URL = "https://lrclib.net/api"
NETEASE_SEARCH_URL = "https://music.163.com/api/cloudsearch/pc"
NETEASE_LYRICS_URL = "https://music.163.com/api/song/lyric"

USER_AGENT = (
    f"youtube-music-downloader/"
    f"{package_version('youtube-music-downloader')}"
)
