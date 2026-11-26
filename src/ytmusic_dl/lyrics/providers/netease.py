"""NetEase Cloud Music lyrics provider."""

import re
from dataclasses import replace
from typing import Any

import httpx

from ytmusic_dl.lyrics.constants import (
    NETEASE_LYRICS_URL,
    NETEASE_SEARCH_URL,
)
from ytmusic_dl.lyrics.normalize import (
    _normalize_text,
    _strip_title_noise,
)
from ytmusic_dl.log import get_logger
from ytmusic_dl.lyrics.scoring import (
    _match_score,
    _passes_basic_checks,
)
from ytmusic_dl.models import LyricsRequest, LyricsResult

logger = get_logger("lyrics.netease")

MAX_LYRICS_FETCHES = 5
MAX_SEARCH_TERMS = 6

class NetEaseSearchUnavailable(Exception):
    """Raised when the NetEase search API is temporarily unavailable."""

def _parse_netease_result(
    song: dict[str, Any],
) -> LyricsResult:
    """Convert a NetEase song result into a LyricsResult."""

    artists = song.get("ar") or []

    artist_names: list[str] = []

    for artist in artists:
        name = artist.get("name")

        if name:
            artist_names.append(str(name))

        for alias in artist.get("alias") or []:
            if alias:
                artist_names.append(str(alias))

    track_name = str(song.get("name", ""))

    translated_names = song.get("tns") or []

    if translated_names:
        track_name = (
            f"{track_name} "
            f"({' / '.join(str(name) for name in translated_names)})"
        )

    album = song.get("al") or {}

    return LyricsResult(
        provider="netease",
        provider_id=str(song["id"]),
        track_name=track_name,
        artist_name=", ".join(
            dict.fromkeys(artist_names)
        ),
        album_name=album.get("name"),
        duration=(
            float(song["dt"]) / 1000
            if song.get("dt") is not None
            else None
        ),
        instrumental=False,
        synced_lyrics=None,
        plain_lyrics=None,
    )

def _build_netease_search_terms(
    track: LyricsRequest,
) -> list[str]:
    """Build progressively simplified NetEase search queries."""

    title = track.title.strip()

    if not title:
        return []

    terms: list[str] = []

    def add_term(value: str) -> None:
        value = value.strip()

        if not value:
            return

        terms.append(value)

        normalized = _normalize_text(value)

        if normalized:
            terms.append(normalized)

    # ---------------------------------------------------------
    # 1. Title with video/remaster noise removed.
    # ---------------------------------------------------------

    search_title = _strip_title_noise(title)

    add_term(search_title)

    # ---------------------------------------------------------
    # 2. Song portion of an "Artist - Song" title.
    # ---------------------------------------------------------

    title_parts = re.split(
        r"\s+[-–—]\s+",
        search_title,
        maxsplit=1,
    )

    if len(title_parts) == 2:
        add_term(title_parts[1])

    # ---------------------------------------------------------
    # 3. Content inside YouTube-style brackets.
    #
    # Example:
    # 蘇打綠 sodagreen【博物館 The Museum】（蘇打綠版）...
    #
    # -> 博物館 The Museum
    # ---------------------------------------------------------

    for pattern in (r"【([^】]+)】", r"\[([^\]]+)\]"):
        for bracket_title in re.findall(pattern, title):
            add_term(
                _strip_title_noise(bracket_title)
            )

    # ---------------------------------------------------------
    # 4. Chinese-only title.
    # ---------------------------------------------------------

    chinese_title = re.sub(
        r"[^\u3400-\u4dbf\u4e00-\u9fff]+",
        "",
        search_title,
    )

    add_term(chinese_title)

    # ---------------------------------------------------------
    # 5. English/Latin title.
    # ---------------------------------------------------------

    english_parts = re.findall(
        r"[A-Za-z][A-Za-z0-9'’&,\- ]*",
        search_title,
    )

    english_title = " ".join(
        part.strip()
        for part in english_parts
        if part.strip()
    ).strip()

    add_term(english_title)

    # ---------------------------------------------------------
    # Preserve order, remove duplicates, and cap the number of
    # requests made against NetEase.
    # ---------------------------------------------------------

    unique_terms = list(
        dict.fromkeys(
            term
            for term in terms
            if term
        )
    )

    return unique_terms[:MAX_SEARCH_TERMS]

