from app.agents.customer_interaction_agent import (
    customer_interaction_agent,
)


def _context_with_size(
    value: str,
    *,
    effective_confidence: float,
    is_stale: bool,
) -> dict:
    return {
        "remembered_facts": [
            {
                "memory_key":
                    "usual_size",

                "memory_value":
                    value,

                "confidence":
                    0.9,

                "effective_confidence":
                    effective_confidence,

                "is_stale":
                    is_stale,
            }
        ]
    }


def test_ordinary_search_does_not_silently_apply_memory():
    parsed = (
        customer_interaction_agent
        .parse(
            "Show me kurtas",

            customer_context=(
                _context_with_size(
                    "M",
                    effective_confidence=0.9,
                    is_stale=False,
                )
            ),
        )
    )


    # Ordinary product search must reflect the
    # current request itself.
    #
    # Personalized saved memory is applied by
    # RecommendationAgent where consent is checked.
    assert (
        parsed.entities.size
        is None
    )


    assert (
        parsed.context_used
        == {}
    )


def test_explicit_size_is_preserved_even_when_memory_differs():
    parsed = (
        customer_interaction_agent
        .parse(
            "Show me kurtas size L",

            customer_context=(
                _context_with_size(
                    "M",
                    effective_confidence=0.9,
                    is_stale=False,
                )
            ),
        )
    )


    assert (
        parsed.entities.size
        == "L"
    )


    assert (
        "usual_size"
        not in parsed.context_used
    )


def test_stale_memory_is_not_applied_to_ordinary_search():
    parsed = (
        customer_interaction_agent
        .parse(
            "Show me kurtas",

            customer_context=(
                _context_with_size(
                    "M",
                    effective_confidence=0.45,
                    is_stale=True,
                )
            ),
        )
    )


    assert (
        parsed.entities.size
        is None
    )


    assert (
        parsed.context_used
        == {}
    )