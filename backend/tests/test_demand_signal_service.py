from unittest.mock import MagicMock

import pytest

from app.services import demand_signal_service as service


@pytest.fixture
def mock_supabase(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(service, "supabase_admin", client)
    return client


def test_record_demand_signal_inserts_payload(mock_supabase):
    result = service.record_demand_signal(
        signal_type="no_catalog_match",
        customer_id="customer-123",
        requested_size="M",
        requested_color="Blue",
        metadata={"query": "blue shirt"},
    )

    assert result is True
    mock_supabase.table.assert_called_once_with("demand_signals")

    inserted_payload = (
        mock_supabase.table.return_value.insert.call_args.args[0]
    )
    assert inserted_payload == {
        "signal_type": "no_catalog_match",
        "fulfilled": False,
        "metadata": {"query": "blue shirt"},
        "customer_id": "customer-123",
        "requested_size": "M",
        "requested_color": "Blue",
    }
    mock_supabase.table.return_value.insert.return_value.execute.assert_called_once()


def test_record_demand_signal_includes_optional_ids(mock_supabase):
    result = service.record_demand_signal(
        signal_type="insufficient_stock",
        product_id="product-123",
        variant_id="variant-123",
        branch_id="branch-123",
        fulfilled=True,
    )

    assert result is True
    inserted_payload = (
        mock_supabase.table.return_value.insert.call_args.args[0]
    )
    assert inserted_payload["product_id"] == "product-123"
    assert inserted_payload["variant_id"] == "variant-123"
    assert inserted_payload["branch_id"] == "branch-123"
    assert inserted_payload["fulfilled"] is True
    assert "customer_id" not in inserted_payload
    assert "requested_size" not in inserted_payload


def test_record_demand_signal_uses_empty_metadata_by_default(mock_supabase):
    result = service.record_demand_signal(signal_type="no_catalog_match")

    assert result is True
    inserted_payload = (
        mock_supabase.table.return_value.insert.call_args.args[0]
    )
    assert inserted_payload["metadata"] == {}
    assert inserted_payload["fulfilled"] is False


@pytest.mark.parametrize("signal_type", ["", " ", "\t"])
def test_record_demand_signal_rejects_blank_type(mock_supabase, signal_type):
    with pytest.raises(ValueError, match="signal_type"):
        service.record_demand_signal(signal_type=signal_type)

    mock_supabase.table.assert_not_called()


def test_record_demand_signal_returns_false_on_database_error(
    mock_supabase,
):
    mock_supabase.table.return_value.insert.return_value.execute.side_effect = (
        RuntimeError("simulated database failure")
    )

    result = service.record_demand_signal(
        signal_type="no_catalog_match",
    )

    assert result is False
