from app.knowledge.chunking import chunk_document
from app.knowledge.documents import extract_text


def test_markdown_extract_and_chunk():
    text, hints = extract_text("manual.md", b"# Title\n\nSome text " * 200)
    assert hints["section"] == "Title"
    spans = chunk_document(text, chunk_size=100, chunk_overlap=15)
    assert len(spans) > 1
    assert spans[0][0] == 0 and spans[-1][1] <= len(text)
    assert spans[0][2] <= 100


def test_pdf_requires_pypdf():
    import pypdf

    assert pypdf.__version__ >= "5"
