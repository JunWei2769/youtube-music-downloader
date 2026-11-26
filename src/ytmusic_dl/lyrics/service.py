"""Lyrics search, scoring, selection, and writing."""

from pathlib import Path

from ytmusic_dl.lyrics.providers import (
    LRCLIBProvider,
    NetEaseProvider,
)
from ytmusic_dl.lyrics.normalize import (
    _extract_editions,
    _normalize_text,
    _strip_title_noise,
)
from ytmusic_dl.lyrics.scoring import (
    MAJOR_EDITION_PENALTY,
    MAX_EDITION_PENALTY,
    MIN_TITLE_SIMILARITY,
    NEUTRAL_EDITIONS,
    _artist_matches,
    _artist_similarity,
    _duration_score,
    _match_score,
    _title_similarity,
    confidence_for_score,
)
from ytmusic_dl.log import get_logger
from ytmusic_dl.models import (
    LyricsCandidate,
    LyricsProvider,
    LyricsRequest,
    LyricsResult,
)

logger = get_logger("lyrics")

DEDUPE_DURATION_TOLERANCE = 2.0

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
    warnings: list[str] = []

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

    # ---------------------------------------------------------
    # Edition compatibility: prefer the requested version and
    # penalize live, acoustic, remix, instrumental, and similar
    # editions. Remasters are treated as the same recording.
    # ---------------------------------------------------------

    query_editions = _extract_editions(request.title)
    result_editions = _extract_editions(result.track_name)

    if (
        "instrumental" in result_editions
        and "instrumental" not in query_editions
    ):
        rejection_reasons.append("instrumental arrangement")

    for edition in sorted(query_editions & result_editions):
        match_reasons.append(f"{edition} edition")

    unexpected_editions = (
        result_editions
        - query_editions
        - NEUTRAL_EDITIONS
    )

    missing_editions = (
        query_editions
        - result_editions
        - NEUTRAL_EDITIONS
    )

    for edition in sorted(unexpected_editions):
        warnings.append(f"result is the {edition} edition")

    for edition in sorted(missing_editions):
        warnings.append(f"requested {edition} edition not found")

    edition_penalty = min(
        (
            len(unexpected_editions)
            + len(missing_editions)
        ) * MAJOR_EDITION_PENALTY,
        MAX_EDITION_PENALTY,
    )

    score = _match_score(
        request,
        result,
    )

    # Prefer synced lyrics when metadata is otherwise equivalent.
    if result.synced_lyrics:
        score += 0.10

    score = max(0.0, score - edition_penalty)

    return LyricsCandidate(
        result=result,
        score=score,
        confidence=confidence_for_score(score),
        match_reasons=match_reasons,
        rejection_reasons=rejection_reasons,
        warnings=warnings,
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
            logger.warning(
                "Lyrics provider %s failed: %s",
                provider.name,
                error,
            )

    return results

def search_candidates(
    request: LyricsRequest,
) -> list[LyricsCandidate]:
    """Search providers and score every returned result."""

    candidates = [
        build_candidate(request, result)
        for result in search_lyrics(request)
    ]

    return _dedupe_candidates(request, candidates)

def _is_duplicate(
    first: LyricsResult,
    second: LyricsResult,
) -> bool:
    """Return whether two results are the same recording."""

    if first.provider != second.provider:
        return False

    # Ignore video/remaster noise so the original and a remaster of
    # the same recording collapse into one candidate.
    if (
        _normalize_text(_strip_title_noise(first.track_name))
        != _normalize_text(_strip_title_noise(second.track_name))
    ):
        return False

    if (
        _normalize_text(first.artist_name)
        != _normalize_text(second.artist_name)
    ):
        return False

    if first.duration is None or second.duration is None:
        return first.duration is None and second.duration is None

    return (
        abs(first.duration - second.duration)
        <= DEDUPE_DURATION_TOLERANCE
    )

def _album_rank(
    request: LyricsRequest,
    album: str | None,
) -> int:
    """Rank how well a candidate album answers the query album."""

    if not request.album:
        return 0

    if not album:
        return 1

    if (
        _normalize_text(request.album)
        == _normalize_text(album)
    ):
        return 2

    return 0

def _dedupe_rank(
    request: LyricsRequest,
    candidate: LyricsCandidate,
) -> tuple[int, int, int]:
    """Rank which duplicate is more useful to keep."""

    result = candidate.result

    has_lyrics = int(
        bool(result.synced_lyrics or result.plain_lyrics)
    )

    edition_match = int(
        bool(
            _extract_editions(request.title)
            & _extract_editions(result.track_name)
        )
    )

    return (
        has_lyrics,
        edition_match,
        _album_rank(request, result.album_name),
    )

def _dedupe_candidates(
    request: LyricsRequest,
    candidates: list[LyricsCandidate],
) -> list[LyricsCandidate]:
    """Collapse duplicate recordings from the same provider."""

    deduped: list[LyricsCandidate] = []

    for candidate in candidates:
        for index, existing in enumerate(deduped):
            if not _is_duplicate(
                existing.result,
                candidate.result,
            ):
                continue

            if (
                _dedupe_rank(request, candidate)
                > _dedupe_rank(request, existing)
            ):
                deduped[index] = candidate

            break
        else:
            deduped.append(candidate)

    return deduped

def find_best_lyrics(
    request: LyricsRequest,
    results: list[LyricsResult],
) -> LyricsResult | None:
    """Find the best lyrics result for a track."""

    candidates = [
        build_candidate(request, result)
        for result in results
    ]

    best = pick_best_candidate(candidates)

    if best is None:
        return None

    # Providers may return metadata-only candidates; fetch the
    # winning candidate's lyrics before handing it to the writer.
    return fetch_missing_lyrics(best.result)

def pick_best_candidate(
    candidates: list[LyricsCandidate],
) -> LyricsCandidate | None:
    """Return the highest-scoring accepted candidate."""

    best: LyricsCandidate | None = None

    for candidate in candidates:
        if not candidate.accepted:
            continue

        if best is None or candidate.score > best.score:
            best = candidate

    return best

def find_best_candidate(
    request: LyricsRequest,
) -> LyricsCandidate | None:
    """Search providers and return the best accepted candidate."""

    return pick_best_candidate(
        search_candidates(request)
    )

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
