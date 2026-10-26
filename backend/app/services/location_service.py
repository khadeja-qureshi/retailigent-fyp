from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any

from app.core.supabase_client import supabase_admin


def _as_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _haversine_km(
    latitude_1: float,
    longitude_1: float,
    latitude_2: float,
    longitude_2: float,
) -> float:
    """Return great-circle distance between two coordinates in kilometres."""

    earth_radius_km = 6371.0088

    lat1 = radians(latitude_1)
    lon1 = radians(longitude_1)
    lat2 = radians(latitude_2)
    lon2 = radians(longitude_2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        sin(dlat / 2.0) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(dlon / 2.0) ** 2
    )

    return 2.0 * earth_radius_km * asin(
        sqrt(a)
    )


def _matches_location(
    branch: dict[str, Any],
    location_filter: str | None,
) -> bool:
    if not location_filter:
        return True

    wanted = location_filter.strip().casefold()

    if not wanted:
        return True

    searchable_values = (
        branch.get("name"),
        branch.get("city"),
        branch.get("area"),
        branch.get("address"),
    )

    return any(
        wanted
        in str(value or "").casefold()
        for value in searchable_values
    )


def search_branches(
    *,
    branch_name: str | None = None,
    city: str | None = None,
    area: str | None = None,
    variant_id: str | None = None,
    customer_latitude: float | None = None,
    customer_longitude: float | None = None,
) -> list[dict[str, Any]]:
    """
    Search active retail branches.

    `branch_name` is intentionally treated as a general location text filter
    so existing chat schemas can support a branch name, city, or area without
    a database/schema migration.

    When `variant_id` is provided, only branches with positive live stock for
    that variant are returned.

    When customer coordinates are provided, every row receives `distance_km`
    and results are ordered nearest-first.
    """

    response = (
        supabase_admin
        .table("branches")
        .select(
            "id, name, city, area, address, "
            "latitude, longitude, phone, "
            "opening_time, closing_time, is_active"
        )
        .eq("is_active", True)
        .execute()
    )

    branches = list(
        response.data
        or []
    )

    location_filter = (
        branch_name
        or area
        or city
    )

    branches = [
        row
        for row in branches
        if _matches_location(
            row,
            location_filter,
        )
    ]

    available_by_branch: dict[str, int] = {}

    if variant_id:
        inventory_response = (
            supabase_admin
            .table("branch_inventory")
            .select(
                "branch_id, available_quantity"
            )
            .eq(
                "variant_id",
                variant_id,
            )
            .gt(
                "available_quantity",
                0,
            )
            .execute()
        )

        for inventory_row in (
            inventory_response.data
            or []
        ):
            branch_id = str(
                inventory_row.get("branch_id")
                or ""
            )

            if not branch_id:
                continue

            available_by_branch[branch_id] = int(
                inventory_row.get(
                    "available_quantity"
                )
                or 0
            )

        branches = [
            row
            for row in branches
            if str(row.get("id") or "")
            in available_by_branch
        ]

    has_customer_location = (
        customer_latitude is not None
        and customer_longitude is not None
    )

    results: list[dict[str, Any]] = []

    for branch in branches:
        branch_id = str(
            branch.get("id")
            or ""
        )

        latitude = _as_float(
            branch.get("latitude")
        )
        longitude = _as_float(
            branch.get("longitude")
        )

        distance_km: float | None = None

        if (
            has_customer_location
            and latitude is not None
            and longitude is not None
        ):
            distance_km = round(
                _haversine_km(
                    float(customer_latitude),
                    float(customer_longitude),
                    latitude,
                    longitude,
                ),
                2,
            )

        results.append(
            {
                "branch_id": branch_id,
                "branch_name": branch.get("name"),
                "name": branch.get("name"),
                "city": branch.get("city"),
                "area": branch.get("area"),
                "address": branch.get("address"),
                "latitude": latitude,
                "longitude": longitude,
                "phone": branch.get("phone"),
                "opening_time": branch.get("opening_time"),
                "closing_time": branch.get("closing_time"),
                "available_quantity": (
                    available_by_branch.get(
                        branch_id
                    )
                    if variant_id
                    else None
                ),
                "distance_km": distance_km,
            }
        )

    if has_customer_location:
        results.sort(
            key=lambda row: (
                row.get("distance_km") is None,
                row.get("distance_km")
                if row.get("distance_km")
                is not None
                else float("inf"),
                str(row.get("branch_name") or ""),
            )
        )
    else:
        results.sort(
            key=lambda row: (
                str(row.get("city") or ""),
                str(row.get("branch_name") or ""),
            )
        )

    return results
