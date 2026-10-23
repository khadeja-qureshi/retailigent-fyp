from __future__ import annotations

import logging
from typing import Any

from app.core.supabase_client import supabase_admin

logger = logging.getLogger(__name__)


class AnalyticsServiceError(Exception):
    """Raised when staff analytics cannot be retrieved."""


ANALYTICS_VIEWS = {
    "high_interest_low_availability": (
        "v_high_interest_low_availability"
    ),
    "unavailable_searches": "v_unavailable_searches",
    "branch_inventory_summary": "v_branch_inventory_summary",
    "product_demand_availability": (
        "v_product_demand_availability"
    ),
}


def _safe_limit(limit: int, maximum: int = 100) -> int:
    return max(1, min(limit, maximum))


def _read_view(
    view_name: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if view_name not in ANALYTICS_VIEWS.values():
        raise ValueError("Unsupported analytics view.")

    try:
        response = (
            supabase_admin.table(view_name)
            .select("*")
            .limit(_safe_limit(limit))
            .execute()
        )
        return response.data or []
    except Exception as exc:
        logger.exception(
            "Could not read analytics view %s.",
            view_name,
        )
        raise AnalyticsServiceError(
            "Analytics data could not be loaded."
        ) from exc


def get_demand_analytics(
    *,
    limit: int = 50,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)

    return {
        "high_interest_low_availability": _read_view(
            ANALYTICS_VIEWS["high_interest_low_availability"],
            limit=safe_limit,
        ),
        "unavailable_searches": _read_view(
            ANALYTICS_VIEWS["unavailable_searches"],
            limit=safe_limit,
        ),
        "product_demand_availability": _read_view(
            ANALYTICS_VIEWS["product_demand_availability"],
            limit=safe_limit,
        ),
    }


def get_inventory_analytics(
    *,
    limit: int = 50,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)

    return {
        "branches": _read_view(
            ANALYTICS_VIEWS["branch_inventory_summary"],
            limit=safe_limit,
        ),
    }
