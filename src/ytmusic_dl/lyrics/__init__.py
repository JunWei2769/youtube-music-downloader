"""
Purpose: Everything related to lyrics.

- Lyrics provider abstraction
- LRCLIB lyrics
- NetEase lyrics
- Lyrics searching
- Lyrics matching
- Synced lyrics
- Plain lyrics
- Lyrics result parsing

Responsibility: Lyrics providers / lyrics matching
"""

# Re-exported so tests and callers can patch `ytmusic_dl.lyrics.httpx`.
import httpx  # noqa: F401

from ytmusic_dl.lyrics.constants import (
    LRCLIB_API_URL,
    NETEASE_LYRICS_URL,
    NETEASE_SEARCH_URL,
    USER_AGENT,
)
from ytmusic_dl.lyrics.normalize import (
    _albums_match,
    _build_title_variants,
    _extract_editions,
    _normalize_album,
    _normalize_text,
    _similarity,
)
from ytmusic_dl.lyrics.providers import (
    LRCLIBProvider,
    NetEaseProvider,
    NetEaseSearchUnavailable,
    _build_netease_search_terms,
    _parse_lrclib_result,
    _parse_netease_result,
)
from ytmusic_dl.lyrics.scoring import (
    ALBUM_MATCH_BONUS,
    CONFIDENCE_ORDER,
    HIGH_CONFIDENCE_SCORE,
    MAJOR_EDITION_PENALTY,
    MAX_DURATION_DIFFERENCE,
    MAX_EDITION_PENALTY,
    MEDIUM_CONFIDENCE_SCORE,
    MIN_TITLE_SIMILARITY,
    NEUTRAL_EDITIONS,
    _artist_matches,
    _artist_similarity,
    _duration_is_acceptable,
    _duration_score,
    _match_score,
    _passes_basic_checks,
    _title_similarity,
    confidence_at_least,
    confidence_for_score,
)
from ytmusic_dl.lyrics.service import (
    PROVIDERS,
    build_candidate,
    fetch_missing_lyrics,
    find_best_candidate,
    find_best_lyrics,
    get_lyrics,
    pick_best_candidate,
    search_candidates,
    search_lyrics,
    write_lyrics,
)
