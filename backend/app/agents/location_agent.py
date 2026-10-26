from __future__ import annotations

from typing import Any

from app.services.location_service import (
    search_branches,
)


class LocationAgent:
    """Read-only branch/location specialist."""

    agent_key = "location_agent"

    def search(
        self,
        *,
        branch_name: str | None = None,
        city: str | None = None,
        area: str | None = None,
        variant_id: str | None = None,
        customer_latitude: float | None = None,
        customer_longitude: float | None = None,
    ) -> list[dict[str, Any]]:
        return search_branches(
            branch_name=branch_name,
            city=city,
            area=area,
            variant_id=variant_id,
            customer_latitude=(
                customer_latitude
            ),
            customer_longitude=(
                customer_longitude
            ),
        )


location_agent = LocationAgent()
