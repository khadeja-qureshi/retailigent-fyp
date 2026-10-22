import os
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault(
    "SUPABASE_URL",
    "http://127.0.0.1:54321",
)
os.environ.setdefault(
    "SUPABASE_SECRET_KEY",
    "test-only-not-a-real-key",
)

import pytest

from app.services import support_service


@pytest.fixture
def mocked_supabase(monkeypatch):
    tickets = MagicMock()
    messages = MagicMock()

    tickets.insert.return_value = tickets
    tickets.delete.return_value = tickets
    tickets.eq.return_value = tickets

    messages.insert.return_value = messages

    def get_table(name):
        if name == "support_escalations":
            return tickets
        if name == "support_ticket_messages":
            return messages
        raise AssertionError(f"Unexpected table: {name}")

    client = MagicMock()
    client.table.side_effect = get_table

    monkeypatch.setattr(
        support_service,
        "supabase_admin",
        client,
    )

    return {
        "client": client,
        "tickets": tickets,
        "messages": messages,
    }


def test_create_support_ticket_persists_ticket_and_initial_message(
    mocked_supabase,
):
    mocked_supabase["tickets"].execute.return_value = (
        SimpleNamespace(
            data=[
                {
                    "id": "ticket-123",
                    "status": "open",
                    "subject": "Delayed order",
                }
            ]
        )
    )
    mocked_supabase["messages"].execute.return_value = (
        SimpleNamespace(data=[{"id": "message-123"}])
    )

    result = support_service.create_support_ticket(
        customer_id="customer-123",
        conversation_id="conversation-123",
        subject="  Delayed order  ",
        description="  My order has not arrived.  ",
    )

    assert result == {
        "ticket_id": "ticket-123",
        "status": "open",
        "subject": "Delayed order",
    }

    ticket_payload = (
        mocked_supabase["tickets"]
        .insert.call_args.args[0]
    )
    assert ticket_payload["customer_id"] == "customer-123"
    assert ticket_payload["conversation_id"] == "conversation-123"
    assert ticket_payload["subject"] == "Delayed order"
    assert ticket_payload["description"] == "My order has not arrived."
    assert ticket_payload["status"] == "open"
    assert ticket_payload["priority"] == "normal"

    message_payload = (
        mocked_supabase["messages"]
        .insert.call_args.args[0]
    )
    assert message_payload["ticket_id"] == "ticket-123"
    assert message_payload["sender_id"] == "customer-123"
    assert message_payload["sender_type"] == "customer"
    assert message_payload["message"] == "My order has not arrived."


@pytest.mark.parametrize(
    ("subject", "description"),
    [
        ("   ", "A description"),
        ("A subject", "   "),
    ],
)
def test_create_support_ticket_rejects_empty_fields(
    mocked_supabase,
    subject,
    description,
):
    with pytest.raises(ValueError):
        support_service.create_support_ticket(
            customer_id="customer-123",
            conversation_id="conversation-123",
            subject=subject,
            description=description,
        )

    mocked_supabase["client"].table.assert_not_called()


def test_create_support_ticket_cleans_up_if_initial_message_fails(
    mocked_supabase,
):
    mocked_supabase["tickets"].execute.return_value = (
        SimpleNamespace(
            data=[
                {
                    "id": "ticket-456",
                    "status": "open",
                    "subject": "Wrong item",
                }
            ]
        )
    )
    mocked_supabase["messages"].execute.side_effect = (
        RuntimeError("Simulated message-write failure")
    )

    with pytest.raises(support_service.SupportTicketError):
        support_service.create_support_ticket(
            customer_id="customer-123",
            conversation_id="conversation-123",
            subject="Wrong item",
            description="I received the wrong item.",
        )

    mocked_supabase["tickets"].delete.assert_called_once()
    assert mocked_supabase["tickets"].eq.call_count == 2


def test_create_support_ticket_does_not_claim_success_without_ticket_id(
    mocked_supabase,
):
    mocked_supabase["tickets"].execute.return_value = (
        SimpleNamespace(data=[])
    )

    with pytest.raises(support_service.SupportTicketError):
        support_service.create_support_ticket(
            customer_id="customer-123",
            conversation_id="conversation-123",
            subject="Missing ticket",
            description="Please help.",
        )

    mocked_supabase["messages"].insert.assert_not_called()
    mocked_supabase["tickets"].delete.assert_not_called()


def test_create_support_ticket_wraps_ticket_database_errors(
    mocked_supabase,
):
    mocked_supabase["tickets"].execute.side_effect = (
        RuntimeError("Simulated database failure")
    )

    with pytest.raises(
        support_service.SupportTicketError,
        match="Unable to create the support ticket",
    ):
        support_service.create_support_ticket(
            customer_id="customer-123",
            conversation_id="conversation-123",
            subject="Database error",
            description="Please help.",
        )

    mocked_supabase["messages"].insert.assert_not_called()
