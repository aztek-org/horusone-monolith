"""Weather data tools — mock METAR/TAF fetch and parsing.

In production these would call the Aviation Weather Center API
(aviationweather.gov) or a DATIS feed.  For the MVP we return
realistic but static mock data for major US airports.
"""

from __future__ import annotations

import re
from typing import Any

# ── Mock METAR database ──────────────────────────────────────────────

MOCK_METARS: dict[str, str] = {
    "KJFK": ("KJFK 151856Z 28012G18KT 10SM FEW040 SCT250 22/12 A3012 RMK AO2 SLP203 T02220117"),
    "KLAX": ("KLAX 151853Z 25008KT 10SM FEW025 SCT200 24/15 A2992 RMK AO2 SLP133 T02440150"),
    "KORD": (
        "KORD 151851Z 31015G22KT 6SM -RA BR SCT015 BKN025 OVC040 "
        "18/16 A2978 RMK AO2 SLP084 T01830161"
    ),
    "KATL": ("KATL 151852Z 18006KT 10SM SCT050 BKN120 28/19 A3008 RMK AO2 SLP185 T02830189"),
    "KSFO": ("KSFO 151856Z 29014KT 10SM FEW010 SCT200 18/11 A2998 RMK AO2 SLP153 T01780111"),
    "KDEN": ("KDEN 151853Z 17008KT 10SM FEW100 SCT200 30/08 A3022 RMK AO2 SLP143 T03000078"),
    "KMIA": ("KMIA 151853Z 14010KT 8SM SCT025 BKN060 31/24 A2990 RMK AO2 SLP123 T03110239"),
}

MOCK_TAFS: dict[str, str] = {
    "KJFK": (
        "TAF KJFK 151730Z 1518/1624 28012G18KT P6SM FEW040 SCT250 "
        "FM152200 30010KT P6SM SCT040 "
        "FM160400 33008KT P6SM FEW050"
    ),
    "KLAX": ("TAF KLAX 151730Z 1518/1624 25008KT P6SM FEW025 SCT200 FM160000 VRB04KT P6SM FEW015"),
    "KORD": (
        "TAF KORD 151730Z 1518/1624 31015G22KT 6SM -RA BR "
        "SCT015 BKN025 OVC040 "
        "FM152300 32010KT P6SM SCT030 "
        "FM160600 34006KT P6SM FEW040"
    ),
    "KATL": ("TAF KATL 151730Z 1518/1624 18006KT P6SM SCT050 BKN120 FM160000 20008KT P6SM SCT060"),
    "KSFO": ("TAF KSFO 151730Z 1518/1624 29014KT P6SM FEW010 SCT200 FM160200 VRB03KT P6SM FEW008"),
}

# ── Default / fallback METAR for unknown airports
DEFAULT_METAR = "{icao} 151856Z 00000KT 10SM CLR 20/10 A3000 RMK AO2 SLP200 T02000100"
DEFAULT_TAF = "TAF {icao} 151730Z 1518/1624 00000KT P6SM SKC"


# ── Fetch functions (mock) ────────────────────────────────────────────


def fetch_metar(icao: str) -> str:
    """Fetch a METAR string for the given ICAO airport code.

    Returns mock data for known airports, a generic clear-sky METAR
    for unknown ones.
    """
    icao = icao.upper().strip()
    return MOCK_METARS.get(icao, DEFAULT_METAR.format(icao=icao))


def fetch_taf(icao: str) -> str:
    """Fetch a TAF string for the given ICAO airport code.

    Returns mock data for known airports, a generic clear TAF otherwise.
    """
    icao = icao.upper().strip()
    return MOCK_TAFS.get(icao, DEFAULT_TAF.format(icao=icao))


# ── Parsing ───────────────────────────────────────────────────────────


def parse_metar(raw: str) -> dict[str, Any]:
    """Parse a raw METAR string into structured components.

    This is a *simplified* parser covering the fields most relevant
    to pre-flight validation.  It does NOT handle every METAR quirk.

    Returns:
        Dict with keys: station, wind_dir, wind_speed, wind_gust,
        visibility_sm, ceiling_ft, sky_layers, temperature, dewpoint,
        altimeter, flight_category, raw.
    """
    result: dict[str, Any] = {"raw": raw}
    tokens = raw.split()

    if not tokens:
        return result

    # Station (first 4-letter code)
    result["station"] = tokens[0] if len(tokens[0]) == 4 else ""

    # Wind — e.g. 28012G18KT or VRB04KT
    wind_match = re.search(r"(\d{3}|VRB)(\d{2,3})(G(\d{2,3}))?KT", raw)
    if wind_match:
        direction = wind_match.group(1)
        result["wind_dir"] = int(direction) if direction != "VRB" else 0
        result["wind_speed"] = int(wind_match.group(2))
        result["wind_gust"] = int(wind_match.group(4)) if wind_match.group(4) else None
    else:
        result["wind_dir"] = 0
        result["wind_speed"] = 0
        result["wind_gust"] = None

    # Visibility — e.g. 10SM or 6SM
    vis_match = re.search(r"(\d+)SM", raw)
    result["visibility_sm"] = int(vis_match.group(1)) if vis_match else 10

    # Sky condition — FEW/SCT/BKN/OVC + altitude (hundreds of feet)
    sky_pattern = re.compile(r"(FEW|SCT|BKN|OVC)(\d{3})")
    layers = [(m.group(1), int(m.group(2)) * 100) for m in sky_pattern.finditer(raw)]
    result["sky_layers"] = layers

    # Ceiling = lowest BKN or OVC
    ceiling = None
    for cover, alt in layers:
        if cover in ("BKN", "OVC"):
            ceiling = alt if ceiling is None else min(ceiling, alt)
            break
    result["ceiling_ft"] = ceiling

    # Temperature / dewpoint — e.g. 22/12 or M02/M05
    temp_match = re.search(r"\s(M?\d{2})/(M?\d{2})\s", raw)
    if temp_match:
        t_str, d_str = temp_match.group(1), temp_match.group(2)
        result["temperature"] = -int(t_str[1:]) if t_str.startswith("M") else int(t_str)
        result["dewpoint"] = -int(d_str[1:]) if d_str.startswith("M") else int(d_str)
    else:
        result["temperature"] = None
        result["dewpoint"] = None

    # Altimeter — e.g. A3012
    alt_match = re.search(r"A(\d{4})", raw)
    result["altimeter"] = int(alt_match.group(1)) / 100.0 if alt_match else 29.92

    # Flight category
    result["flight_category"] = determine_flight_category(
        result["visibility_sm"], result["ceiling_ft"]
    )

    return result


def determine_flight_category(
    visibility_sm: int | float | None,
    ceiling_ft: int | None,
) -> str:
    """Determine flight category per FAA criteria.

    Returns:
        One of "VFR", "MVFR", "IFR", "LIFR".
    """
    vis = visibility_sm if visibility_sm is not None else 10
    ceil = ceiling_ft  # None means clear (unlimited ceiling)

    # LIFR: vis < 1 SM  OR  ceiling < 500 ft
    if vis < 1 or (ceil is not None and ceil < 500):
        return "LIFR"
    # IFR: vis 1–3 SM  OR  ceiling 500–999 ft
    if vis < 3 or (ceil is not None and ceil < 1000):
        return "IFR"
    # MVFR: vis 3–5 SM  OR  ceiling 1000–3000 ft
    if vis <= 5 or (ceil is not None and ceil <= 3000):
        return "MVFR"
    # VFR
    return "VFR"
