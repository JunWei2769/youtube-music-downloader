"""
Purpose: Lyrics-only command-line interface.

- Search providers without downloading audio
- Save the best or a selected lyrics candidate
- Report match confidence and reasons

Responsibility: Lyrics-only user interaction
"""

import argparse
from pathlib import Path

from ytmusic_dl.downloader import extract_single_track
from ytmusic_dl.lyrics import (
    search_candidates,
    write_lyrics,
)
from ytmusic_dl.models import (
    LyricsCandidate,
    LyricsQuery,
)
from ytmusic_dl.utils import build_lyrics_filename, format_duration

CONFIDENCE_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
}

DEFAULT_LYRICS_OUTPUT = Path("downloads/lyrics")

def _add_query_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    """Add arguments shared by lyrics search and download."""

    parser.add_argument(
        "query",
        help="Song title or YouTube Music URL",
    )

    parser.add_argument(
        "--artist",
        help="Artist name (required when searching by title)",
    )

    parser.add_argument(
        "--album",
        help="Album name",
    )

    parser.add_argument(
        "--duration",
        type=float,
        metavar="SECONDS",
        help="Track duration in seconds",
    )

def build_lyrics_parser() -> argparse.ArgumentParser:
    """Build the parser for `ytmusic-dl lyrics`."""

    parser = argparse.ArgumentParser(
        prog="ytmusic-dl lyrics",
        description=(
            "Search and download lyrics without downloading audio."
        ),
    )

    subparsers = parser.add_subparsers(
        dest="action",
        required=True,
    )

    search_parser = subparsers.add_parser(
        "search",
        help="Search lyrics providers without saving anything",
        description=(
            "Search lyrics providers and show every scored candidate."
        ),
    )

    _add_query_arguments(search_parser)

    download_parser = subparsers.add_parser(
        "download",
        help="Search lyrics providers and save a lyrics file",
        description=(
            "Search lyrics providers and save the best or a selected "
            "candidate as an .lrc file."
        ),
    )

    _add_query_arguments(download_parser)

    selection = download_parser.add_mutually_exclusive_group(
        required=True,
    )

    selection.add_argument(
        "--best",
        action="store_true",
        help="Save the highest-scoring accepted candidate",
    )

    selection.add_argument(
        "--select",
        type=int,
        metavar="N",
        help="Save candidate N from the candidate list",
    )

    download_parser.add_argument(
        "--min-confidence",
        choices=("low", "medium", "high"),
        default="medium",
        help=(
            "Minimum confidence required by --best (default: medium)"
        ),
    )

    download_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_LYRICS_OUTPUT,
        help=(
            "Output directory "
            f"(default: {DEFAULT_LYRICS_OUTPUT})"
        ),
    )

    download_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing lyrics file",
    )

    return parser

