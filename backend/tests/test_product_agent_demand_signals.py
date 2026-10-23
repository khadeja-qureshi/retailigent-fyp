from unittest.mock import patch

from app.agents.product_agent import ProductAgent


def test_no_catalog_match_records_demand_when_enabled():
    agent = ProductAgent()

    with (
        patch("app.agents.product_agent.search_variants", return_value=[]),
        patch("app.agents.product_agent.record_demand_signal") as record,
    ):
        result = agent.search(
            query="blue kurta",
            color="Blue",
            size="M",
            customer_id="customer-123",
            track_demand=True,
        )

    assert result == []
    record.assert_called_once_with(
        signal_type="no_catalog_match",
        customer_id="customer-123",
        branch_id=None,
        requested_size="M",
        requested_color="Blue",
        metadata={"query": "blue kurta"},
    )


def test_no_catalog_match_does_not_record_by_default():
    agent = ProductAgent()

    with (
        patch("app.agents.product_agent.search_variants", return_value=[]),
        patch("app.agents.product_agent.record_demand_signal") as record,
    ):
        result = agent.search(query="blue kurta")

    assert result == []
    record.assert_not_called()


def test_filtered_out_results_record_requested_variant():
    agent = ProductAgent()
    candidates = [
        {
            "product_id": "product-123",
            "variant_id": "variant-123",
            "product": {"material": "cotton"},
            "variant": {
                "color": {"name": "White"},
                "size": {"name": "L"},
            },
            "pricing": {"effective_price": 1000},
            "inventory": [],
        }
    ]

    with (
        patch(
            "app.agents.product_agent.search_variants",
            return_value=candidates,
        ),
        patch("app.agents.product_agent.record_demand_signal") as record,
    ):
        result = agent.search(
            query="blue kurta",
            color="Blue",
            size="M",
            customer_id="customer-123",
            track_demand=True,
        )

    assert result == []
    record.assert_called_once_with(
        signal_type="requested_variant_unavailable",
        customer_id="customer-123",
        product_id="product-123",
        variant_id="variant-123",
        branch_id=None,
        requested_size="M",
        requested_color="Blue",
        metadata={
            "query": "blue kurta",
            "requested_material": None,
            "requested_category": None,
            "min_price": None,
            "max_price": None,
            "requested_city": None,
            "candidate_count": 1,
        },
    )


def test_successful_search_does_not_record_unmet_demand():
    agent = ProductAgent()
    candidates = [
        {
            "product_id": "product-123",
            "variant_id": "variant-123",
            "product": {"material": "cotton"},
            "variant": {
                "color": {"name": "Blue"},
                "size": {"name": "M"},
            },
            "pricing": {"effective_price": 1000},
            "inventory": [],
        }
    ]

    with (
        patch(
            "app.agents.product_agent.search_variants",
            return_value=candidates,
        ),
        patch("app.agents.product_agent.record_demand_signal") as record,
    ):
        result = agent.search(
            query="blue kurta",
            color="Blue",
            size="M",
            track_demand=True,
        )

    assert len(result) == 1
    record.assert_not_called()

def test_filtered_out_results_without_ids_record_null_attribution():
    agent = ProductAgent()
    candidates = [
        {
            "product": {"material": "cotton"},
            "variant": {
                "color": {"name": "White"},
                "size": {"name": "L"},
            },
            "pricing": {"effective_price": 1000},
            "inventory": [],
        }
    ]

    with (
        patch(
            "app.agents.product_agent.search_variants",
            return_value=candidates,
        ),
        patch("app.agents.product_agent.record_demand_signal") as record,
    ):
        result = agent.search(
            query="blue kurta",
            color="Blue",
            size="M",
            track_demand=True,
        )

    assert result == []
    record.assert_called_once_with(
        signal_type="requested_variant_unavailable",
        customer_id=None,
        product_id=None,
        variant_id=None,
        branch_id=None,
        requested_size="M",
        requested_color="Blue",
        metadata={
            "query": "blue kurta",
            "requested_material": None,
            "requested_category": None,
            "min_price": None,
            "max_price": None,
            "requested_city": None,
            "candidate_count": 1,
        },
    )