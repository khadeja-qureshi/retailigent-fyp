from __future__ import annotations

from typing import Any

from app.agents.product_agent import product_agent
from app.services.recommendation_service import (
    get_recommendation_context,
)


def _first_value(value: Any) -> Any:
    """
    Return the first usable value from a saved
    preference.
    """

    if isinstance(value, list):
        return (
            value[0]
            if value
            else None
        )

    if isinstance(value, str):
        value = value.strip()

        return (
            value
            if value
            else None
        )

    return value


def _memory_value(
    facts: list[dict[str, Any]],
    key: str,
) -> Any:
    """
    Find a usable remembered fact by memory key.
    """

    for fact in facts:
        if (
            fact.get("memory_key")
            != key
        ):
            continue

        value = fact.get(
            "memory_value"
        )

        if (
            value is not None
            and value != ""
        ):
            return value

    return None


class RecommendationAgent:
    """
    Personalized recommendation agent.

    Explicit filters supplied in the current
    message are hard constraints.

    Saved preferences and memories are soft
    personalization constraints.

    If the saved preferences over-constrain the
    search and return zero products, the agent
    retries using only the explicit constraints
    from the current request.
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

        # Keep a copy of what the user explicitly
        # requested in this message.
        explicit = {
            "category": category,
            "color": color,
            "size": size,
            "material": material,
            "min_price": min_price,
            "max_price": max_price,
        }

        context = (
            get_recommendation_context(
                customer_id
            )
        )

        personalization_applied = False

        if context[
            "personalization_allowed"
        ]:
            preferences = (
                context["preferences"]
            )

            facts = (
                context[
                    "remembered_facts"
                ]
            )

            if category is None:
                category = (
                    _first_value(
                        preferences.get(
                            "preferred_categories"
                        )
                    )
                    or
                    _memory_value(
                        facts,
                        "preferred_category",
                    )
                )

                personalization_applied = (
                    personalization_applied
                    or category is not None
                )

            if color is None:
                color = (
                    _first_value(
                        preferences.get(
                            "preferred_colors"
                        )
                    )
                    or
                    _memory_value(
                        facts,
                        "preferred_color",
                    )
                )

                personalization_applied = (
                    personalization_applied
                    or color is not None
                )

            if size is None:
                size = (
                    _first_value(
                        preferences.get(
                            "preferred_sizes"
                        )
                    )
                    or
                    _memory_value(
                        facts,
                        "usual_size",
                    )
                )

                personalization_applied = (
                    personalization_applied
                    or size is not None
                )

            if material is None:
                material = (
                    _memory_value(
                        facts,
                        "preferred_material",
                    )
                )

                personalization_applied = (
                    personalization_applied
                    or material is not None
                )

            if min_price is None:
                min_price = (
                    preferences.get(
                        "budget_min"
                    )
                )

                personalization_applied = (
                    personalization_applied
                    or min_price is not None
                )

            if max_price is None:
                max_price = (
                    preferences.get(
                        "budget_max"
                    )
                )

                personalization_applied = (
                    personalization_applied
                    or max_price is not None
                )

        search_query = (
            query or ""
        ).strip()

        if not search_query:
            search_query = " ".join(
                str(value)
                for value in (
                    category,
                    color,
                    material,
                )
                if value
            ).strip()

        if not search_query:
            search_query = "clothing"

        results = (
            product_agent.search(
                query=search_query,
                match_count=match_count,
                category=category,
                color=color,
                size=size,
                material=material,
                min_price=min_price,
                max_price=max_price,
            )
        )

        # Stored preferences should guide
        # recommendations, but should not cause a
        # broad semantic request such as:
        #
        # "something for a wedding"
        #
        # to incorrectly return no catalog results.
        #
        # Therefore retry once using only the
        # explicit current-message filters.
        if (
            not results
            and personalization_applied
            and bool(
                (query or "").strip()
            )
        ):
            results = (
                product_agent.search(
                    query=search_query,
                    match_count=match_count,
                    category=explicit[
                        "category"
                    ],
                    color=explicit[
                        "color"
                    ],
                    size=explicit[
                        "size"
                    ],
                    material=explicit[
                        "material"
                    ],
                    min_price=explicit[
                        "min_price"
                    ],
                    max_price=explicit[
                        "max_price"
                    ],
                )
            )

        return results


recommendation_agent = (
    RecommendationAgent()
)