def _build_query(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> LyricsQuery | None:
    """Build a lyrics query from CLI arguments."""

    query = args.query.strip()

    if query.startswith(("http://", "https://")):
        try:
            tracks = extract_single_track(query)
        except Exception as error:
            print(f"Error: could not read track metadata: {error}")
            return None

        if not tracks:
            print("Error: no track metadata found for that URL.")
            return None

        track = tracks[0]

        return LyricsQuery(
            title=track.title,
            artist=args.artist or track.artist,
            album=args.album or track.album,
            duration=(
                args.duration
                if args.duration is not None
                else track.duration
            ),
            video_id=track.video_id,
            webpage_url=track.webpage_url or query,
        )

    if not args.artist:
        parser.error(
            "--artist is required when searching by title"
        )

    return LyricsQuery(
        title=query,
        artist=args.artist,
        album=args.album,
        duration=args.duration,
    )

def _sort_candidates(
    candidates: list[LyricsCandidate],
) -> list[LyricsCandidate]:
    """Sort candidates by score, keeping provider order for ties."""

    return sorted(
        candidates,
        key=lambda candidate: candidate.score,
        reverse=True,
    )

def _print_query(query: LyricsQuery) -> None:
    """Print the query being searched."""

    print(
        f"Title:    {query.title}\n"
        f"Artist:   {query.artist or 'Unknown'}\n"
        f"Album:    {query.album or 'Unknown'}\n"
        f"Duration: {format_duration(query.duration)}"
    )

    print()

def _print_candidates(
    candidates: list[LyricsCandidate],
) -> None:
    """Print scored candidates."""

    if not candidates:
        print("No lyrics candidates found.")
        return

    for index, candidate in enumerate(candidates, start=1):
        result = candidate.result

        if candidate.accepted:
            status = candidate.confidence
        else:
            status = "rejected"

        print(
            f"{index}. [{status}] {result.provider} — "
            f"{result.track_name} — {result.artist_name}"
        )

        print(f"   Album:    {result.album_name or 'Unknown'}")
        print(f"   Duration: {format_duration(result.duration)}")
        print(f"   Score:    {candidate.score:.2f}")

        if candidate.match_reasons:
            print(
                f"   Matches:  "
                f"{'; '.join(candidate.match_reasons)}"
            )

        if candidate.rejection_reasons:
            print(
                f"   Rejected: "
                f"{'; '.join(candidate.rejection_reasons)}"
            )

        print()

def _run_search(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    """Run `ytmusic-dl lyrics search`."""

    query = _build_query(args, parser)

    if query is None:
        return 1

    _print_query(query)

    candidates = _sort_candidates(
        search_candidates(query)
    )

    _print_candidates(candidates)

    return 0

def _is_confident_enough(
    candidate: LyricsCandidate,
    minimum: str,
) -> bool:
    """Return whether a candidate meets the confidence floor."""

    return (
        CONFIDENCE_ORDER[candidate.confidence]
        >= CONFIDENCE_ORDER[minimum]
    )

def _select_candidate(
    args: argparse.Namespace,
    candidates: list[LyricsCandidate],
) -> LyricsCandidate | None:
    """Resolve --best or --select to a single candidate."""

    if args.select is not None:
        if not 1 <= args.select <= len(candidates):
            print(
                f"Error: --select must be between 1 and "
                f"{len(candidates)}."
            )
            return None

        candidate = candidates[args.select - 1]

        if candidate.rejection_reasons:
            print(
                "Error: the selected candidate was rejected: "
                f"{'; '.join(candidate.rejection_reasons)}"
            )
            return None

        return candidate

    accepted = [
        candidate
        for candidate in candidates
        if candidate.accepted
    ]

    if not accepted:
        print(
            "Error: no candidate passed the match checks. "
            "Use --select to choose one manually."
        )
        return None

    best = accepted[0]

    if not _is_confident_enough(best, args.min_confidence):
        print(
            f"Error: the best candidate has {best.confidence} "
            f"confidence, below --min-confidence "
            f"{args.min_confidence}. "
            "Use --select to choose manually or lower the threshold."
        )
        return None

    return best

def _run_download(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    """Run `ytmusic-dl lyrics download`."""

    query = _build_query(args, parser)

    if query is None:
        return 1

    _print_query(query)

    candidates = _sort_candidates(
        search_candidates(query)
    )

    _print_candidates(candidates)

    if not candidates:
        return 1

    candidate = _select_candidate(args, candidates)

    if candidate is None:
        return 1

    filename = build_lyrics_filename(
        query.title,
        query.artist,
    )

    output_path = args.output / f"{filename}.lrc"

    if output_path.exists() and not args.overwrite:
        print(f"Already exists: {output_path}")
        print("Use --overwrite to replace it.")
        return 0

    try:
        write_lyrics(candidate.result, output_path)
    except ValueError as error:
        print(f"Error: {error}")
        return 1

    print(f"Saved:      {output_path}")
    print(f"Provider:   {candidate.result.provider}")
    print(f"Confidence: {candidate.confidence}")

    return 0

def run_lyrics_command(
    argv: list[str] | None = None,
) -> int:
    """Run a lyrics-only command and return an exit code."""

    parser = build_lyrics_parser()
    args = parser.parse_args(argv)

    if args.action == "search":
        return _run_search(args, parser)

    return _run_download(args, parser)
