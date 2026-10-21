from __future__ import annotations

from typing import Any

from app.services.location_service import search_active_branches


class LocationAgent:
    """Finds active retail branches and their published location details."""

    agent_key = "location_agent"

    def search(
        self,
        *,
        city: str | None = None,
        area: str | None = None,
        branch_name: str | None = None,
        variant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return search_active_branches(
            city=city,
            area=area,
            branch_name=branch_name,
            variant_id=variant_id,
        )


location_agent = LocationAgent()
