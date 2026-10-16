"""Deterministic organization identifier helpers.

Organization UUIDs are derived from their slug (``uuid5(NAMESPACE_DNS,
"<slug>.aero")``) so the same value can be computed by the database seeder,
the Keycloak realm import, and the JWT claim parser without a database
round-trip.  This keeps the ``organization_id`` claim and ``users.id`` style
identifiers consistent across the stack (see issue #18).
"""

from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)

ORG_ID_DOMAIN = "aero"


def org_id_for_slug(slug: str) -> uuid.UUID:
    """Return the deterministic organization UUID for *slug*.

    Args:
        slug: The organization slug (e.g. ``"skybridge"``).

    Returns:
        The stable ``uuid5`` for ``"<slug>.aero"``.
    """
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"{slug}.{ORG_ID_DOMAIN}")


def parse_org_id_claim(value: str | None) -> uuid.UUID | None:
    """Parse the ``organization_id`` JWT claim into a UUID.

    The claim should carry a UUID string (current Keycloak mapping).  Legacy
    or stale tokens may instead carry the bare organization slug, which is
    resolved to its deterministic UUID rather than raising ``uuid_parsing``.

    Args:
        value: The raw claim value, or ``None``/empty if absent.

    Returns:
        The organization UUID, or ``None`` when the claim is absent.
    """
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        logger.warning("organization_id claim %r is not a UUID; resolving it as a slug", value)
        return org_id_for_slug(value)
