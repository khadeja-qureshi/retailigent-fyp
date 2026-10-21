from __future__ import annotations

from typing import Any

from app.agents.product_agent import product_agent
from app.services.recommendation_service import (
    get_recommendation_context,
)


def _first_value(value: Any) -> Any:
    """Return the first usable value from a saved preference."""
    if isinstance(value, list):
        return value[0] if value else None

    if isinstance(value, str):
        value = value.strip()
        return value or None

    return value


def _memory_value(
    facts: list[dict[str, Any]],
    key: str,
) -> Any:
    """Find a usable, consented memory fact by key."""
    for fact in facts:
        if fact.get("memory_key") != key:
            continue

        value = fact.get("memory_value")

        if value is not None and value != "":
            return value

    return None


class RecommendationAgent:
    """
    Personalized product recommendations.

    Explicit filters from the current message take precedence.
    Saved preferences and memory are used only when the customer
    has opted in to personalized recommendations.
    """

    def recommend(
        self,
        customer_id: str,
        query: str = "",
        *,
        category: str | None = None,
        color: str | None = None,
        size: str | None = None,
        material: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        match_count: int = 10,
    ) -> list[dict[str, Any]]:
        context = get_recommendation_context(customer_id)

        # Only explicit current-message filters are available
        # when personalized recommendations are not permitted.
        if context["personalization_allowed"]:
            preferences = context["preferences"]
            facts = context["remembered_facts"]

            category = (
                category
                or _first_value(
                    preferences.get("preferred_categories")
                )
                or _memory_value(facts, "preferred_category")
            )

            color = (
                color
                or _first_value(
                    preferences.get("preferred_colors")
                )
            )

            size = (
                size
                or _first_value(
                    preferences.get("preferred_sizes")
                )
                or _memory_value(facts, "usual_size")
            )

            material = (
                material
                or _memory_value(facts, "preferred_material")
            )

            if min_price is None:
                min_price = preferences.get("budget_min")

            if max_price is None:
                max_price = preferences.get("budget_max")

        search_query = (query or "").strip()

        if not search_query:
            search_query = " ".join(
                str(value)
                for value in (category, color, material)
                if value
            ).strip()

        if not search_query:
            search_query = "clothing"

        return product_agent.search(
            query=search_query,
            match_count=match_count,
            category=category,
            color=color,
            size=size,
            material=material,
            min_price=min_price,
            max_price=max_price,
        )


recommendation_agent = RecommendationAgent()
