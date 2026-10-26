from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any

from app.core.supabase_client import supabase_admin
from app.services.inventory_service import (
    get_inventory_snapshot_enriched,
)


def _as_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def _haversine_km(
    latitude_1: float,
    longitude_1: float,
    latitude_2: float,
    longitude_2: float,
) -> float:
    """
    Return great-circle distance between
    two coordinates in kilometres.
    """

    earth_radius_km = 6371.0088

    lat1 = radians(
        latitude_1
    )

    lon1 = radians(
        longitude_1
    )

    lat2 = radians(
        latitude_2
    )

    lon2 = radians(
        longitude_2
    )

    dlat = (
        lat2
        -
        lat1
    )

    dlon = (
        lon2
        -
        lon1
    )

    a = (
        sin(
            dlat / 2.0
        )
        ** 2
        +
        cos(
            lat1
        )
        *
        cos(
            lat2
        )
        *
        sin(
            dlon / 2.0
        )
        ** 2
    )

    return (
        2.0
        *
        earth_radius_km
        *
        asin(
            sqrt(
                a
            )
        )
    )


def _contains_text(
    value: Any,
    wanted: str | None,
) -> bool:
    if not wanted:
        return True

    wanted_normalized = (
        wanted
        .strip()
        .casefold()
    )

    if not wanted_normalized:
        return True

    return (
        wanted_normalized
        in
        str(
            value
            or ""
        )
        .strip()
        .casefold()
    )


def _matches_branch_name_or_location(
    branch: dict[
        str,
        Any,
    ],
    branch_name: str | None,
) -> bool:
    """
    The chat schema historically exposed
    only branch_name for location questions.

    For backward compatibility, this acts
    as a general branch/location text filter
    and may match:
    - branch name
    - city
    - area
    - address
    """

    if not branch_name:
        return True

    return any(
        _contains_text(
            branch.get(
                field
            ),
            branch_name,
        )
        for field in (
            "name",
            "city",
            "area",
            "address",
        )
    )


def search_active_branches(
    *,
    branch_name: str | None = None,
    city: str | None = None,
    area: str | None = None,
    variant_id: str | None = None,
    customer_latitude: (
        float | None
    ) = None,
    customer_longitude: (
        float | None
    ) = None,
) -> list[
    dict[
        str,
        Any,
    ]
]:
    """
    Return active retail branches matching
    optional location and stock filters.

    Compatibility guarantees:
    - keeps the original public function
      search_active_branches()
    - supports city and area filters
    - uses authoritative enriched inventory
      when variant_id is supplied
    - calculates nearest-store distance
    - returns the stable BranchMap payload
    """

    response = (
        supabase_admin
        .table(
            "branches"
        )
        .select(
            "id, name, city, area, address, "
            "latitude, longitude, phone, "
            "opening_time, closing_time"
        )
        .eq(
            "is_active",
            True,
        )
        .execute()
    )

    branches = list(
        response.data
        or []
    )

    filtered_branches: list[
        dict[
            str,
            Any,
        ]
    ] = []

    for branch in branches:

        if not (
            _matches_branch_name_or_location(
                branch,
                branch_name,
            )
        ):
            continue

        if (
            city
            and
            not _contains_text(
                branch.get(
                    "city"
                ),
                city,
            )
        ):
            continue

        if (
            area
            and
            not _contains_text(
                branch.get(
                    "area"
                ),
                area,
            )
        ):
            continue

        filtered_branches.append(
            branch
        )

    available_by_branch: dict[
        str,
        int,
    ] = {}

    if variant_id:
        inventory_rows = (
            get_inventory_snapshot_enriched(
                variant_id
            )
        )

        for inventory_row in (
            inventory_rows
            or []
        ):
            branch_id = str(
                inventory_row.get(
                    "branch_id"
                )
                or ""
            )

            if not branch_id:
                continue

            available_quantity = int(
                inventory_row.get(
                    "available_quantity"
                )
                or 0
            )

            if (
                available_quantity
                <= 0
            ):
                continue

            available_by_branch[
                branch_id
            ] = (
                available_quantity
            )

        filtered_branches = [
            branch
            for branch
            in filtered_branches
            if str(
                branch.get(
                    "id"
                )
                or ""
            )
            in available_by_branch
        ]

    has_customer_location = (
        customer_latitude
        is not None
        and
        customer_longitude
        is not None
    )

    results: list[
        dict[
            str,
            Any,
        ]
    ] = []

    for branch in (
        filtered_branches
    ):
        branch_id = str(
            branch.get(
                "id"
            )
            or ""
        )

        latitude = (
            _as_float(
                branch.get(
                    "latitude"
                )
            )
        )

        longitude = (
            _as_float(
                branch.get(
                    "longitude"
                )
            )
        )

        distance_km: (
            float | None
        ) = None

        if (
            has_customer_location
            and
            latitude
            is not None
            and
            longitude
            is not None
        ):
            distance_km = round(
                _haversine_km(
                    float(
                        customer_latitude
                    ),
                    float(
                        customer_longitude
                    ),
                    latitude,
                    longitude,
                ),
                2,
            )

        results.append(
            {
                "branch_id":
                    branch_id,

                "branch_name":
                    branch.get(
                        "name"
                    ),

                # Kept for older service
                # callers and unit tests.
                "name":
                    branch.get(
                        "name"
                    ),

                "city":
                    branch.get(
                        "city"
                    ),

                "area":
                    branch.get(
                        "area"
                    ),

                "address":
                    branch.get(
                        "address"
                    ),

                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "phone":
                    branch.get(
                        "phone"
                    ),

                "opening_time":
                    branch.get(
                        "opening_time"
                    ),

                "closing_time":
                    branch.get(
                        "closing_time"
                    ),

                "available_quantity":
                    (
                        available_by_branch
                        .get(
                            branch_id
                        )
                        if variant_id
                        else None
                    ),

                "distance_km":
                    distance_km,
            }
        )

    if has_customer_location:
        results.sort(
            key=lambda row: (
                row.get(
                    "distance_km"
                )
                is None,

                (
                    row.get(
                        "distance_km"
                    )
                    if row.get(
                        "distance_km"
                    )
                    is not None
                    else float(
                        "inf"
                    )
                ),

                str(
                    row.get(
                        "branch_name"
                    )
                    or ""
                ),
            )
        )

    else:
        results.sort(
            key=lambda row: (
                str(
                    row.get(
                        "city"
                    )
                    or ""
                ),

                str(
                    row.get(
                        "branch_name"
                    )
                    or ""
                ),
            )
        )

    return results


def search_branches(
    *,
    branch_name: str | None = None,
    city: str | None = None,
    area: str | None = None,
    variant_id: str | None = None,
    customer_latitude: (
        float | None
    ) = None,
    customer_longitude: (
        float | None
    ) = None,
) -> list[
    dict[
        str,
        Any,
    ]
]:
    """
    Phase 13 service name used by
    LocationAgent.

    Delegates to the historical public API
    so tests and runtime use one behavior.
    """

    return search_active_branches(
        branch_name=
            branch_name,

        city=
            city,

        area=
            area,

        variant_id=
            variant_id,

        customer_latitude=
            customer_latitude,

        customer_longitude=
            customer_longitude,
    )