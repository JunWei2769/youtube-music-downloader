"""Text normalization and similarity helpers for lyrics matching."""

import re
from difflib import SequenceMatcher

from opencc import OpenCC

_OPENCC = OpenCC("t2s")

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
