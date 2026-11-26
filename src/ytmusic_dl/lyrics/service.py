"""Lyrics search, scoring, selection, and writing."""

from pathlib import Path

from ytmusic_dl.lyrics.providers import (
    LRCLIBProvider,
    NetEaseProvider,
)
from ytmusic_dl.lyrics.scoring import (
    MIN_TITLE_SIMILARITY,
    _artist_matches,
    _artist_similarity,
    _duration_score,
    _match_score,
    _title_similarity,
    confidence_for_score,
)
from ytmusic_dl.models import (
    LyricsCandidate,
    LyricsProvider,
    LyricsRequest,
    LyricsResult,
)

PROVIDERS: tuple[LyricsProvider, ...] = (
    LRCLIBProvider(),
    NetEaseProvider(),
)

def build_candidate(
    request: LyricsRequest,
    result: LyricsResult,
) -> LyricsCandidate:
    """Score a lyrics result and explain the match."""

    title_score = _title_similarity(
        request.title,
        result.track_name,
    )

    artist_score = _artist_similarity(
        request.artist,
        result.artist_name,
    )

    duration_score = _duration_score(
        request.duration,
        result.duration,
    )

    match_reasons: list[str] = []
    rejection_reasons: list[str] = []

    if title_score >= 0.90:
        match_reasons.append("title matches")
    elif title_score >= MIN_TITLE_SIMILARITY:
        match_reasons.append(
            f"title similarity {title_score:.2f}"
        )
    else:
        rejection_reasons.append(
            f"title similarity {title_score:.2f} is below "
            f"{MIN_TITLE_SIMILARITY:.2f}"
        )

    if not _artist_matches(
        request.artist,
        result.artist_name,
    ):
        rejection_reasons.append("artist does not match")
    elif artist_score >= 0.90:
        match_reasons.append("artist matches")
    else:
        match_reasons.append(
            f"artist similarity {artist_score:.2f}"
        )

    if request.duration is None or result.duration is None:
        match_reasons.append("duration not compared")
    else:
        difference = abs(request.duration - result.duration)

        if duration_score == 0.0:
            rejection_reasons.append(
                f"duration differs by {difference:.1f}s"
            )
        else:
            match_reasons.append(
                f"duration within {difference:.1f}s"
            )

    if result.synced_lyrics:
        match_reasons.append("synchronized lyrics available")
    elif result.plain_lyrics:
        match_reasons.append("plain lyrics available")

    score = _match_score(
        request,
        result,
    )

    # Prefer synced lyrics when metadata is otherwise equivalent.
    if result.synced_lyrics:
        score += 0.10

    return LyricsCandidate(
        result=result,
        score=score,
        confidence=confidence_for_score(score),
        match_reasons=match_reasons,
        rejection_reasons=rejection_reasons,
    )

def fetch_missing_lyrics(
    result: LyricsResult,
) -> LyricsResult:
    """Populate lyrics content using the provider that returned it."""

    if result.synced_lyrics or result.plain_lyrics:
        return result

    for provider in PROVIDERS:
        if provider.name == result.provider:
            return provider.fetch_lyrics(result)

    return result

def search_lyrics(request: LyricsRequest) -> list[LyricsResult]:
    """Search all lyrics providers for matching candidates."""

    results: list[LyricsResult] = []

    for provider in PROVIDERS:
        try:
            results.extend(
                provider.search(request)
            )
        except Exception as error:
            print(
                f"Warning: {provider.name} lyrics "
                f"provider failed: {error}"
            )

    return results

def search_candidates(
    request: LyricsRequest,
) -> list[LyricsCandidate]:
    """Search providers and score every returned result."""

    return [
        build_candidate(request, result)
        for result in search_lyrics(request)
    ]

def find_best_lyrics(
    request: LyricsRequest,
    results: list[LyricsResult],
) -> LyricsResult | None:
    """Find the best lyrics result for a track."""
    if not results:
        return None

    best_result = None
    best_score = 0.0

    for result in results:
        candidate = build_candidate(request, result)

        if not candidate.accepted:
            continue

        if candidate.score > best_score:
            best_score = candidate.score
            best_result = result

    if best_result is None:
        return None

    # Providers may return metadata-only candidates; fetch the
    # winning candidate's lyrics before handing it to the writer.
    return fetch_missing_lyrics(best_result)

def get_lyrics(
    request: LyricsRequest,
) -> LyricsResult | None:
    """Find the best available lyrics."""

    results = search_lyrics(request)

    return find_best_lyrics(
        request,
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
