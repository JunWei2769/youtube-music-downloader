"""Lyrics provider implementations."""

__all__ = [
    "LRCLIBProvider",
    "NetEaseProvider",
    "NetEaseSearchUnavailable",
    "_build_netease_search_terms",
    "_parse_lrclib_result",
    "_parse_netease_result",
]

from ytmusic_dl.lyrics.providers.lrclib import (
    LRCLIBProvider,
    _parse_lrclib_result,
)
from ytmusic_dl.lyrics.providers.netease import (
    NetEaseProvider,
    NetEaseSearchUnavailable,
    _build_netease_search_terms,
    _parse_netease_result,
)
