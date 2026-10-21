from __future__ import annotations

from typing import Any

from app.core.supabase_client import supabase_admin
from app.services.inventory_service import get_inventory_snapshot_enriched


BRANCH_FIELDS = (
    "id, name, city, area, address, latitude, longitude, "
    "phone, opening_time, closing_time, is_active"
)


def search_active_branches(
    *,
    city: str | None = None,
    area: str | None = None,
    branch_name: str | None = None,
    variant_id: str | None = None,
) -> list[dict[str, Any]]:
    """Search active branches and optionally require verified stock."""

    response = (
        supabase_admin.table("branches")
        .select(BRANCH_FIELDS)
        .eq("is_active", True)
        .execute()
    )

    branches = response.data or []

    def matches(value: Any, requested: str | None) -> bool:
        return (
            not requested
            or requested.strip().casefold() in str(value or "").casefold()
        )

    branches = [
        branch
        for branch in branches
        if matches(branch.get("city"), city)
        and matches(branch.get("area"), area)
        and matches(branch.get("name"), branch_name)
    ]

    if variant_id:
        inventory = get_inventory_snapshot_enriched(variant_id)
        in_stock_branch_ids = {
            str(row.get("branch_id"))
            for row in inventory
            if int(row.get("available_quantity") or 0) > 0
        }
        branches = [
            branch
            for branch in branches
            if str(branch.get("id")) in in_stock_branch_ids
        ]

    return [
        {
            "branch_id": str(branch["id"]),
            "name": branch["name"],
            "city": branch["city"],
            "area": branch.get("area"),
            "address": branch.get("address"),
            "latitude": (
                float(branch["latitude"])
                if branch.get("latitude") is not None
                else None
            ),
            "longitude": (
                float(branch["longitude"])
                if branch.get("longitude") is not None
                else None
            ),
            "phone": branch.get("phone"),
            "opening_time": (
                str(branch["opening_time"])
                if branch.get("opening_time") is not None
                else None
            ),
            "closing_time": (
                str(branch["closing_time"])
                if branch.get("closing_time") is not None
                else None
            ),
        }
        for branch in branches
    ]
