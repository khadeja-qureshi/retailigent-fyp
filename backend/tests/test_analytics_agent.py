from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.agents.analytics_agent import AnalyticsAgent
from app.services.analytics_service import AnalyticsServiceError


@pytest.fixture
def agent():
    return AnalyticsAgent()


@pytest.fixture
def analytics_data():
    return (
        {
            "high_interest_low_availability": [
                {
                    "product_id": "product-1",
                    "variant_id": "variant-1",
                    "branch_id": "branch-1",
                    "demand_signal_count": 5,
                    "unfulfilled_signal_count": 5,
                }
            ],
            "unavailable_searches": [
                {
                    "signal_type": "requested_variant_unavailable",
                    "requested_size": "M",
                    "requested_color": "Black",
                    "signal_count": 5,
                }
            ],
            "product_demand_availability": [
                {
                    "product_id": "product-1",
                    "demand_signal_count": 5,
                    "unfulfilled_signal_count": 5,
                }
            ],
        },
        {
            "branches": [
                {
                    "branch_id": "branch-1",
                    "total_variants": 10,
                    "available_variants": 5,
                    "low_stock_variants": 2,
                    "out_of_stock_variants": 3,
                }
            ]
        },
    )


@patch("app.agents.analytics_agent.analytics_service")
@patch("app.agents.analytics_agent.httpx.post")
def test_answer_uses_retrieved_analytics(
    mock_post,
    mock_service,
    agent,
    analytics_data,
):
    demand, inventory = analytics_data
    mock_service.get_demand_analytics.return_value = demand
    mock_service.get_inventory_analytics.return_value = inventory

    response = MagicMock()
    response.json.return_value = {
        "response": (
            "Five unmet signals were recorded for size M in Black."
        )
    }
    mock_post.return_value = response

    result = agent.answer("Which requested variants are unavailable?")

    assert result["data_status"] == "available"
    assert "Five unmet signals" in result["answer"]
    assert result["sources"][0]["record_count"] == 3
    assert result["sources"][1]["record_count"] == 1
    mock_service.get_demand_analytics.assert_called_once_with(limit=20)
    mock_service.get_inventory_analytics.assert_called_once_with(limit=20)
    mock_post.assert_called_once()

    prompt = mock_post.call_args.kwargs["json"]["prompt"]
    assert "product-1" in prompt
    assert "Black" in prompt


@patch("app.agents.analytics_agent.analytics_service")
def test_empty_analytics_is_not_reported_as_zero(
    mock_service,
    agent,
):
    mock_service.get_demand_analytics.return_value = {
        "high_interest_low_availability": [],
        "unavailable_searches": [],
        "product_demand_availability": [],
    }
    mock_service.get_inventory_analytics.return_value = {
        "branches": [],
    }

    result = agent.answer("What is the unmet demand?")

    assert result["data_status"] == "empty"
    assert "does not establish" in result["answer"]
    assert "zero" in result["answer"]
    assert result["sources"][0]["record_count"] == 0


@patch("app.agents.analytics_agent.analytics_service")
def test_database_failure_is_reported_as_unavailable(
    mock_service,
    agent,
):
    mock_service.get_demand_analytics.side_effect = AnalyticsServiceError(
        "Analytics data could not be loaded."
    )

    result = agent.answer("Summarize demand")

    assert result["data_status"] == "unavailable"
    assert "couldn't retrieve" in result["answer"]
    assert result["sources"] == []
    mock_service.get_inventory_analytics.assert_not_called()


@pytest.mark.parametrize(
    "question",
    [
        "",
        "   ",
        "x" * 1001,
    ],
)
def test_invalid_question_is_rejected(agent, question):
    with pytest.raises(ValueError):
        agent.answer(question)


@patch("app.agents.analytics_agent.analytics_service")
@patch("app.agents.analytics_agent.httpx.post")
def test_ollama_failure_does_not_invent_a_summary(
    mock_post,
    mock_service,
    agent,
    analytics_data,
):
    demand, inventory = analytics_data
    mock_service.get_demand_analytics.return_value = demand
    mock_service.get_inventory_analytics.return_value = inventory

    mock_post.side_effect = httpx.ConnectError("Ollama unavailable")

    result = agent.answer("Summarize demand")

    assert result["data_status"] == "available"
    assert "couldn't generate a summary" in result["answer"]
    assert result["sources"][0]["record_count"] == 3
