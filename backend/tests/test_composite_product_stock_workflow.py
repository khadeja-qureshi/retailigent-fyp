from app.agents.orchestrator_agent import (
    _rank_inventory_rows,
    _wants_highest_stock_ranking,
    _wants_product_stock_composite,
)


def test_composite_detection_for_rich_shopping_query():
    message = (
        "Find me a cotton kurta in size M under Rs. 5000 that is "
        "available in Karachi and tell me which branch has the most stock."
    )

    assert _wants_product_stock_composite(message) is True
    assert _wants_highest_stock_ranking(message) is True


def test_plain_product_search_does_not_trigger_inventory_chain():
    assert _wants_product_stock_composite("Show me cotton kurtas") is False


def test_inventory_ranking_uses_verified_quantity():
    rows = [
        (
            "variant-a",
            [
                {
                    "available_quantity": 3,
                    "branch": {
                        "name": "Clifton",
                        "city": "Karachi",
                        "area": "Clifton",
                    },
                },
                {
                    "available_quantity": 8,
                    "branch": {
                        "name": "Tariq Road",
                        "city": "Karachi",
                        "area": "PECHS",
                    },
                },
            ],
        ),
        (
            "variant-b",
            [
                {
                    "available_quantity": 20,
                    "branch": {
                        "name": "Gulberg",
                        "city": "Lahore",
                        "area": "Gulberg",
                    },
                }
            ],
        ),
    ]

    ranked = _rank_inventory_rows(
        rows,
        requested_location="Karachi",
    )

    assert [item[1]["available_quantity"] for item in ranked] == [8, 3]
    assert ranked[0][1]["branch"]["name"] == "Tariq Road"
