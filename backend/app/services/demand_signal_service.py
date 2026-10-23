from __future__ import annotations

import logging
from typing import Any

from app.core.supabase_client import supabase_admin

logger = logging.getLogger(__name__)


def record_demand_signal(
    *,
    signal_type: str,
    customer_id: str | None = None,
    product_id: str | None = None,
    variant_id: str | None = None,
    branch_id: str | None = None,
    requested_size: str | None = None,
    requested_color: str | None = None,
    fulfilled: bool = False,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Record an unmet-demand signal without disrupting the customer flow.

    Returns True when the insert succeeds and False when it fails.
    """
    if not signal_type or not signal_type.strip():
        raise ValueError("signal_type must be a non-empty string")

    payload: dict[str, Any] = {
        "signal_type": signal_type.strip(),
        "fulfilled": fulfilled,
        "metadata": metadata or {},
    }

    optional_fields = {
        "customer_id": customer_id,
        "product_id": product_id,
        "variant_id": variant_id,
        "branch_id": branch_id,
        "requested_size": requested_size,
        "requested_color": requested_color,
    }

    payload.update(
        {
            key: value
            for key, value in optional_fields.items()
            if value is not None
        }
    )

    try:
        supabase_admin.table("demand_signals").insert(payload).execute()
        return True
    except Exception:
        logger.warning(
            "Failed to record demand signal: %s",
            signal_type,
            exc_info=True,
        )
        return False