class NetEaseProvider:
    """NetEase Cloud Music lyrics provider."""

    name = "netease"

    def __init__(self) -> None:
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
            "Referer": "https://music.163.com/",
        }

        self.client = httpx.Client(
            headers=self.headers,
            follow_redirects=True,
            timeout=10.0,
        )

        self.initialized = False

    def _initialize(self) -> bool:
        """Initialize the NetEase HTTP session."""

        if self.initialized:
            return True

        try:
            response = self.client.get(
                "https://music.163.com/discover"
            )
            response.raise_for_status()

        except httpx.HTTPError:
            return False

        self.initialized = True
        return True

    def search(
        self,
        track: LyricsRequest,
    ) -> list[LyricsResult]:
        """Search NetEase and return every discovered candidate."""

        if not self._initialize():
            return []

        candidates: list[LyricsResult] = []
        seen_provider_ids: set[str] = set()

        search_terms = _build_netease_search_terms(track)

        for search_term in search_terms:
            try:
                songs = self._search_songs(search_term)
            except NetEaseSearchUnavailable:
                break

            for song in songs:
                result = _parse_netease_result(song)

                if result.provider_id in seen_provider_ids:
                    continue

                seen_provider_ids.add(result.provider_id)
                candidates.append(result)

        hydrated = self._hydrate_best_candidates(
            track,
            candidates,
        )

        by_id = {
            result.provider_id: result
            for result in hydrated
        }

        return [
            by_id.get(result.provider_id, result)
            for result in candidates
        ]

    def _hydrate_best_candidates(
        self,
        track: LyricsRequest,
        candidates: list[LyricsResult],
    ) -> list[LyricsResult]:
        """Fetch lyrics for the most promising candidates only."""

        ranked = sorted(
            candidates,
            key=lambda result: _match_score(track, result),
            reverse=True,
        )

        hydrated: list[LyricsResult] = []

        for result in ranked:
            if len(hydrated) >= MAX_LYRICS_FETCHES:
                break

            if not _passes_basic_checks(track, result):
                continue

            hydrated.append(
                self.fetch_lyrics(result)
            )

        return hydrated

    def fetch_lyrics(self, result: LyricsResult) -> LyricsResult:
        """Fetch lyrics content for a discovered candidate."""

        if result.synced_lyrics or result.plain_lyrics:
            return result

        lyrics = self._get_lyrics(result.provider_id)

        if lyrics is None:
            return result

        return replace(result, synced_lyrics=lyrics)

    def _search_songs(
        self,
        search_term: str,
    ) -> list[dict[str, Any]]:
        """Search NetEase for songs."""

        try:
            response = self.client.post(
                NETEASE_SEARCH_URL,
                data={
                    "s": search_term,
                    "type": 1,
                    "offset": 0,
                    "limit": 10,
                    "total": "true",
                },
            )

            logger.debug(
                "[NetEase] Search: %r → HTTP %s",
                search_term,
                response.status_code,
            )

            response.raise_for_status()

            data = response.json()

        except (httpx.HTTPError, ValueError) as error:
            logger.warning(
                "[NetEase] Search failed for %r: %s",
                search_term,
                error,
            )
            return []

        if not isinstance(data, dict):
            logger.warning(
                "[NetEase] Invalid response for %r",
                search_term,
            )
            return []

        code = data.get("code")

        if code != 200:
            logger.warning(
                "[NetEase] API error for %r: code=%s",
                search_term,
                code,
            )
            raise NetEaseSearchUnavailable(
                f"NetEase search unavailable (code {code})"
            )

        result = data.get("result")

        if not isinstance(result, dict):
            logger.warning(
                "[NetEase] No result object for %r",
                search_term,
            )
            return []

        songs = result.get("songs", [])

        if not isinstance(songs, list):
            logger.warning(
                "[NetEase] Invalid songs list for %r",
                search_term,
            )
            return []

        logger.debug(
            "[NetEase] Search returned %d songs for %r",
            len(songs),
            search_term,
        )

        return [
            song
            for song in songs
            if isinstance(song, dict)
        ]

    def _get_lyrics(
        self,
        provider_id: str,
    ) -> str | None:
        """Retrieve synchronized lyrics by NetEase song ID."""

        try:
            response = self.client.get(
                NETEASE_LYRICS_URL,
                params={
                    "id": provider_id,
                    "lv": 1,
                },
            )

            logger.debug(
                "[NetEase] Lyrics request: id=%s → HTTP %s",
                provider_id,
                response.status_code,
            )

            response.raise_for_status()

            data = response.json()

        except (httpx.HTTPError, ValueError) as error:
            logger.warning(
                "[NetEase] Lyrics request failed for id=%s: %s",
                provider_id,
                error,
            )
            return None

        lyric_data = data.get("lrc") or {}

        lyrics = lyric_data.get("lyric")

        if not lyrics:
            logger.debug(
                "[NetEase] No lyrics returned for id=%s",
                provider_id,
            )
            return None

        logger.debug(
            "[NetEase] Lyrics found for id=%s",
            provider_id,
        )

        return str(lyrics)
