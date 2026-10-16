"""External service interfaces.

Provides clean abstraction boundaries for external data sources that
currently use mock/stub data.  Each service class can be swapped out
for a real API integration (AVWX, FAA NASR, Google Vision, etc.) by
implementing the same async interface.

Modules
-------
weather_service
    METAR/TAF retrieval and flight-category determination.
weather_providers
    Raw METAR/TAF transports behind the ``WeatherProvider`` seam.
airspace_service
    Airspace class lookup at a point or along a route.
ocr_service
    Text and structured-data extraction from flight plan images.
"""
