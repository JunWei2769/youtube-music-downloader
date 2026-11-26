"""Build lyrics queries from desktop input."""

from ytmusic_dl.downloader import extract_single_track
from ytmusic_dl.models import LyricsQuery

def build_lyrics_query(
    text: str,
    *,
    artist: str | None = None,
    album: str | None = None,
    duration: float | None = None,
) -> LyricsQuery:
    """Build a LyricsQuery from a title or YouTube Music URL."""

    text = text.strip()

    if not text:
        raise ValueError(
            "Enter a song title or YouTube Music URL."
        )

    if text.startswith(("http://", "https://")):
        tracks = extract_single_track(text)

        if not tracks:
            raise ValueError(
                "No track metadata found for that URL."
            )

        track = tracks[0]

        return LyricsQuery(
            title=track.title,
            artist=artist or track.artist,
            album=album or track.album,
            duration=(
                duration
                if duration is not None
                else track.duration
            ),
            video_id=track.video_id,
            webpage_url=track.webpage_url or text,
        )

    if not artist:
        raise ValueError(
            "Artist is required when searching by title."
        )

    return LyricsQuery(
        title=text,
        artist=artist,
        album=album,
        duration=duration,
    )
