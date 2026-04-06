"""OCR service — placeholder for flight-plan image text extraction.

In production, swap the stub implementation for a real OCR backend:

* **Tesseract** — open-source, self-hosted via ``pytesseract``.
* **Google Cloud Vision** — high accuracy, requires GCP credentials.
* **AWS Textract** — form-aware extraction, requires AWS credentials.

The public interface is fully async so integrating a real HTTP-based
OCR API (e.g. Vision AI REST endpoint) requires no caller changes.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sample / placeholder data returned when no real OCR backend is available.
# ---------------------------------------------------------------------------

_SAMPLE_EXTRACTED_TEXT = (
    "VFR Flight Plan\n"
    "Aircraft: C172\n"
    "Departure: KJFK\n"
    "Arrival: KBOS\n"
    "Altitude: 5500\n"
    "Route: KJFK MERIT GREKI KBOS\n"
    "Remarks: Student pilot training flight"
)

_SAMPLE_STRUCTURED: dict[str, Any] = {
    "departure_icao": "KJFK",
    "arrival_icao": "KBOS",
    "alternate_icao": None,
    "aircraft_type": "C172",
    "cruise_altitude": 5500,
    "route_string": "KJFK MERIT GREKI KBOS",
    "flight_rules": "VFR",
    "remarks": "Student pilot training flight",
}


class OCRService:
    """Async interface for extracting text from flight-plan images.

    The current implementation returns **placeholder** data.  Replace
    ``extract_text`` and ``extract_flight_plan`` with calls to a real
    OCR provider when available.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def extract_text(self, image_bytes: bytes) -> str:
        """Extract raw text from an image.

        Args:
            image_bytes: Raw image bytes (JPEG, PNG, etc.).

        Returns:
            Extracted text string.  Returns sample text when no real
            OCR backend is configured.
        """
        if not image_bytes:
            logger.warning("OCR extract_text called with empty image")
            return ""

        logger.info(
            "OCR extract_text called (%d bytes) — returning placeholder",
            len(image_bytes),
        )
        # TODO: Replace with real OCR call, e.g.:
        #   async with httpx.AsyncClient() as client:
        #       resp = await client.post(ocr_url, content=image_bytes)
        #       return resp.json()["text"]
        return _SAMPLE_EXTRACTED_TEXT

    async def extract_flight_plan(self, image_bytes: bytes) -> dict[str, Any]:
        """Extract a structured flight plan from an image.

        This is a higher-level method that combines OCR text extraction
        with field parsing.  In production it may use a form-aware OCR
        engine (e.g. AWS Textract AnalyzeDocument) directly.

        Args:
            image_bytes: Raw image bytes.

        Returns:
            Dict with parsed flight plan fields.  Returns sample
            structured data when no real OCR backend is configured.
        """
        if not image_bytes:
            logger.warning("OCR extract_flight_plan called with empty image")
            return {}

        logger.info(
            "OCR extract_flight_plan called (%d bytes) — returning placeholder",
            len(image_bytes),
        )
        return dict(_SAMPLE_STRUCTURED)
