"""Flight plan parser — AI-powered extraction from text and images.

Uses Ollama (via ``httpx``) to parse free-text flight plan descriptions
into structured data.  Falls back gracefully to basic keyword extraction
when the LLM is unavailable.

Usage::

    parser = FlightPlanParser(
        ollama_base_url="http://localhost:11434",
        model="llama3:latest",
    )
    result = await parser.from_text("VFR from KJFK to KBOS at 5500 in a C172")
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.services.external.ocr_service import OCRService
from app.services.llm.prompts import FLIGHT_PLAN_PARSE_PROMPT

logger = logging.getLogger(__name__)

# Timeout for Ollama requests — generous because LLM inference is slow.
_OLLAMA_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)

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
        ollama_base_url: Ollama REST API base URL.
        model: Model name to use (e.g. ``"llama3:latest"``).
    """

    def __init__(self, ollama_base_url: str, model: str) -> None:
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.model = model
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
            raw_response = await self._call_ollama(prompt)
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
    # Ollama integration
    # ------------------------------------------------------------------

    async def _call_ollama(self, prompt: str) -> str:
        """Send a prompt to the Ollama ``/api/generate`` endpoint.

        Returns:
            The model's text response.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses.
            httpx.ConnectError: If Ollama is unreachable.
        """
        url = f"{self.ollama_base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 500,
            },
        }

        async with httpx.AsyncClient(timeout=_OLLAMA_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return str(data.get("response", ""))

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
            c for c in icao_matches
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
