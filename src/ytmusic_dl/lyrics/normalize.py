"""Text normalization and similarity helpers for lyrics matching."""

import re
from difflib import SequenceMatcher

from opencc import OpenCC

_OPENCC = OpenCC("t2s")

BRACKET_PATTERN = re.compile(
    r"[\(\（\[【]([^\)\）\]】]*)[\)\）\]】]"
)

NOISE_PATTERN = re.compile(
    r"\b(?:"
    r"official\s+music\s+video"
    r"|official\s+video"
    r"|music\s+video"
    r"|official\s+audio"
    r"|lyric\s+video"
    r"|lyrics?"
    r"|visuali[sz]er"
    r"|performance\s+video"
    r"|audio\s+only"
    r"|mv|m/v"
    r"|hd|hq|4k|8k"
    r"|1080p|2160p"
    r"|remaster(?:ed)?(?:\s+\d{4})?"
    r"|explicit"
    r")\b",
    re.IGNORECASE,
)

def _strip_title_noise(value: str) -> str:
    """Remove video and remaster noise from a title."""

    def replace_bracket(match: re.Match[str]) -> str:
        content = match.group(1)

        if NOISE_PATTERN.search(content):
            return " "

        return match.group(0)

    cleaned = BRACKET_PATTERN.sub(
        replace_bracket,
        value,
    )

    cleaned = NOISE_PATTERN.sub(" ", cleaned)

    # Drop brackets that became empty.
    cleaned = re.sub(
        r"[\(\（\[【]\s*[\)\）\]】]",
        " ",
        cleaned,
    )

    cleaned = re.sub(r"\s+", " ", cleaned)

    cleaned = cleaned.strip(" -–—|·.,")

    # Never reduce a title to nothing.
    return cleaned or value.strip()

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

    # Strip video and remaster noise so a clean provider title can
    # match a noisy YouTube title. This only adds a variant; other
    # signals still have to corroborate the match.
    noise_free = _strip_title_noise(title)

    if noise_free and noise_free != title:
        variants.append(noise_free)
        variants.append(_normalize_text(noise_free))

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
