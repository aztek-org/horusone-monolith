import re

from app.knowledge.chunking import chunk_document
from app.knowledge.documents import extract_text


def test_markdown_extract_and_chunk():
    text, hints = extract_text("manual.md", b"# Title\n\nSome text " * 200)
    assert hints["section"] == "Title"
    chunk_size = 100
    chunk_overlap = 15
    spans = chunk_document(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    assert len(spans) > 1
    assert spans[0][0] == 0 and spans[-1][1] <= len(text)
    assert spans[0][2] <= chunk_size

    tokens = list(re.finditer(r"\S+", text))
    token_starts = [match.start() for match in tokens]
    token_ends = [match.end() for match in tokens]
    stride = chunk_size - chunk_overlap
    for index, (char_start, char_end, token_count) in enumerate(spans):
        first_token = index * stride
        last_token = min(first_token + chunk_size, len(tokens)) - 1
        expected_start = 0 if index == 0 else token_starts[first_token]
        expected_end = token_ends[last_token]
        assert (char_start, char_end) == (expected_start, expected_end)
        assert text[char_start:char_end] == text[expected_start:expected_end]
        assert token_count == last_token - first_token + 1
        assert text[char_start:char_end] == text[char_start:char_end].strip()


def test_pdf_requires_pypdf():
    import pypdf

    assert pypdf.__version__ >= "5"
