"""Flight plan parser — AI-powered extraction from text and images.

Extraction runs through the provider-independent ``LLMModule`` with
``purpose="flight_plan_parse"``, so any configured provider works.  Falls back
gracefully to basic keyword extraction when the provider is unavailable.

Usage::

    parser = FlightPlanParser(llm)
    result = await parser.from_text("VFR from KJFK to KBOS at 5500 in a C172")
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import get_settings
from app.llm import GenerationRequest, SceneConstraints, build_llm
from app.llm.types import LLMModule
from app.services.external.ocr_service import OCRService
from app.services.llm.prompts import FLIGHT_PLAN_PARSE_PROMPT

logger = logging.getLogger(__name__)

# Sampling and budget for a parse.  A parse must be near-deterministic and the
# whole JSON document must fit, so these are stated once here and travel as
# request constraints rather than as literals inside a provider's wire payload.
PARSE_CONSTRAINTS = SceneConstraints(temperature=0.1, max_output_tokens=500)

# Fields we expect from the LLM JSON response.
_EXPECTED_FIELDS = {
    "departure_icao",
    "arrival_icao",
    "alternate_icao",
    "aircraft_type",
    "cruise_altitude",
    "route_string",
    "flight_rules",
    "remarks",
}


class FlightPlanParser:
    """Parse flight plans from various sources using AI.

    Args:
        llm: Provider-independent language-model module.  When omitted, the
            module configured by the ``LLM_*`` settings is built on demand, which
            is what the not-yet-migrated route relies on.
        constraints: Sampling and token budget for a parse.  Defaults to
            :data:`PARSE_CONSTRAINTS`.
        language: Language of the parse prompt, carried on every request.
        ollama_base_url: Accepted only so the unmigrated caller keeps working.
            Redundant with ``LLM_BASE_URL`` and never used; the provider is
            chosen by ``LLM_PROVIDER``.
        model: Accepted for the same reason; redundant with ``LLM_MODEL``.
    """

    def __init__(
        self,
        llm: LLMModule | None = None,
        *,
        constraints: SceneConstraints | None = None,
        language: str = "en",
        ollama_base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        if ollama_base_url is not None or model is not None:
            logger.debug(
                "FlightPlanParser ignores ollama_base_url/model; the configured "
                "LLM provider supplies both"
            )
        self.llm = llm if llm is not None else build_llm(get_settings())
        self.constraints = PARSE_CONSTRAINTS if constraints is None else constraints
        self.language = language
        self._ocr = OCRService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def from_text(self, text: str) -> dict[str, Any]:
        """Parse a free-text flight plan into structured data.

        Tries the LLM first; falls back to regex-based keyword
        extraction if the LLM is unreachable or returns invalid JSON.

        Args:
            text: Free-text flight plan description.

        Returns:
            Dict with parsed flight plan fields.
        """
        prompt = FLIGHT_PLAN_PARSE_PROMPT.format(free_text=text)

        try:
            raw_response = await self._generate(prompt)
            parsed = self._extract_json(raw_response)
            if parsed:
                logger.info("Flight plan parsed via LLM: %s", list(parsed.keys()))
                return self._normalise(parsed)
        except Exception:
            logger.warning("LLM parsing failed — falling back to keyword extraction", exc_info=True)

        # Fallback: basic regex extraction
        return self._keyword_fallback(text)

    async def from_image(self, image_bytes: bytes) -> dict[str, Any]:
        """Extract and parse a flight plan from an uploaded image.

        Pipeline: OCR → text → LLM parse (with keyword fallback).

        Args:
            image_bytes: Raw image bytes (JPEG, PNG, etc.).

        Returns:
            Dict with parsed flight plan fields.
        """
        ocr_text = await self._ocr.extract_text(image_bytes)
        if not ocr_text:
            logger.warning("OCR returned empty text — returning placeholder data")
            return await self._ocr_structured_fallback(image_bytes)

        return await self.from_ocr_text(ocr_text)

    async def from_ocr_text(self, ocr_text: str) -> dict[str, Any]:
        """Parse OCR-extracted text into structured flight plan data.

        Identical to :pymethod:`from_text` but makes the two-step
        pipeline explicit.

        Args:
            ocr_text: Text previously extracted via OCR.

        Returns:
            Dict with parsed flight plan fields.
        """
        return await self.from_text(ocr_text)

    # ------------------------------------------------------------------
    # Provider integration
    # ------------------------------------------------------------------

    async def _generate(self, prompt: str) -> str:
        """Ask the configured provider to parse the plan.

        Returns:
            The model's text response, which :pymethod:`_extract_json` parses.

        Raises:
            LLMUnavailableError: No permitted provider could answer.
            LLMUsageError: The provider rejected the request.
        """
        result = await self.llm.generate(
            GenerationRequest(
                prompt=prompt,
                purpose="flight_plan_parse",
                scene_constraints=self.constraints,
                language=self.language,
            )
        )
        return result.text

    # ------------------------------------------------------------------
    # Response extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        """Extract the first JSON object from an LLM response string.

        Handles common LLM quirks like wrapping JSON in Markdown
        code fences.

        Returns:
            Parsed dict, or ``None`` if no valid JSON was found.
        """
        # Strip Markdown code fences
        cleaned = re.sub(r"```(?:json)?\s*", "", text)
        cleaned = cleaned.replace("```", "")

        # Try to find a JSON object in the text
        brace_start = cleaned.find("{")
        brace_end = cleaned.rfind("}")
        if brace_start == -1 or brace_end == -1 or brace_end <= brace_start:
            return None

        candidate = cleaned[brace_start : brace_end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
        return None

    @staticmethod
    def _normalise(data: dict[str, Any]) -> dict[str, Any]:
        """Normalise and validate parsed flight plan fields.

        Ensures ICAO codes are upper-case and fills missing keys
        with ``None``.
        """
        result: dict[str, Any] = {}
        for key in _EXPECTED_FIELDS:
            result[key] = data.get(key)

        # Uppercase ICAO codes
        for icao_key in ("departure_icao", "arrival_icao", "alternate_icao"):
            val = result.get(icao_key)
            if isinstance(val, str):
                result[icao_key] = val.upper().strip()

        # Uppercase flight rules
        rules = result.get("flight_rules")
        if isinstance(rules, str):
            result["flight_rules"] = rules.upper().strip()

        # Ensure cruise_altitude is int or None
        alt = result.get("cruise_altitude")
        if alt is not None:
            try:
                result["cruise_altitude"] = int(alt)
            except (ValueError, TypeError):
                result["cruise_altitude"] = None

        return result

    @staticmethod
    def _keyword_fallback(text: str) -> dict[str, Any]:
        """Best-effort extraction using regex patterns.

        This is the fallback when the LLM is unavailable.  It looks
        for common patterns like 4-letter ICAO codes, altitude numbers,
        aircraft type designators, and VFR/IFR keywords.
        """
        upper = text.upper()

        # ICAO codes (4-letter starting with K, E, L, etc.)
        icao_matches = re.findall(r"\b([A-Z]{4})\b", upper)
        # Filter likely ICAO codes (starting with K for US, or known prefixes)
        icao_codes = [
            c
            for c in icao_matches
            if c[0] in "KELCPSBDGMU" and c not in ("FROM", "PLAN", "KNOT", "WITH", "WILL")
        ]

        departure = icao_codes[0] if len(icao_codes) >= 1 else None
        arrival = icao_codes[1] if len(icao_codes) >= 2 else None
        alternate = icao_codes[2] if len(icao_codes) >= 3 else None

        # Flight rules
        flight_rules: str | None = None
        if "IFR" in upper:
            flight_rules = "IFR"
        elif "VFR" in upper:
            flight_rules = "VFR"

        # Altitude
        alt_match = re.search(r"(\d{3,5})\s*(?:FT|FEET|MSL|AGL|FL)?", upper)
        cruise_altitude: int | None = None
        if alt_match:
            candidate_alt = int(alt_match.group(1))
            if 500 <= candidate_alt <= 60000:
                cruise_altitude = candidate_alt

        # Aircraft type (common designators)
        aircraft_match = re.search(
            r"\b(C1[57][02]|PA[234]\d|BE[34]\d|B7[3-8]\d|A3[12]\d|SR2[02])\b", upper
        )
        aircraft_type = aircraft_match.group(1) if aircraft_match else None

        # Route string — look for space-separated identifiers
        route_match = re.search(r"ROUTE[:\s]+(.+?)(?:\n|$)", upper)
        route_string = route_match.group(1).strip() if route_match else None

        return {
            "departure_icao": departure,
            "arrival_icao": arrival,
            "alternate_icao": alternate,
            "aircraft_type": aircraft_type,
            "cruise_altitude": cruise_altitude,
            "route_string": route_string,
            "flight_rules": flight_rules,
            "remarks": None,
        }

    async def _ocr_structured_fallback(self, image_bytes: bytes) -> dict[str, Any]:
        """Use OCR service's structured extractor as a last resort."""
        try:
            return await self._ocr.extract_flight_plan(image_bytes)
        except Exception:
            logger.exception("OCR structured fallback also failed")
            return {k: None for k in _EXPECTED_FIELDS}
