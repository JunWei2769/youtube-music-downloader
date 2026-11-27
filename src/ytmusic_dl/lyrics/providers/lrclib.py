"""LRCLIB lyrics provider."""

from typing import Any

import httpx

from ytmusic_dl.lyrics.constants import (
    LRCLIB_API_URL,
    USER_AGENT,
)
from ytmusic_dl.lyrics.normalize import (
    _script_variants,
    _search_title_variants,
)
from ytmusic_dl.models import LyricsRequest, LyricsResult

def _script_pairs(
    title: str,
    artist: str | None,
) -> list[tuple[str, str | None]]:
    """Pair title and artist in their raw, Simplified, and Traditional forms."""

    titles = _script_variants(title)
    artists = _script_variants(artist) if artist else []

    pairs: list[tuple[str, str | None]] = []

    for index, title_variant in enumerate(titles):
        if artists:
            artist_variant = (
                artists[index]
                if index < len(artists)
                else artists[0]
            )
        else:
            artist_variant = None

        pair = (title_variant, artist_variant)

        if pair not in pairs:
            pairs.append(pair)

    return pairs

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

    def search(self, track: LyricsRequest) -> list[LyricsResult]:
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

    def fetch_lyrics(self, result: LyricsResult) -> LyricsResult:
        """LRCLIB includes lyrics content in search results."""

        return result

    def _get_exact(
        self,
        track: LyricsRequest,
    ) -> LyricsResult | None:
        """Use LRCLIB's metadata-based lookup."""
        if not track.artist:
            return None

        for title, artist in _script_pairs(
            track.title,
            track.artist,
        ):
            params: dict[str, Any] = {
                "track_name": title,
                "artist_name": artist,
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
                continue

            response.raise_for_status()

            return _parse_lrclib_result(
                response.json()
            )

        return None

    def _search(
        self,
        track: LyricsRequest,
    ) -> list[LyricsResult]:
        """Search LRCLIB using clean title variants."""

        results: list[LyricsResult] = []
        seen_provider_ids: set[str] = set()

        for title in _search_title_variants(track.title)[:5]:
            for query_title in _script_variants(title):
                params: dict[str, Any] = {
                    "track_name": query_title,
                }

                try:
                    response = httpx.get(
                        f"{LRCLIB_API_URL}/search",
                        params=params,
                        headers=self.headers,
                        timeout=10.0,
                    )

                    response.raise_for_status()

                    data = response.json()

                except (httpx.HTTPError, ValueError):
                    continue

                if not isinstance(data, list):
                    continue

                for item in data:
                    result = _parse_lrclib_result(item)

                    if (
                        result.provider_id
                        in seen_provider_ids
                    ):
                        continue

                    seen_provider_ids.add(
                        result.provider_id
                    )
                    results.append(result)

                if results:
                    break

        return results
