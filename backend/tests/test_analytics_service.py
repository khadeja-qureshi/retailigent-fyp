from unittest.mock import MagicMock, patch

import pytest

from app.services.analytics_service import (
    AnalyticsServiceError,
    _safe_limit,
    _read_view,
    get_demand_analytics,
    get_inventory_analytics,
)


def test_safe_limit_is_bounded():
    assert _safe_limit(0) == 1
    assert _safe_limit(25) == 25
    assert _safe_limit(500) == 100


def test_read_view_rejects_unknown_view():
    with pytest.raises(ValueError, match="Unsupported"):
        _read_view("customer_private_data")


@patch("app.services.analytics_service.supabase_admin")
def test_demand_analytics_reads_expected_views(mock_supabase):
    expected = {
        "v_high_interest_low_availability": [{"demand_signal_count": 3}],
        "v_unavailable_searches": [{"signal_count": 2}],
        "v_product_demand_availability": [{"unfulfilled_signal_count": 1}],
    }

    def table_side_effect(name):
        table = MagicMock()
        table.select.return_value.limit.return_value.execute.return_value.data = (
            expected[name]
        )
        return table

    mock_supabase.table.side_effect = table_side_effect

    result = get_demand_analytics(limit=20)

    assert result["high_interest_low_availability"] == [
        {"demand_signal_count": 3}
    ]
    assert result["unavailable_searches"] == [{"signal_count": 2}]
    assert result["product_demand_availability"] == [
        {"unfulfilled_signal_count": 1}
    ]
    assert mock_supabase.table.call_count == 3


@patch("app.services.analytics_service.supabase_admin")
def test_inventory_analytics_reads_branch_summary(mock_supabase):
    mock_supabase.table.return_value.select.return_value.limit.return_value.execute.return_value.data = [
        {"total_variants": 10, "out_of_stock_variants": 2}
    ]

    result = get_inventory_analytics(limit=10)

    assert result["branches"] == [
        {"total_variants": 10, "out_of_stock_variants": 2}
    ]
    mock_supabase.table.assert_called_once_with(
        "v_branch_inventory_summary"
    )


@patch("app.services.analytics_service.supabase_admin")
def test_database_errors_are_wrapped(mock_supabase):
    mock_supabase.table.side_effect = RuntimeError("database unavailable")

    with pytest.raises(
        AnalyticsServiceError,
        match="Analytics data could not be loaded",
    ):
        _read_view("v_unavailable_searches")
