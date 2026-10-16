"""Provider-aware reachability probing for language-model endpoints.

Each adapter knows its own protocol, so it names the endpoint it can ask; this
module holds the one classification they share.  A provider that answers at all
is reachable, a provider that answers wrongly is ``degraded``, and one that
cannot be reached is ``unreachable`` — so a healthy Groq or NVIDIA NIM
deployment is not reported as down because Ollama's route is missing.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

# Readiness must answer quickly; inference timeouts are far too long for it.
HEALTH_PROBE_TIMEOUT_SECONDS = 3.0


async def probe_endpoint(
    url: str,
    *,
    headers: dict[str, str] | None = None,
) -> str:
    """Classify one provider endpoint as reachable, degraded, or unreachable.

    Args:
        url: The provider's own health endpoint.
        headers: Provider authentication, when it requires any.

    Returns:
        ``"ok"`` for a 2xx response, ``"degraded"`` for any other response, and
        ``"unreachable"`` when the endpoint could not be contacted.
    """
    try:
        async with httpx.AsyncClient(timeout=HEALTH_PROBE_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=headers)
    except Exception:
        logger.warning("LLM health probe could not reach %s", url, exc_info=True)
        return "unreachable"
    if response.is_success:
        return "ok"
    logger.warning("LLM health probe to %s returned %s", url, response.status_code)
    return "degraded"
