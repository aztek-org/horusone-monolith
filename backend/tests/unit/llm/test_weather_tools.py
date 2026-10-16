"""Unit tests for weather fetch helpers and METAR/TAF parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.llm.tools.weather_tools import (
    DEFAULT_METAR,
    MOCK_METARS,
    determine_flight_category,
    fetch_metar,
    fetch_taf,
    parse_metar,
    parse_taf,
)

FIXTURES = Path(__file__).parents[2] / "fixtures" / "weather"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text().strip()


class TestFetch:
    def test_known_metar_is_returned_verbatim(self) -> None:
        assert fetch_metar("KJFK") == MOCK_METARS["KJFK"]

    def test_lookup_is_case_and_whitespace_insensitive(self) -> None:
        assert fetch_metar("  kjfk ") == MOCK_METARS["KJFK"]

    def test_unknown_metar_uses_the_default_template(self) -> None:
        result = fetch_metar("ZZZZ")

        assert result == DEFAULT_METAR.format(icao="ZZZZ")
        assert "ZZZZ" in result
        assert "CLR" in result

    def test_known_taf_is_returned(self) -> None:
        assert "TAF KJFK" in fetch_taf("KJFK")

    def test_unknown_taf_uses_the_default_template(self) -> None:
        result = fetch_taf("ZZZZ")

        assert result.startswith("TAF ZZZZ")
        assert "SKC" in result


class TestParseMetar:
    def test_full_parse_of_a_vfr_metar(self) -> None:
        result = parse_metar(
            "KJFK 151856Z 28012G18KT 10SM FEW040 SCT250 22/12 A3012 "
            "RMK AO2 SLP203 T02220117"
        )

        assert result["station"] == "KJFK"
        assert result["wind_dir"] == 280
        assert result["wind_speed"] == 12
        assert result["wind_gust"] == 18
        assert result["visibility_sm"] == 10
        assert result["sky_layers"] == [("FEW", 4000), ("SCT", 25000)]
        assert result["ceiling_ft"] is None
        assert result["temperature"] == 22
        assert result["dewpoint"] == 12
        assert result["altimeter"] == pytest.approx(30.12)
        assert result["flight_category"] == "VFR"

    def test_ceiling_is_the_first_broken_or_overcast_layer(self) -> None:
        result = parse_metar(
            "KORD 151851Z 31015G22KT 6SM -RA BR SCT015 BKN025 OVC040 18/16 A2978"
        )

        assert result["ceiling_ft"] == 2500
        assert result["visibility_sm"] == 6
        assert result["wind_gust"] == 22
        assert result["flight_category"] == "MVFR"

    def test_variable_wind_direction_is_zero(self) -> None:
        result = parse_metar("KXYZ 151856Z VRB04KT 10SM CLR 20/10 A3000")

        assert result["wind_dir"] == 0
        assert result["wind_speed"] == 4
        assert result["wind_gust"] is None

    def test_negative_temperatures_are_parsed(self) -> None:
        result = parse_metar("KMSP 151853Z 00000KT 10SM CLR M02/M05 A3012")

        assert result["temperature"] == -2
        assert result["dewpoint"] == -5

    def test_missing_optional_fields_are_defaulted(self) -> None:
        result = parse_metar("KLAX 151853Z")

        assert result["wind_dir"] == 0
        assert result["wind_speed"] == 0
        assert result["visibility_sm"] == 10
        assert result["sky_layers"] == []
        assert result["temperature"] is None
        assert result["dewpoint"] is None
        assert result["altimeter"] == pytest.approx(29.92)

    def test_empty_metar_returns_only_the_raw_string(self) -> None:
        assert parse_metar("") == {"raw": ""}

    def test_raw_string_is_always_preserved(self) -> None:
        raw = "KJFK 151856Z 28012KT 10SM CLR 22/12 A3012"
        assert parse_metar(raw)["raw"] == raw


@pytest.mark.parametrize(
    ("visibility_sm", "ceiling_ft", "expected"),
    [
        # Visibility-driven categories.
        (0.5, None, "LIFR"),
        (1, None, "IFR"),
        (2, None, "IFR"),
        (3, None, "MVFR"),
        (5, None, "MVFR"),
        (6, None, "VFR"),
        # Ceiling-driven categories.
        (10, 400, "LIFR"),
        (10, 500, "IFR"),
        (10, 999, "IFR"),
        (10, 1000, "MVFR"),
        (10, 3000, "MVFR"),
        (10, 3001, "VFR"),
        # Unlimited ceiling.
        (10, None, "VFR"),
        (None, None, "VFR"),
    ],
)
def test_determine_flight_category_boundaries(
    visibility_sm: float | None,
    ceiling_ft: int | None,
    expected: str,
) -> None:
    assert determine_flight_category(visibility_sm, ceiling_ft) == expected


class TestParseTaf:
    """Full TAF parsing, pinned against AWC-shaped raw-text fixtures."""

    def test_kjfk_periods_are_split_on_fm(self) -> None:
        taf = parse_taf(_fixture("kjfk_taf.txt"))

        assert taf["station"] == "KJFK"
        assert taf["issued"] == "151730Z"
        assert taf["valid"] == "1518/1624"
        assert [period["type"] for period in taf["periods"]] == ["INITIAL", "FM", "FM"]

        initial, second, third = taf["periods"]
        assert initial["from"] is None
        assert initial["wind_dir"] == 280
        assert initial["wind_speed"] == 12
        assert initial["wind_gust"] == 18
        assert initial["visibility_sm"] == 6.0  # P6SM -> greater than six
        assert initial["sky_layers"] == [("FEW", 4000), ("SCT", 25000)]
        assert initial["ceiling_ft"] is None
        assert initial["flight_category"] == "VFR"

        assert second["from"] == "152200"
        assert second["wind_speed"] == 10
        assert second["sky_layers"] == [("SCT", 4000)]
        assert third["from"] == "160400"
        assert third["wind_dir"] == 330

    def test_ksea_change_groups_carry_time_ranges(self) -> None:
        taf = parse_taf(_fixture("ksea_taf_changes.txt"))

        assert [period["type"] for period in taf["periods"]] == [
            "INITIAL",
            "TEMPO",
            "PROB30",
            "FM",
        ]

        _, tempo, prob, forecast = taf["periods"]
        assert (tempo["from"], tempo["to"]) == ("1518", "1522")
        assert tempo["visibility_sm"] == 3.0
        assert tempo["flight_category"] == "MVFR"

        assert (prob["from"], prob["to"]) == ("1602", "1608")
        assert prob["visibility_sm"] == 0.5
        assert prob["sky_layers"] == [("VV", 200)]
        assert prob["ceiling_ft"] == 200
        assert prob["flight_category"] == "LIFR"

        assert forecast["from"] == "161000"

    def test_tempo_uses_the_most_restrictive_of_visibility_and_ceiling(self) -> None:
        taf = parse_taf(_fixture("kord_taf_tempo.txt"))

        tempo = taf["periods"][1]
        assert tempo["type"] == "TEMPO"
        assert tempo["visibility_sm"] == 2.0
        assert tempo["ceiling_ft"] == 1200
        # Two statute miles is IFR even though the 1200 ft ceiling is MVFR.
        assert tempo["flight_category"] == "IFR"

    def test_empty_input_yields_no_periods(self) -> None:
        parsed = parse_taf("")

        assert parsed["periods"] == []
        assert parsed["station"] == ""
        assert parsed["raw"] == ""

    def test_omitted_optional_fields_are_defaulted(self) -> None:
        taf = parse_taf("TAF ZZZZ 151730Z 1518/1624 00000KT SKC")

        assert taf["station"] == "ZZZZ"
        assert len(taf["periods"]) == 1
        assert taf["periods"][0]["visibility_sm"] is None
        assert taf["periods"][0]["wind_speed"] == 0

    @pytest.mark.parametrize(
        ("visibility", "expected"),
        [
            ("P6SM", 6.0),
            ("10SM", 10.0),
            ("3SM", 3.0),
            ("1/2SM", 0.5),
            ("M1/4SM", 0.25),
            ("1 1/2SM", 1.5),
        ],
    )
    def test_visibility_forms(self, visibility: str, expected: float) -> None:
        taf = parse_taf(f"TAF ZZZZ 151730Z 1518/1624 00000KT {visibility} SKC")

        assert taf["periods"][0]["visibility_sm"] == pytest.approx(expected)
