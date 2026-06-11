from __future__ import annotations

import re


NORMALIZATION_VERSION = "2026-05-09-v1"

_URL_START_RE = re.compile(r"(https?://|www\.)", re.IGNORECASE)
_DOMAIN_FRAGMENT_RE = re.compile(r"\b[a-z0-9-]+(?:\s*\.\s*[a-z0-9-]+){1,}\b")
_DOMAIN_PATH_WRAP_RE = re.compile(
    r"((?:[a-z0-9-]+\.)+[a-z]{2,})\s*\n\s*(?=[A-Za-z0-9/_?#=&.%~+-])"
)
_ZERO_WIDTH_CHARS_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
_URL_ALLOWED_CHARS = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
    "-._~:/?#[]@!$&'()*+,;=%"
)


def normalize_text_for_retrieval(text: str) -> tuple[str, dict[str, int | bool | str]]:
    if not text:
        return text, _build_report(text, text, 0, 0, 0)

    original = text
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    zero_width_count = len(_ZERO_WIDTH_CHARS_RE.findall(text))
    text = _ZERO_WIDTH_CHARS_RE.sub("", text)

    special_space_count = text.count("\u00a0") + text.count("\u3000")
    text = text.replace("\u00a0", " ").replace("\u3000", " ")

    text, url_repairs = _repair_broken_urls(text)
    text, domain_repairs = _repair_broken_domains(text)
    text = _normalize_whitespace(text)

    return text, _build_report(
        original,
        text,
        url_repairs,
        domain_repairs,
        zero_width_count + special_space_count,
    )


def _repair_broken_urls(text: str) -> tuple[str, int]:
    if not text:
        return text, 0

    parts: list[str] = []
    repairs = 0
    cursor = 0

    while True:
        match = _URL_START_RE.search(text, cursor)
        if not match:
            parts.append(text[cursor:])
            break

        parts.append(text[cursor:match.start()])
        start = match.start()
        end = match.end()
        saw_newline_gap = False

        while end < len(text):
            char = text[end]
            if char in _URL_ALLOWED_CHARS:
                end += 1
                continue

            if char.isspace():
                gap_end = end
                saw_newline = False
                while gap_end < len(text) and text[gap_end].isspace():
                    if text[gap_end] == "\n":
                        saw_newline = True
                    gap_end += 1

                if saw_newline and gap_end < len(text) and text[gap_end] in _URL_ALLOWED_CHARS:
                    saw_newline_gap = True
                    end = gap_end
                    continue
                break

            break

        fragment = text[start:end]
        if saw_newline_gap:
            cleaned = "".join(fragment.split())
            if cleaned != fragment:
                repairs += 1
            parts.append(cleaned)
        else:
            parts.append(fragment)

        cursor = end

    return "".join(parts), repairs


def _repair_broken_domains(text: str) -> tuple[str, int]:
    repairs = 0

    def normalize_domain_fragment(match: re.Match[str]) -> str:
        nonlocal repairs
        fragment = match.group(0)
        cleaned = re.sub(r"\s*\.\s*", ".", fragment)
        if cleaned != fragment:
            repairs += 1
        return cleaned

    text = _DOMAIN_FRAGMENT_RE.sub(normalize_domain_fragment, text)

    def normalize_domain_path(match: re.Match[str]) -> str:
        nonlocal repairs
        repairs += 1
        return match.group(1)

    text = _DOMAIN_PATH_WRAP_RE.sub(normalize_domain_path, text)
    return text, repairs


def _normalize_whitespace(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t\f\v]+", " ", line)
        lines.append(line.rstrip())

    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _build_report(
    original_text: str,
    normalized_text: str,
    url_repairs: int,
    domain_repairs: int,
    space_repairs: int,
) -> dict[str, int | bool | str]:
    return {
        "version": NORMALIZATION_VERSION,
        "changed": original_text != normalized_text,
        "url_repairs": url_repairs,
        "domain_repairs": domain_repairs,
        "space_repairs": space_repairs,
        "original_length": len(original_text),
        "normalized_length": len(normalized_text),
    }
