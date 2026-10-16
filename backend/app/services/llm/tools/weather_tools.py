"""Weather report fixtures and METAR/TAF parsing.

The fetch helpers return realistic but static mock data for major US airports.
They back ``MockWeatherProvider`` (and therefore the default non-production
path). Live reports come from the configured ``WeatherProvider``; every
provider's text is parsed here.
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


# ── TAF parsing ───────────────────────────────────────────────────────

#: Change indicators that open a new forecast period in a TAF.
_TAF_PERIOD_RE = re.compile(r"^(FM\d{6}|BECMG|TEMPO|PROB\d{2}|INTER)$")
_TAF_WIND_RE = re.compile(r"(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?(?:KT|MPS)")
_TAF_FULL_VIS_RE = re.compile(r"^(P|M)?(\d+)SM$")
_TAF_FRACTION_VIS_RE = re.compile(r"^(P|M)?(\d+)/(\d+)SM$")
_TAF_SKY_RE = re.compile(r"^(FEW|SCT|BKN|OVC)(\d{3})")
_TAF_VV_RE = re.compile(r"^VV(\d{3})")
_TAF_TIME_RANGE_RE = re.compile(r"^\d{4}/\d{4}$")
_TAF_ISSUED_RE = re.compile(r"^\d{6}Z$")
_TAF_VALID_RE = re.compile(r"^\d{4}/\d{4}$")


def _parse_taf_wind(text: str) -> dict[str, Any]:
    """Extract wind from one forecast period."""
    match = _TAF_WIND_RE.search(text)
    if not match:
        return {"wind_dir": 0, "wind_speed": 0, "wind_gust": None}
    direction = match.group(1)
    return {
        "wind_dir": int(direction) if direction != "VRB" else 0,
        "wind_speed": int(match.group(2)),
        "wind_gust": int(match.group(3)) if match.group(3) else None,
    }


def _parse_taf_visibility(tokens: list[str]) -> float | None:
    """Extract prevailing visibility in statute miles.

    Handles ``10SM``, ``P6SM`` (greater than six), ``M1/4SM`` (less than), and
    the split ``1 1/2SM`` form where the whole number is its own token.
    """
    for index, token in enumerate(tokens):
        fraction = _TAF_FRACTION_VIS_RE.match(token)
        if fraction:
            value = int(fraction.group(2)) / int(fraction.group(3))
            if index > 0 and tokens[index - 1].isdigit():
                value += int(tokens[index - 1])
            return value
        full = _TAF_FULL_VIS_RE.match(token)
        if full:
            return float(full.group(2))
    return None


def _parse_taf_sky(tokens: list[str]) -> list[tuple[str, int]]:
    """Extract sky layers, including vertical visibility (``VV``)."""
    layers: list[tuple[str, int]] = []
    for token in tokens:
        layer = _TAF_SKY_RE.match(token)
        if layer:
            layers.append((layer.group(1), int(layer.group(2)) * 100))
            continue
        obscured = _TAF_VV_RE.match(token)
        if obscured:
            layers.append(("VV", int(obscured.group(1)) * 100))
    return layers


def _ceiling_from_layers(layers: list[tuple[str, int]]) -> int | None:
    """Return the lowest ceiling layer (broken/overcast/obscured)."""
    ceilings = [alt for cover, alt in layers if cover in ("BKN", "OVC", "VV")]
    return min(ceilings) if ceilings else None


def _parse_taf_period(tokens: list[str]) -> dict[str, Any]:
    """Parse the wind/visibility/sky common to every forecast period."""
    layers = _parse_taf_sky(tokens)
    visibility = _parse_taf_visibility(tokens)
    ceiling = _ceiling_from_layers(layers)
    return {
        **_parse_taf_wind(" ".join(tokens)),
        "visibility_sm": visibility,
        "sky_layers": layers,
        "ceiling_ft": ceiling,
        "flight_category": determine_flight_category(visibility, ceiling),
    }


def _classify_taf_period(tokens: list[str]) -> tuple[str, str | None, str | None, list[str]]:
    """Split one period's tokens into (type, from, to, body)."""
    if not tokens:
        return "INITIAL", None, None, []

    head = tokens[0]
    if head.startswith("FM"):
        return "FM", head[2:], None, tokens[1:]
    if head in ("BECMG", "TEMPO", "INTER") or head.startswith("PROB"):
        body = tokens[1:]
        start: str | None = None
        end: str | None = None
        if body and _TAF_TIME_RANGE_RE.match(body[0]):
            start, end = body[0].split("/")
            body = body[1:]
        return head, start, end, body
    return "INITIAL", None, None, tokens


def parse_taf(raw: str) -> dict[str, Any]:
    """Parse a raw TAF into its forecast periods.

    Every period carries the same fields a METAR parse produces for
    wind/visibility/sky/ceiling/category, plus its own ``type`` — ``INITIAL``,
    ``FM``, ``BECMG``, ``TEMPO``, ``PROB30``/``PROB40``, or ``INTER`` — and the
    ``from``/``to`` clock values where the period declares them. ``FM`` periods
    use the six-digit ``DDHHMM`` form; change groups use ``DDHH``.

    Returns:
        Dict with ``raw``, ``station``, ``issued``, ``valid``, and ``periods``.
        An unparseable or empty input returns empty ``periods``.
    """
    result: dict[str, Any] = {
        "raw": raw,
        "station": "",
        "issued": None,
        "valid": None,
        "periods": [],
    }
    tokens = raw.split()
    if not tokens:
        return result

    if tokens[0] == "TAF":
        tokens = tokens[1:]
    while tokens and tokens[0] in ("AMD", "COR", "RTD"):
        tokens = tokens[1:]
    if tokens and re.fullmatch(r"[A-Z]{4}", tokens[0]):
        result["station"] = tokens[0]
        tokens = tokens[1:]
    if tokens and _TAF_ISSUED_RE.match(tokens[0]):
        result["issued"] = tokens[0]
        tokens = tokens[1:]
    if tokens and _TAF_VALID_RE.match(tokens[0]):
        result["valid"] = tokens[0]
        tokens = tokens[1:]

    groups: list[list[str]] = [[]]
    for token in tokens:
        if _TAF_PERIOD_RE.match(token):
            groups.append([token])
        else:
            groups[-1].append(token)

    for group in groups:
        if not group:
            continue
        period_type, from_time, to_time, body = _classify_taf_period(group)
        result["periods"].append(
            {
                "type": period_type,
                "from": from_time,
                "to": to_time,
                "raw": " ".join(group),
                **_parse_taf_period(body),
            }
        )

    return result
