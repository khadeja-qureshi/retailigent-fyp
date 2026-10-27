from __future__ import annotations

from typing import Any

from app.agents.product_agent import product_agent
from app.services.recommendation_service import (
    get_recommendation_context,
)


def _first_value(
    value: Any,
) -> Any:
    """Return the first usable value from a saved preference."""
    if isinstance(value, list):
        return value[0] if value else None

    if isinstance(value, str):
        value = value.strip()
        return value if value else None

    return value


def _memory_value(
    facts: list[dict[str, Any]],
    key: str,
) -> Any:
    """Find a usable remembered fact by memory key."""
    for fact in facts:
        if fact.get("memory_key") != key:
            continue

        value = fact.get("memory_value")

        if value is not None and value != "":
            return value

    return None


def _normalize_text(
    value: Any,
) -> str:
    return " ".join(
        str(value or "")
        .strip()
        .casefold()
        .replace("-", " ")
        .replace("_", " ")
        .split()
    )


def _available_at_preferred_branch(
    result: dict[str, Any],
    preferred_branch: str | None,
) -> bool:
    """
    Return True when a result has positive availability at the
    customer's preferred branch/location.

    Saved branch preference is used only for recommendation ranking.
    It never overrides explicit branch constraints in the current
    user message.
    """
    wanted = _normalize_text(
        preferred_branch
    )

    if not wanted:
        return False

    for row in (
        result.get("inventory")
        or []
    ):
        try:
            available = int(
                row.get(
                    "available_quantity"
                )
                or 0
            )
        except (
            TypeError,
            ValueError,
        ):
            available = 0

        if available <= 0:
            continue

        branch = (
            row.get("branch")
            or {}
        )

        haystack = " ".join(
            _normalize_text(
                branch.get(key)
            )
            for key in (
                "name",
                "city",
                "area",
                "address",
            )
        )

        if wanted in haystack:
            return True

    return False


class RecommendationAgent:
    """
    Personalized recommendation agent.

    Rules:
    1. Explicit filters from the current user message are hard constraints.
    2. Saved preferences and memories are used only when personalization is enabled.
    3. Saved preferences never override an explicit current-message constraint.
    4. Generic recommendations keep saved category/color/size/material/budget filters.
    5. Preference relaxation is only used when a real current query exists.
    6. Preferred branch is a ranking signal, not a correctness constraint.
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

        preferred_branch: str | None = None

        if context[
            "personalization_allowed"
        ]:
            preferences = (
                context["preferences"]
            )

            facts = (
                context["remembered_facts"]
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

            preferred_branch = (
                _memory_value(
                    facts,
                    "preferred_branch",
                )
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

        raw_query = (
            query
            or ""
        ).strip()

        raw_query_normalized = (
            raw_query.casefold()
        )

        generic_recommendation_query = (
            not raw_query
            or any(
                phrase
                in raw_query_normalized
                for phrase in (
                    "recommend",
                    "suggest",
                    "what should i buy",
                    "what would suit me",
                    "what would you recommend",
                    "what do you recommend",
                    "recommend something",
                    "suggest something",
                    "mere liye",
                    "kya loon",
                    "kya lu",
                )
            )
        )

        personalized_query = (
            " ".join(
                str(value)
                for value in (
                    category,
                    color,
                    material,
                )
                if value
            )
            .strip()
        )

        if (
            generic_recommendation_query
            and personalized_query
        ):
            search_query = (
                personalized_query
            )

        elif raw_query:
            search_query = (
                raw_query
            )

        elif personalized_query:
            search_query = (
                personalized_query
            )

        else:
            search_query = (
                "clothing"
            )

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

        if (
            not results
            and personalization_applied
            and raw_query
        ):
            relaxed_category = (
                explicit["category"]
                or category
            )

            relaxed_material = (
                explicit["material"]
                or material
            )

            if (
                relaxed_category
                or relaxed_material
            ):
                relaxed_query = (
                    " ".join(
                        str(value)
                        for value in (
                            relaxed_category,
                            relaxed_material,
                        )
                        if value
                    )
                    .strip()
                    or raw_query
                )

                results = (
                    product_agent.search(
                        query=relaxed_query,
                        match_count=match_count,
                        category=relaxed_category,
                        color=explicit[
                            "color"
                        ],
                        size=explicit[
                            "size"
                        ],
                        material=relaxed_material,
                        min_price=explicit[
                            "min_price"
                        ],
                        max_price=explicit[
                            "max_price"
                        ],
                    )
                )

        if (
            not results
            and personalization_applied
            and raw_query
        ):
            results = (
                product_agent.search(
                    query=raw_query,
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

        if (
            preferred_branch
            and results
        ):
            results = sorted(
                results,
                key=lambda item: (
                    not
                    _available_at_preferred_branch(
                        item,
                        preferred_branch,
                    )
                ),
            )

        return results


recommendation_agent = (
    RecommendationAgent()
)