"""Whitespace-based chunking with character citation offsets."""

from __future__ import annotations

import re

_TOKEN_PATTERN = re.compile(r"\S+")


def chunk_document(
    text: str, chunk_size: int, chunk_overlap: int
) -> list[tuple[int, int, int]]:
    """Return ``(char_start, char_end, token_count)`` windows.

    Whitespace is used as the token approximation. Consecutive windows share
    ``chunk_overlap`` tokens, while the first window includes leading
    whitespace so a document's citation offsets begin at character zero.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must not be negative")

    tokens = list(_TOKEN_PATTERN.finditer(text))
    if not tokens:
        return []

    stride = max(1, chunk_size - min(chunk_overlap, chunk_size - 1))
    spans: list[tuple[int, int, int]] = []
    for start in range(0, len(tokens), stride):
        window = tokens[start : start + chunk_size]
        if not window:
            break
        char_start = 0 if start == 0 else window[0].start()
        char_end = window[-1].end()
        spans.append((char_start, char_end, len(window)))
        if start + chunk_size >= len(tokens):
            break
    return spans
