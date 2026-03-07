# Skill: Aviation Domain Knowledge

Use this skill to write accurate aviation content, ATC scenarios, and ICAO-compliant phraseology in Horus.

## ICAO Standard Phraseology

ICAO phraseology is the globally standardized language for aviation radio communications. Always use standard phrases — not colloquial language.

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
| **Correction** | Error in previous transmission, correct version follows |

### Numbers Pronunciation

- Numbers spoken digit by digit for headings, frequencies, altitudes
- Except: flight levels, altitudes above 10,000 ft use groupings
  - "FL350" = "flight level three five zero"
  - "10,000 ft" = "one zero thousand feet"
- Decimal point in frequencies = "decimal" or "point"
  - 118.3 = "one one eight decimal three"

### Standard ATC Transmissions

#### Ground / Pushback
```
ATC: "[Callsign], pushback approved, face [direction], altimeter [QNH]."
ATC: "[Callsign], taxi to runway [XX] via [taxiways], hold short of runway [YY]."
ATC: "[Callsign], runway [XX], line up and wait."
```

#### Departure
```
ATC: "[Callsign], runway [XX], cleared for takeoff, wind [direction] at [speed]."
ATC: "[Callsign], contact departure on [frequency], good day."
ATC: "[Callsign], turn left/right heading [XXX], climb and maintain [altitude]."
```

#### Enroute
```
ATC: "[Callsign], climb/descend and maintain flight level [XXX]."
ATC: "[Callsign], direct [waypoint], resume own navigation."
ATC: "[Callsign], traffic [o'clock position], [distance] miles, [altitude], [aircraft type]."
ATC: "[Callsign], contact [facility name] on [frequency], good day."
```

#### Approach
```
ATC: "[Callsign], expect ILS approach runway [XX]."
ATC: "[Callsign], descend via the [STAR name] arrival, cross [fix] at [altitude]."
ATC: "[Callsign], cleared ILS runway [XX] approach."
ATC: "[Callsign], reduce speed to [knots]."
```

#### Landing
```
ATC: "[Callsign], runway [XX], cleared to land, wind [direction] at [speed]."
ATC: "[Callsign], exit runway at [taxiway], contact ground on [frequency]."
ATC: "[Callsign], go around, climb runway heading, maintain [altitude]."
```

### Pilot Readback Requirements

Pilots must **read back** (repeat) critical instructions:
- Runway-in-use
- Takeoff/landing clearances
- Altitude/flight level assignments
- Heading assignments
- Frequency changes
- Transponder codes (squawk)

## Scenario Structure

Each training scenario in Horus has:

```python
{
  "name": str,              # Human-readable name
  "description": str,       # What the student will practice
  "difficulty": int,        # 1 (beginner) to 5 (expert)
  "airport_icao": str,      # 4-letter ICAO code, e.g. "KJFK", "LEMD", "EGLL"
  "runway": str,            # Runway designation, e.g. "31L", "09"
  "weather_preset": str,    # "VFR", "MVFR", "IFR", "LIFR"
  "phase": str,             # "ground", "departure", "enroute", "approach", "landing"
}
```

### Difficulty Levels

| Level | Description |
|-------|-------------|
| 1 | Beginner: single clearances, standard weather, no traffic |
| 2 | Elementary: multi-step taxi routes, light traffic |
| 3 | Intermediate: holds, weather, handoffs |
| 4 | Advanced: emergencies, complex airspace |
| 5 | Expert: simultaneous events, degraded comms |

### Major Airport ICAO Codes

| ICAO | Airport | Notes |
|------|---------|-------|
| KJFK | New York JFK | Complex, heavy traffic |
| KLAX | Los Angeles | Complex intersecting runways |
| KORD | Chicago O'Hare | Parallel operations |
| EGLL | London Heathrow | European procedures |
| LEMD | Madrid Barajas | Spanish language option |
| YSSY | Sydney | Southern hemisphere |
| ZBAA | Beijing Capital | Asian operations |

## Weather Categories (USA)

| Category | Ceiling | Visibility |
|----------|---------|------------|
| VFR | >3,000 ft AGL | >5 SM |
| MVFR | 1,000–3,000 ft | 3–5 SM |
| IFR | 500–999 ft | 1–3 SM |
| LIFR | <500 ft | <1 SM |

## System Prompts for ATC Agent

When modifying `app/services/llm/prompts.py`, the system prompt must:
1. Establish the AI as a specific ATC position (Ground, Tower, Approach, Departure, Center)
2. Specify airport ICAO and current weather
3. Enforce ICAO phraseology
4. Limit response length (radio calls are concise)
5. Not explain aviation concepts — respond only as ATC would

### Example System Prompt Structure

```
You are an Air Traffic Controller at [Airport ICAO Name] ([ICAO code]).
You are working the [position] frequency [frequency].
Current weather: [METAR or description].
Active runway: [runway].

Respond ONLY using standard ICAO ATC phraseology. Be concise. 
Address the pilot by their callsign. Do not explain — just issue instructions.
```

## Common Mistakes to Avoid

- ❌ "Yes, you can land" → ✅ "[Callsign], runway 27, cleared to land"
- ❌ "Go to 10,000 feet" → ✅ "[Callsign], climb and maintain one zero thousand"
- ❌ "Turn right" → ✅ "[Callsign], turn right heading two seven zero"
- ❌ Pilot says "OK" → ✅ Pilot says "Roger" or reads back clearance
- ❌ Using informal language or explanations in ATC responses
