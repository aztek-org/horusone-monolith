"""Golden-file test: the ingest manual must survive the ingest path it documents.

``docs/knowledge/INGEST.md`` is the operator-facing description of the knowledge
ingest path. A manual that cannot be ingested by that path, or that stops
agreeing with the shipped defaults, is no longer documentation of this system.

These tests need no database: they exercise ``extract_text`` and
``chunk_document``, the two pure steps that decide what a Markdown upload
becomes. The concrete values asserted here are the ones a shipped default has
previously drifted away from — see the "Shipped defaults are part of the
contract" section of
``docs/architecture/ADR-009-opentelemetry-and-postgres-trace.md``.
"""

from pathlib import Path

from app.config import KnowledgeSettings
from app.knowledge.chunking import chunk_document
from app.knowledge.documents import extract_text

INGEST_MANUAL = Path(__file__).parents[4] / "docs" / "knowledge" / "INGEST.md"


def _manual() -> tuple[str, dict[str, int | str | None], list[tuple[int, int, int]]]:
    """Run the manual through the real Markdown extraction and chunking path."""
    text, hints = extract_text("INGEST.md", INGEST_MANUAL.read_bytes())
    settings = KnowledgeSettings()
    spans = chunk_document(text, settings.chunk_size, settings.chunk_overlap)
    return text, hints, spans


def test_manual_ingests_into_at_least_one_chunk() -> None:
    text, _, spans = _manual()

    assert text
    assert len(spans) > 0
    assert spans[0][0] == 0


def test_first_chunk_states_the_chunking_contract() -> None:
    """The manual's contract sentence must survive into the first chunk.

    The manual hyphenates: it writes "1000-token window", not "1000 tokens".
    """
    text, _, spans = _manual()
    first_chunk = text[spans[0][0] : spans[0][1]]

    assert "1000-token" in first_chunk


def test_manual_agrees_with_shipped_chunking_defaults() -> None:
    """The manual's contract sentence is derived from the shipped settings.

    This is the assertion that would have caught ``chunk_overlap`` shipping as
    200 while the contract said 150. Both numbers are read from the settings
    object, so changing a default and the manual together is a deliberate edit
    rather than an accident.
    """
    text, _, _ = _manual()
    settings = KnowledgeSettings()

    assert f"{settings.chunk_size}-token window" in text
    assert f"{settings.chunk_overlap}-token" in text


def test_manual_agrees_with_shipped_embedding_dimension() -> None:
    """The dimension lock in the manual is the dimension the code expects."""
    text, _, _ = _manual()
    settings = KnowledgeSettings()

    assert f"{settings.embedding_dimensions}-dimensional" in text


def test_manual_names_the_environment_variables_it_tells_operators_to_set() -> None:
    text, _, _ = _manual()

    for env_name in (
        "KNOWLEDGE_CHUNK_SIZE",
        "KNOWLEDGE_CHUNK_OVERLAP",
        "KNOWLEDGE_EMBEDDING_DIMENSIONS",
        "KNOWLEDGE_DEFAULT_CHUNK_QUOTA",
    ):
        assert env_name in text, f"{env_name} is documented in config but not in the manual"


def test_markdown_section_hint_is_the_first_h1() -> None:
    text, hints, _ = _manual()

    first_h1 = next(
        line[2:].strip() for line in text.splitlines() if line.startswith("# ")
    )
    assert hints["section"] == first_h1
    assert hints["page"] is None


def test_every_chunk_quotes_the_extracted_source_exactly() -> None:
    """Citation offsets must round-trip, or a citation points at the wrong text."""
    text, _, spans = _manual()

    for start, end, token_count in spans:
        assert 0 <= start < end <= len(text)
        assert token_count > 0
        assert text[start:end].strip()
