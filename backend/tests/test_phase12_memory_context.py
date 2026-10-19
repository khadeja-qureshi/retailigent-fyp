from app.agents.customer_interaction_agent import (
    customer_interaction_agent,
)


def test_remembered_size_is_used_for_search():
    parsed = (
        customer_interaction_agent
        .parse(
            "Show me kurtas",
            customer_context={
                "remembered_facts": [
                    {
                        "memory_key":
                            "usual_size",
                        "memory_value":
                            "M",
                        "confidence":
                            0.9,
                        "effective_confidence":
                            0.9,
                        "is_stale":
                            False,
                    }
                ]
            },
        )
    )

    assert (
        parsed.entities.size
        == "M"
    )

    assert (
        parsed.context_used[
            "usual_size"
        ]
        == "M"
    )


def test_explicit_size_overrides_memory():
    parsed = (
        customer_interaction_agent
        .parse(
            "Show me kurtas size L",
            customer_context={
                "remembered_facts": [
                    {
                        "memory_key":
                            "usual_size",
                        "memory_value":
                            "M",
                        "confidence":
                            0.9,
                        "effective_confidence":
                            0.9,
                        "is_stale":
                            False,
                    }
                ]
            },
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


def test_low_confidence_stale_size_is_not_applied():
    parsed = (
        customer_interaction_agent
        .parse(
            "Show me kurtas",
            customer_context={
                "remembered_facts": [
                    {
                        "memory_key":
                            "usual_size",
                        "memory_value":
                            "M",
                        "confidence":
                            0.9,
                        "effective_confidence":
                            0.45,
                        "is_stale":
                            True,
                    }
                ]
            },
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