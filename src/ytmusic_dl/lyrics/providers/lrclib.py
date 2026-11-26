"""LRCLIB lyrics provider."""

from typing import Any

import httpx

from ytmusic_dl.lyrics.constants import (
    LRCLIB_API_URL,
    USER_AGENT,
)
from ytmusic_dl.models import LyricsRequest, LyricsResult

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
        track: LyricsRequest,
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
