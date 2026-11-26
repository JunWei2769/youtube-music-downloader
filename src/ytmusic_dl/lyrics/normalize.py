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

# Edition words are matched inside brackets first, where they are
# unambiguous. Bare title words such as "Live" or "Piano" are only
# treated as editions when they form a known phrase or suffix, so
# songs like "Live Forever" and "Piano Man" stay untouched.

_BRACKET_EDITIONS = {
    "live": r"\blive\b|现场|演唱会",
    "remaster": r"remaster|重制|重置|母带",
    "acoustic": r"acoustic|unplugged|不插电",
    "instrumental": (
        r"instrumental|karaoke|pianoforte|"
        r"\bpiano\b|backing track|伴奏|纯音乐|钢琴"
    ),
    "remix": r"remix|rework|bootleg|\bdj\b|dj版|混音",
    "cover": r"\bcover\b|tribute|翻唱",
    "demo": r"\bdemo\b|小样",
    "radio_edit": r"radio edit|single edit",
    "extended": r"extended",
    "speed": r"sped up|slowed|nightcore|reverb",
}

_TITLE_EDITIONS = {
    "live": (
        r"\blive (?:at|in|from|version|session)\b|"
        r"现场版|演唱会版"
    ),
    "remaster": r"remaster|重制版|重置版|母带",
    "acoustic": r"\bacoustic\b|\bunplugged\b|不插电",
    "instrumental": (
        r"\binstrumental\b|\bkaraoke\b|\bpianoforte\b|"
        r"\bpiano version\b|backing track|伴奏|纯音乐"
    ),
    "remix": r"\bremix\b|\brework\b|\bbootleg\b|混音",
    "cover": r"\bcover version\b|\bcover by\b|翻唱版",
    "demo": r"\bdemo version\b|小样",
    "radio_edit": r"\bradio edit\b|\bsingle edit\b",
    "extended": (
        r"\bextended version\b|\bextended mix\b|"
        r"\bextended edit\b"
    ),
    "speed": r"\bsped up\b|\bslowed\b|\bnightcore\b|\breverb\b",
}

_SUFFIX_EDITIONS = {
    "live": r"\s[-–—]\s*live$|\s[-–—]\s*现场版$",
    "acoustic": r"\s[-–—]\s*acoustic$",
    "remix": r"\s[-–—]\s*remix$",
    "instrumental": r"\s[-–—]\s*instrumental$",
    "demo": r"\s[-–—]\s*demo$",
    "cover": r"\s[-–—]\s*cover$",
}

def _extract_editions(title: str) -> frozenset[str]:
    """Return the edition tags present in a title."""

    text = _normalize_text(title)

    if not text:
        return frozenset()

    editions: set[str] = set()

    for content in re.findall(BRACKET_PATTERN, text):
        for edition, pattern in _BRACKET_EDITIONS.items():
            if re.search(pattern, content):
                editions.add(edition)

    for edition, pattern in _TITLE_EDITIONS.items():
        if re.search(pattern, text):
            editions.add(edition)

    for edition, pattern in _SUFFIX_EDITIONS.items():
        if re.search(pattern, text):
            editions.add(edition)

    return frozenset(editions)

_ALBUM_NOISE = re.compile(
    r"\b("
    r"deluxe|expanded|anniversary|special|bonus|edition|"
    r"remaster(?:ed)?(?:\s+\d{4})?|version|soundtrack"
    r")\b",
    re.IGNORECASE,
)

def _normalize_album(value: str | None) -> str:
    """Normalize an album name for comparison."""

    if not value:
        return ""

    text = _normalize_text(value)

    # Edition and packaging details live in brackets, for example
    # "Whenever You Need Somebody (Deluxe Edition / Remastered 2022)".
    text = BRACKET_PATTERN.sub(" ", text)
    text = _ALBUM_NOISE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip(" -–—|·.,")

def _albums_match(
    first: str | None,
    second: str | None,
) -> bool:
    """Return whether two album names refer to the same album."""

    first_normalized = _normalize_album(first)
    second_normalized = _normalize_album(second)

    return (
        bool(first_normalized)
        and first_normalized == second_normalized
    )
