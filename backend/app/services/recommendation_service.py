from __future__ import annotations

import logging
from typing import Any

from app.core.supabase_client import supabase_admin
from app.services.memory_service import (
    get_customer_context_snapshot,
)

logger = logging.getLogger(__name__)

PREFERENCE_FIELDS = (
    "preferred_categories",
    "preferred_colors",
    "preferred_sizes",
    "preferred_styles",
    "budget_min",
    "budget_max",
    "allow_personalized_recommendations",
)


def get_recommendation_context(
    customer_id: str,
) -> dict[str, Any]:
    """
    Load saved personalization data only when the customer
    has explicitly enabled personalized recommendations.

    If consent is absent or disabled, saved preferences and
    remembered facts are never returned to recommendation logic.
    Current-message filters are handled separately by the caller.
    """
    response = (
        supabase_admin
        .table("customer_preferences")
        .select(
            ", ".join(PREFERENCE_FIELDS)
        )
        .eq("customer_id", customer_id)
        .limit(1)
        .execute()
    )

    rows = response.data or []

    if not rows:
        return {
            "personalization_allowed": False,
            "preferences": {},
            "remembered_facts": [],
        }

    preferences = rows[0]

    if not preferences.get(
        "allow_personalized_recommendations",
        False,
    ):
        return {
            "personalization_allowed": False,
            "preferences": {},
            "remembered_facts": [],
        }

    try:
        snapshot = get_customer_context_snapshot(
            customer_id
        )
    except Exception:
        logger.warning(
            "Could not load memory for personalized "
            "recommendations; continuing with saved preferences only.",
            exc_info=True,
        )
        snapshot = {}

    if not isinstance(snapshot, dict):
        snapshot = {}

    remembered_facts = []

    for fact in snapshot.get("remembered_facts", []):
        if not isinstance(fact, dict):
            continue

        if fact.get("is_stale", False):
            continue

        confidence = fact.get(
            "effective_confidence",
            fact.get("confidence", 0),
        )

        try:
            confidence = float(confidence or 0)
        except (TypeError, ValueError):
            continue

        if confidence < 0.70:
            continue

        remembered_facts.append(fact)

    return {
        "personalization_allowed": True,
        "preferences": {
            key: preferences.get(key)
            for key in PREFERENCE_FIELDS
            if key != "allow_personalized_recommendations"
        },
        "remembered_facts": remembered_facts,
    }