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

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Protocol

import httpx
from opencc import OpenCC

from ytmusic_dl.models import Lyrics, LyricsResult, Track

LRCLIB_API_URL = "https://lrclib.net/api"
NETEASE_SEARCH_URL = "https://music.163.com/api/cloudsearch/pc"
NETEASE_LYRICS_URL = "https://music.163.com/api/song/lyric"

USER_AGENT = "youtube-music-downloader/0.1.0"

MIN_MATCH_SCORE = 0.75
MAX_DURATION_DIFFERENCE = 10.0

_OPENCC = OpenCC("t2s")

class NetEaseSearchUnavailable(Exception):
    """Raised when the NetEase search API is temporarily unavailable."""

class LyricsProvider(Protocol):
    """Interface implemented by lyrics providers."""

    name: str

    def search(self, track: Track) -> list[LyricsResult]:
        """Search the provider for lyrics candidates."""
        ...

def _normalize_text(value: str | None) -> str:
    """Normalize text for lyrics matching."""
    if not value:
        return ""

    normalized = value.casefold()

    replacements = {
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "「": "[",
        "」": "]",
        "：": ":",
        "，": ",",
        "！": "!",
        "？": "?",
        "＋": "+",
        "＆": "&",
        "　": " ",
    }

    for old, new in replacements.items():
        normalized = normalized.replace(old, new)

    # Normalize Traditional Chinese to Simplified Chinese.
    normalized = _OPENCC.convert(normalized)

    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s*([+&,/])\s*", r"\1", normalized)

    return normalized.strip()

