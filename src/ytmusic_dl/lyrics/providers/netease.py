"""NetEase Cloud Music lyrics provider."""

import re
from dataclasses import replace
from typing import Any

import httpx

from ytmusic_dl.lyrics.constants import (
    NETEASE_LYRICS_URL,
    NETEASE_SEARCH_URL,
)
from ytmusic_dl.lyrics.normalize import _normalize_text
from ytmusic_dl.lyrics.scoring import (
    _match_score,
    _passes_basic_checks,
)
from ytmusic_dl.models import LyricsRequest, LyricsResult

MAX_LYRICS_FETCHES = 5

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

        if value:
            terms.append(value)

            normalized = _normalize_text(value)

            if normalized:
                terms.append(normalized)

    # ---------------------------------------------------------
    # 1. Original title
    # ---------------------------------------------------------

    add_term(title)

    # ---------------------------------------------------------
    # 2. Extract content inside YouTube-style brackets.
    #
    # Example:
    # 蘇打綠 sodagreen【博物館 The Museum】（蘇打綠版）...
    #
    # -> 博物館 The Museum
    # ---------------------------------------------------------

    bracket_titles = re.findall(
        r"【([^】]+)】",
        title,
    )

    for bracket_title in bracket_titles:
        add_term(bracket_title)

    # Also support normal parentheses/brackets when useful.
    bracket_titles = re.findall(
        r"\[([^\]]+)\]",
        title,
    )

    for bracket_title in bracket_titles:
        add_term(bracket_title)

    # ---------------------------------------------------------
    # 3. Remove common YouTube metadata.
    # ---------------------------------------------------------

    search_title = re.sub(
        r"\b"
        r"(official\s+music\s+video|"
        r"official\s+video|"
        r"music\s+video)"
        r"\b",
        "",
        title,
        flags=re.IGNORECASE,
    )

    # Remove common version/live suffixes.
    search_title = re.sub(
        r"\s*[\(\（]"
        r".*?"
        r"(?:live|现场|演唱会|version|版)"
        r".*?"
        r"[\)\）]",
        "",
        search_title,
        flags=re.IGNORECASE,
    )

    search_title = search_title.strip()

    if search_title:
        add_term(search_title)

    # ---------------------------------------------------------
    # 4. Extract Chinese-only title.
    # ---------------------------------------------------------

    chinese_title = re.sub(
        r"[^\u3400-\u4dbf\u4e00-\u9fff]+",
        "",
        search_title,
    )

    if chinese_title:
        add_term(chinese_title)

    # ---------------------------------------------------------
    # 5. Extract English/Latin title.
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

    if english_title:
        add_term(english_title)

    # ---------------------------------------------------------
    # Preserve order and remove duplicates.
    # ---------------------------------------------------------

    return list(
        dict.fromkeys(
            term
            for term in terms
            if term
        )
    )

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

            print(
                f"[NetEase] Search: {search_term!r} "
                f"→ HTTP {response.status_code}"
            )

            response.raise_for_status()

            data = response.json()

        except (httpx.HTTPError, ValueError) as error:
            print(
                f"[NetEase] Search failed for "
                f"{search_term!r}: {error}"
            )
            return []

        if not isinstance(data, dict):
            print(
                f"[NetEase] Invalid response for "
                f"{search_term!r}"
            )
            return []

        code = data.get("code")

        if code != 200:
            print(
                f"[NetEase] API error for "
                f"{search_term!r}: code={code}"
            )
            raise NetEaseSearchUnavailable(
                f"NetEase search unavailable (code {code})"
            )

        result = data.get("result")

        if not isinstance(result, dict):
            print(
                f"[NetEase] No result object for "
                f"{search_term!r}"
            )
            return []

        songs = result.get("songs", [])

        if not isinstance(songs, list):
            print(
                f"[NetEase] Invalid songs list for "
                f"{search_term!r}"
            )
            return []

        print(
            f"[NetEase] Search returned "
            f"{len(songs)} songs for {search_term!r}"
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

            print(
                f"[NetEase] Lyrics request: "
                f"id={provider_id} "
                f"→ HTTP {response.status_code}"
            )

            response.raise_for_status()

            data = response.json()

        except (httpx.HTTPError, ValueError) as error:
            print(
                f"[NetEase] Lyrics request failed "
                f"for id={provider_id}: {error}"
            )
            return None

        lyric_data = data.get("lrc") or {}

        lyrics = lyric_data.get("lyric")

        if not lyrics:
            print(
                f"[NetEase] No lyrics returned "
                f"for id={provider_id}"
            )
            return None

        print(
            f"[NetEase] Lyrics found "
            f"for id={provider_id}"
        )

        return str(lyrics)
