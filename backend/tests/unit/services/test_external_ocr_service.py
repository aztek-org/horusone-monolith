"""Unit tests for the external OCRService placeholder behaviour.

The service is a documented stub: non-empty images yield canned sample
data, empty images yield empty results.  These tests pin that contract so
a future real backend swap is explicit.
"""

from __future__ import annotations

import pytest

from app.services.external import ocr_service as ocr_module
from app.services.external.ocr_service import OCRService


class TestExtractText:
    """Tests for OCRService.extract_text()."""

    @pytest.mark.asyncio
    async def test_returns_placeholder_text_for_non_empty_image(self) -> None:
        service = OCRService()

        text = await service.extract_text(b"\xff\xd8\xff\xe0fake-jpeg")

        assert text == ocr_module._SAMPLE_EXTRACTED_TEXT
        assert "Departure: KJFK" in text
        assert "Arrival: KBOS" in text

    @pytest.mark.asyncio
    async def test_empty_image_returns_empty_string(self) -> None:
        service = OCRService()

        assert await service.extract_text(b"") == ""

    @pytest.mark.asyncio
    async def test_never_calls_a_network_client(self) -> None:
        """The stub must not import or open an httpx client."""
        service = OCRService()

        assert not hasattr(service, "_client")
        assert await service.extract_text(b"x") == ocr_module._SAMPLE_EXTRACTED_TEXT


class TestExtractFlightPlan:
    """Tests for OCRService.extract_flight_plan()."""

    @pytest.mark.asyncio
    async def test_returns_placeholder_structured_data(self) -> None:
        service = OCRService()

        plan = await service.extract_flight_plan(b"\x89PNG-fake")

        assert plan["departure_icao"] == "KJFK"
        assert plan["arrival_icao"] == "KBOS"
        assert plan["aircraft_type"] == "C172"
        assert plan["cruise_altitude"] == 5500
        assert plan["flight_rules"] == "VFR"
        assert plan["alternate_icao"] is None

    @pytest.mark.asyncio
    async def test_empty_image_returns_empty_dict(self) -> None:
        service = OCRService()

        assert await service.extract_flight_plan(b"") == {}

    @pytest.mark.asyncio
    async def test_returns_a_copy_of_the_module_constant(self) -> None:
        """Callers must not be able to mutate the shared placeholder."""
        service = OCRService()

        plan = await service.extract_flight_plan(b"image")
        plan["departure_icao"] = "MUTATED"

        assert ocr_module._SAMPLE_STRUCTURED["departure_icao"] == "KJFK"
