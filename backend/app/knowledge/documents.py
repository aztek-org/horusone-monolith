"""Text extraction and source-type handling for knowledge uploads."""

from __future__ import annotations

import io
from pathlib import Path


def source_type(filename: str) -> str:
    """Return the supported source type for an upload filename."""
    suffix = Path(filename).suffix.lower()
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix == ".txt":
        return "text"
    if suffix == ".pdf":
        return "pdf"
    raise ValueError(f"Unsupported knowledge document format: {filename}")


def extract_text(filename: str, content: bytes) -> tuple[str, dict[str, int | str | None]]:
    """Extract searchable text and citation hints from an upload.

    Markdown and text uploads are UTF-8 decoded. PDF uploads are parsed with
    pypdf; v1 records the first page as a coarse citation hint while joining
    all extracted page text for the document.
    """
    kind = source_type(filename)
    if kind in {"markdown", "text"}:
        text = content.decode("utf-8")
        hints: dict[str, int | str | None] = {
            "page": None,
            "section": None,
        }
        if kind == "markdown":
            for line in text.splitlines():
                if line.startswith("# "):
                    hints["section"] = line[2:].strip()
                    break
        return text, hints

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages), {"page": 1 if pages else None, "section": None}