def _build_title_variants(title: str) -> list[str]:
    """Build alternative title forms for lyrics matching."""
    title = title.strip()

    if not title:
        return []

    variants: list[str] = [
        title,
        _normalize_text(title),
    ]

    # Remove common live/version suffixes.
    simplified = re.sub(
        r"\s*[\(\（].*?"
        r"(live|现场|演唱会|version|版)"
        r".*?[\)\）]",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    if simplified:
        variants.append(simplified)
        variants.append(_normalize_text(simplified))

    # Extract the title portion before the " - " separator.
    title_part = re.split(
        r"\s+-\s+",
        title,
        maxsplit=1,
    )[0].strip()

    # Remove parenthesized version/live information.
    chinese_title = re.sub(
        r"[\(\（].*?[\)\）]",
        "",
        title_part,
    ).strip()

    # Keep only Chinese characters.
    chinese_title = re.sub(
        r"[^\u3400-\u4dbf\u4e00-\u9fff]+",
        "",
        chinese_title,
    )

    if chinese_title:
        variants.append(chinese_title)
        variants.append(_normalize_text(chinese_title))

    # Extract English/Latin title.
    english_parts = re.findall(
        r"[A-Za-z][A-Za-z0-9'’&,\- ]*",
        title,
    )

    english_title = " ".join(
        part.strip()
        for part in english_parts
        if part.strip()
    ).strip()

    if english_title:
        variants.append(english_title)
        variants.append(_normalize_text(english_title))

    return list(
        dict.fromkeys(
            variant.strip()
            for variant in variants
            if variant.strip()
        )
    )

def _similarity(first: str, second: str) -> float:
    """Return a similarity score between two strings."""

    first_normalized = _normalize_text(first)
    second_normalized = _normalize_text(second)

    if not first_normalized or not second_normalized:
        return 0.0

    if first_normalized == second_normalized:
        return 1.0

    return SequenceMatcher(
        None,
        first_normalized,
        second_normalized,
    ).ratio()

def _artist_matches(
    track_artist: str | None,
    lyrics_artist: str | None,
) -> bool:
    """Return whether the lyrics artist matches the track artist."""

    if not track_artist or not lyrics_artist:
        return False

    def normalize_artists(value: str) -> set[str]:
        """Normalize an artist string into comparable artist names."""

        normalized = _normalize_text(value)

        parts = re.split(
            r",|&|feat\.?|ft\.?|／|/|、|_aka_",
            normalized,
        )

        return {
            part.strip()
            for part in parts
            if part.strip()
        }

    track_artists = normalize_artists(track_artist)
    lyrics_artists = normalize_artists(lyrics_artist)

    if not track_artists or not lyrics_artists:
        return False

    return bool(track_artists & lyrics_artists)

def _artist_similarity(
    track_artist: str | None,
    result_artist: str | None,
) -> float:
    """Return an artist similarity score."""

    first = _normalize_text(track_artist)
    second = _normalize_text(result_artist)

    if not first or not second:
        return 0.0

    if first == second:
        return 1.0

    def normalize_artists(value: str) -> set[str]:
        parts = re.split(
            r",|&|/|／|、|_aka_|feat\.?|ft\.?",
            value,
        )

        return {
            part.strip()
            for part in parts
            if part.strip()
        }

    first_artists = normalize_artists(first)
    second_artists = normalize_artists(second)

    if first_artists and second_artists:
        overlap = first_artists & second_artists

        if overlap:
            return len(overlap) / max(
                len(first_artists),
                len(second_artists),
            )

    return _similarity(first, second)

def _duration_score(
    track_duration: float | None,
    lyrics_duration: float | None,
) -> float:
    """Return a score based on duration difference."""

    if track_duration is None or lyrics_duration is None:
        return 0.0

    difference = abs(track_duration - lyrics_duration)

    if difference <= 2:
        return 1.0

    if difference <= 5:
        return 0.8

    if difference <= 10:
        return 0.5

    return 0.0

def _duration_is_acceptable(
    track_duration: float | None,
    lyrics_duration: float | None,
) -> bool:
    """Return whether two known durations are close enough."""

    if track_duration is None or lyrics_duration is None:
        return True

    return (
        abs(track_duration - lyrics_duration)
        <= MAX_DURATION_DIFFERENCE
    )

def _title_similarity(
    track_title: str | None,
    result_title: str | None,
) -> float:
    """Return the best similarity across title variants."""
    if not track_title or not result_title:
        return 0.0

    track_variants = _build_title_variants(track_title)
    result_variants = _build_title_variants(result_title)

    return max(
        (
            _similarity(track_variant, result_variant)
            for track_variant in track_variants
            for result_variant in result_variants
        ),
        default=0.0,
    )

def _match_score(
    track: Track,
    result: LyricsResult,
) -> float:
    """Calculate the overall match score for a lyrics result."""

    title_score = _title_similarity(
        track.title,
        result.track_name,
    )

    artist_score = _artist_similarity(
        track.artist,
        result.artist_name,
    )

    duration_score = _duration_score(
        track.duration,
        result.duration,
    )

    duration_exact = (
        track.duration is not None
        and result.duration is not None
        and abs(track.duration - result.duration) <= 1.0
    )

    # Strong match:
    # - duration is essentially identical
    # - artist has a meaningful match
    # - title has reasonable similarity
    #
    # This is important for YouTube Music titles containing
    # extra metadata such as "Official Music Video", bilingual
    # names, version information, etc.
    if (
        duration_exact
        and title_score >= 0.60
        and artist_score >= 0.50
    ):
        return 1.0

    return (
        title_score * 0.50
        + artist_score * 0.25
        + duration_score * 0.25
    )

def _parse_lrclib_result(
    item: dict[str, Any],
) -> LyricsResult:
    """Convert an LRCLIB response into a LyricsResult."""

    return LyricsResult(
        provider="lrclib",
        provider_id=str(item["id"]),
        track_name=str(
            item.get(
                "trackName",
                item.get("name", ""),
            )
        ),
        artist_name=str(
            item.get("artistName", "")
        ),
        album_name=item.get("albumName"),
        duration=(
            float(item["duration"])
            if item.get("duration") is not None
            else None
        ),
        instrumental=bool(
            item.get("instrumental", False)
        ),
        synced_lyrics=item.get("syncedLyrics"),
        plain_lyrics=item.get("plainLyrics"),
    )

class LRCLIBProvider:
    """LRCLIB lyrics provider."""

    name = "lrclib"

    def __init__(self) -> None:
        self.headers = {
            "User-Agent": USER_AGENT,
        }

    def search(self, track: Track) -> list[LyricsResult]:
        """Search the provider for lyrics candidates."""

        results: list[LyricsResult] = []

        try:
            result = self._get_exact(track)

            if result is not None:
                results.append(result)

        except httpx.HTTPError:
            pass

        if results:
            return results

        try:
            return self._search(track)

        except httpx.HTTPError:
            return []

    def _get_exact(
        self,
        track: Track,
    ) -> LyricsResult | None:
        """Use LRCLIB's metadata-based lookup."""
        if not track.artist:
            return None

        params: dict[str, Any] = {
            "track_name": track.title,
            "artist_name": track.artist,
        }

        if track.album:
            params["album_name"] = track.album

        if track.duration is not None:
            params["duration"] = track.duration

        response = httpx.get(
            f"{LRCLIB_API_URL}/get",
            params=params,
            headers=self.headers,
            timeout=10.0,
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()

        return _parse_lrclib_result(
            response.json()
        )

    def _search(
        self,
        track: Track,
    ) -> list[LyricsResult]:
        """Search LRCLIB's keyword endpoint."""
        params: dict[str, Any] = {
            "track_name": track.title,
        }

        if track.artist:
            params["artist_name"] = track.artist

        if track.album:
            params["album_name"] = track.album

        response = httpx.get(
            f"{LRCLIB_API_URL}/search",
            params=params,
            headers=self.headers,
            timeout=10.0,
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list):
            return []

        return [
            _parse_lrclib_result(item)
            for item in data
        ]

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

def _build_netease_search_terms(track: Track) -> list[str]:
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
        track: Track,
    ) -> list[LyricsResult]:
        """Search NetEase and return validated lyric candidates."""

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

                if not _duration_is_acceptable(
                    track.duration,
                    result.duration,
                ):
                    print(
                        f"[NetEase] Rejected: duration mismatch "
                        f"(track={track.duration}, "
                        f"lyrics={result.duration})"
                    )
                    continue

                score = _match_score(
                    track,
                    result,
                )

                if score < MIN_MATCH_SCORE:
                    print(
                        f"[NetEase] Rejected: "
                        f"score {score:.3f} < {MIN_MATCH_SCORE}"
                    )
                    continue

                lyrics = self._get_lyrics(
                    result.provider_id
                )

                if lyrics is None:
                    continue

                result.synced_lyrics = lyrics
                candidates.append(result)

                return candidates

        return candidates

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

PROVIDERS: tuple[LyricsProvider, ...] = (
    LRCLIBProvider(),
    NetEaseProvider(),
)


def search_lyrics(track: Track) -> list[LyricsResult]:
    """Search all lyrics providers for matching candidates."""

    results: list[LyricsResult] = []

    for provider in PROVIDERS:
        try:
            results.extend(
                provider.search(track)
            )
        except Exception as error:
            print(
                f"Warning: {provider.name} lyrics "
                f"provider failed: {error}"
            )

    return results

def find_best_lyrics(
    track: Track,
    results: list[LyricsResult],
) -> LyricsResult | None:
    """Find the best lyrics result for a track."""

    if not results:
        return None

    best_result = None
    best_score = 0.0

    for result in results:
        title_score = _title_similarity(
            track.title,
            result.track_name,
        )

        artist_score = _artist_similarity(
            track.artist,
            result.artist_name,
        )

        duration_score = _duration_score(
            track.duration,
            result.duration,
        )

        # Reject results with a clearly different title.
        if title_score < 0.60:
            continue

        # Reject results with a clearly different artist.
        if not _artist_matches(
            track.artist,
            result.artist_name,
        ):
            continue

        # Reject results with a known but clearly different duration.
        if (
            track.duration is not None
            and result.duration is not None
            and duration_score == 0.0
        ):
            continue

        score = (
            title_score * 0.60
            + artist_score * 0.20
            + duration_score * 0.20
        )

        # Prefer synced lyrics when metadata is otherwise equivalent.
        if result.synced_lyrics:
            score += 0.10

        if score > best_score:
            best_score = score
            best_result = result

    return best_result

def get_lyrics(
    track: Track,
) -> LyricsResult | None:
    """Find the best available lyrics."""

    results = search_lyrics(track)

    return find_best_lyrics(
        track,
        results,
    )

def write_lyrics(
    lyrics: LyricsResult,
    output_path: Path,
) -> Path:
    """Write lyrics to a file."""

    if lyrics.synced_lyrics:
        content = lyrics.synced_lyrics
    elif lyrics.plain_lyrics:
        content = lyrics.plain_lyrics
    else:
        raise ValueError(
            f"No lyrics available for: {lyrics.track_name}"
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        content,
        encoding="utf-8",
    )

    return output_path
