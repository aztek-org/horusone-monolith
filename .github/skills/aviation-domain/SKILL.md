---
name: Aviation Domain Knowledge
description: >
  ATC vocabulary, ICAO standard phraseology, scenario structure, weather categories,
  and communication patterns for writing accurate aviation content in Horus.
---

# Aviation Domain Knowledge

Use this skill to write accurate aviation content, ATC scenarios, and ICAO-compliant phraseology.

## ICAO Standard Phraseology

### Core Vocabulary

| Term | Meaning |
|------|---------|
| **Roger** | Message received and understood |
| **Wilco** | Will comply (implies Roger) |
| **Affirmative** | Yes |
| **Negative** | No |
| **Say again** | Repeat your last transmission |
| **Stand by** | Wait |
| **Go ahead** | Proceed with your message |
| **Break** | Separating messages to different aircraft |
| **Correction** | Error in previous transmission |

### Numbers Pronunciation

- Numbers spoken digit by digit for headings, frequencies, altitudes
- Decimal point in frequencies = "decimal": 118.3 = "one one eight decimal three"
- Flight levels: FL350 = "flight level three five zero"

### Standard ATC Transmissions

#### Ground / Pushback
```
ATC: "[Callsign], pushback approved, face [direction], altimeter [QNH]."
ATC: "[Callsign], taxi to runway [XX] via [taxiways], hold short of runway [YY]."
```

#### Departure
```
ATC: "[Callsign], runway [XX], cleared for takeoff, wind [direction] at [speed]."
ATC: "[Callsign], contact departure on [frequency], good day."
```

#### Enroute
```
ATC: "[Callsign], climb/descend and maintain flight level [XXX]."
ATC: "[Callsign], traffic [o'clock position], [distance] miles, [altitude], [type]."
```

#### Approach & Landing
```
ATC: "[Callsign], cleared ILS runway [XX] approach."
ATC: "[Callsign], runway [XX], cleared to land, wind [direction] at [speed]."
ATC: "[Callsign], go around, climb runway heading, maintain [altitude]."
```

### Pilot Readback Requirements

Pilots must read back: runway-in-use, takeoff/landing clearances, altitude assignments, heading assignments, frequency changes, and squawk codes.

## Scenario Structure

```python
{
  "name": str,              # Human-readable name
  "description": str,       # What the student will practice
  "difficulty": int,        # 1 (beginner) to 5 (expert)
  "airport_icao": str,      # 4-letter ICAO code
  "runway": str,            # e.g. "31L", "09"
  "weather_preset": str,    # "VFR", "MVFR", "IFR", "LIFR"
  "phase": str,             # "ground", "departure", "enroute", "approach", "landing"
}
```

### Difficulty Levels

| Level | Description |
|-------|-------------|
| 1 | Beginner: single clearances, standard weather, no traffic |
| 2 | Elementary: multi-step taxi, light traffic |
| 3 | Intermediate: holds, weather, handoffs |
| 4 | Advanced: emergencies, complex airspace |
| 5 | Expert: simultaneous events, degraded comms |

### Weather Categories (USA)

| Category | Ceiling | Visibility |
|----------|---------|------------|
| VFR | >3,000 ft AGL | >5 SM |
| MVFR | 1,000–3,000 ft | 3–5 SM |
| IFR | 500–999 ft | 1–3 SM |
| LIFR | <500 ft | <1 SM |

## Common Mistakes to Avoid

- ❌ "Yes, you can land" → ✅ "[Callsign], runway 27, cleared to land"
- ❌ "Go to 10,000 feet" → ✅ "[Callsign], climb and maintain one zero thousand"
- ❌ "Turn right" → ✅ "[Callsign], turn right heading two seven zero"
- ❌ Using informal language in ATC responses
