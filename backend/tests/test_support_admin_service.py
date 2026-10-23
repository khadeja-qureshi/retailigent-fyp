from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services import support_admin_service as service


@pytest.fixture
def mocked_supabase(monkeypatch):
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.limit.return_value = query

    client = MagicMock()
    client.table.return_value = query

    monkeypatch.setattr(service, "supabase_admin", client)

    return {"client": client, "query": query}


def test_list_tickets_sorts_by_priority(mocked_supabase):
    mocked_supabase["query"].execute.return_value = SimpleNamespace(
        data=[
            {"id": "low-1", "priority": "low", "updated_at": "2026-10-22T12:00:00Z"},
            {"id": "normal-1", "priority": "normal", "updated_at": "2026-10-22T12:00:00Z"},
            {"id": "urgent-1", "priority": "urgent", "updated_at": "2026-10-22T12:00:00Z"},
            {"id": "high-1", "priority": "high", "updated_at": "2026-10-22T12:00:00Z"},
        ]
    )

    result = service.list_support_tickets()

    assert [ticket["id"] for ticket in result] == [
        "urgent-1",
        "high-1",
        "normal-1",
        "low-1",
    ]


def test_list_tickets_applies_filters_and_caps_limit(mocked_supabase):
    mocked_supabase["query"].execute.return_value = SimpleNamespace(data=[])

    result = service.list_support_tickets(
        status="open",
        priority="urgent",
        limit=500,
    )

    assert result == []
    mocked_supabase["query"].eq.assert_any_call("status", "open")
    mocked_supabase["query"].eq.assert_any_call("priority", "urgent")
    mocked_supabase["query"].limit.assert_called_once_with(100)
    mocked_supabase["query"].order.assert_called_once_with(
        "updated_at",
        desc=True,
    )


def test_list_tickets_clamps_minimum_limit(mocked_supabase):
    mocked_supabase["query"].execute.return_value = SimpleNamespace(data=[])

    service.list_support_tickets(limit=0)

    mocked_supabase["query"].limit.assert_called_once_with(1)


def test_list_tickets_returns_empty_list_for_no_rows(mocked_supabase):
    mocked_supabase["query"].execute.return_value = SimpleNamespace(data=None)

    assert service.list_support_tickets() == []


def test_list_tickets_wraps_database_errors(mocked_supabase):
    mocked_supabase["query"].execute.side_effect = RuntimeError("database unavailable")

    with pytest.raises(
        service.SupportAdminServiceError,
        match="queue could not be loaded",
    ):
        service.list_support_tickets()


def test_list_tickets_uses_newest_first_within_same_priority(mocked_supabase):
    mocked_supabase["query"].execute.return_value = SimpleNamespace(
        data=[
            {"id": "older", "priority": "high", "updated_at": "2026-10-20T10:00:00Z"},
            {"id": "newer", "priority": "high", "updated_at": "2026-10-22T10:00:00Z"},
            {"id": "urgent", "priority": "urgent", "updated_at": "2026-10-19T10:00:00Z"},
        ]
    )

    result = service.list_support_tickets()

    assert [ticket["id"] for ticket in result] == [
        "urgent",
        "newer",
        "older",
    ]


def test_get_support_ticket_returns_matching_ticket(mocked_supabase):
    ticket = {"id": "ticket-1", "subject": "Order delay"}
    mocked_supabase["query"].execute.return_value = SimpleNamespace(
        data=[ticket]
    )

    result = service.get_support_ticket("ticket-1")

    assert result == ticket
    mocked_supabase["query"].eq.assert_called_once_with("id", "ticket-1")
    mocked_supabase["query"].limit.assert_called_once_with(1)


def test_get_support_ticket_returns_none_when_missing(mocked_supabase):
    mocked_supabase["query"].execute.return_value = SimpleNamespace(data=[])

    assert service.get_support_ticket("missing-ticket") is None


def test_get_support_ticket_rejects_blank_id(mocked_supabase):
    with pytest.raises(ValueError, match="ticket ID is required"):
        service.get_support_ticket("   ")

    mocked_supabase["client"].table.assert_not_called()


def test_list_ticket_messages_returns_chronological_rows(mocked_supabase):
    messages = [
        {"id": "message-1", "created_at": "2026-10-22T10:00:00Z"},
        {"id": "message-2", "created_at": "2026-10-22T10:05:00Z"},
    ]
    mocked_supabase["query"].execute.return_value = SimpleNamespace(
        data=messages
    )

    result = service.list_support_ticket_messages("ticket-1")

    assert result == messages
    mocked_supabase["client"].table.assert_called_with(
        "support_ticket_messages"
    )
    mocked_supabase["query"].eq.assert_called_once_with(
        "ticket_id",
        "ticket-1",
    )
    mocked_supabase["query"].order.assert_called_once_with(
        "created_at",
        desc=False,
    )
    mocked_supabase["query"].limit.assert_called_once_with(500)


def test_list_ticket_messages_rejects_blank_id(mocked_supabase):
    with pytest.raises(ValueError, match="ticket ID is required"):
        service.list_support_ticket_messages("")

    mocked_supabase["client"].table.assert_not_called()


def test_list_ticket_messages_wraps_database_errors(mocked_supabase):
    mocked_supabase["query"].execute.side_effect = RuntimeError(
        "database unavailable"
    )

    with pytest.raises(
        service.SupportAdminServiceError,
        match="conversation could not be loaded",
    ):
        service.list_support_ticket_messages("ticket-1")


def test_update_ticket_changes_status_and_priority(mocked_supabase):
    updated = {
        "id": "ticket-1",
        "status": "in_progress",
        "priority": "urgent",
    }
    mocked_supabase["query"].update.return_value = mocked_supabase["query"]
    mocked_supabase["query"].execute.return_value = SimpleNamespace(
        data=[updated]
    )

    result = service.update_support_ticket(
        ticket_id="ticket-1",
        status="in_progress",
        priority="urgent",
    )

    assert result == updated
    mocked_supabase["query"].update.assert_called_once_with(
        {"status": "in_progress", "priority": "urgent"}
    )
    mocked_supabase["query"].eq.assert_called_with("id", "ticket-1")


def test_update_ticket_can_unassign_staff(mocked_supabase):
    mocked_supabase["query"].update.return_value = mocked_supabase["query"]
    mocked_supabase["query"].execute.return_value = SimpleNamespace(
        data=[{"id": "ticket-1", "assigned_staff_id": None}]
    )

    service.update_support_ticket(
        ticket_id="ticket-1",
        assigned_staff_id=None,
        update_assignment=True,
    )

    mocked_supabase["query"].update.assert_called_once_with(
        {"assigned_staff_id": None}
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"status": "invalid"}, "status"),
        ({"priority": "critical"}, "priority"),
        ({}, "At least one"),
    ],
)
def test_update_ticket_rejects_invalid_or_empty_updates(
    mocked_supabase,
    kwargs,
    message,
):
    with pytest.raises(ValueError, match=message):
        service.update_support_ticket(
            ticket_id="ticket-1",
            **kwargs,
        )

    mocked_supabase["client"].table.assert_not_called()


def test_update_ticket_returns_none_when_not_found(mocked_supabase):
    mocked_supabase["query"].update.return_value = mocked_supabase["query"]
    mocked_supabase["query"].execute.return_value = SimpleNamespace(data=[])

    assert service.update_support_ticket(
        ticket_id="missing",
        status="resolved",
    ) is None


def test_add_staff_reply_persists_trimmed_message(mocked_supabase):
    reply = {
        "id": "message-1",
        "ticket_id": "ticket-1",
        "sender_id": "staff-1",
        "sender_type": "staff",
        "message": "We are investigating.",
    }
    mocked_supabase["query"].insert.return_value = mocked_supabase["query"]
    mocked_supabase["query"].execute.return_value = SimpleNamespace(
        data=[reply]
    )

    result = service.add_staff_ticket_message(
        ticket_id="ticket-1",
        staff_id="staff-1",
        message="  We are investigating.  ",
    )

    assert result == reply
    mocked_supabase["query"].insert.assert_called_once_with(
        {
            "ticket_id": "ticket-1",
            "sender_id": "staff-1",
            "sender_type": "staff",
            "message": "We are investigating.",
        }
    )


@pytest.mark.parametrize(
    ("ticket_id", "staff_id", "message"),
    [
        ("", "staff-1", "Hello"),
        ("ticket-1", "", "Hello"),
        ("ticket-1", "staff-1", "   "),
    ],
)
def test_add_staff_reply_rejects_blank_fields(
    mocked_supabase,
    ticket_id,
    staff_id,
    message,
):
    with pytest.raises(ValueError):
        service.add_staff_ticket_message(
            ticket_id=ticket_id,
            staff_id=staff_id,
            message=message,
        )

    mocked_supabase["client"].table.assert_not_called()


def test_add_staff_reply_does_not_claim_success_without_inserted_row(
    mocked_supabase,
):
    mocked_supabase["query"].insert.return_value = mocked_supabase["query"]
    mocked_supabase["query"].execute.return_value = SimpleNamespace(data=[])

    with pytest.raises(
        service.SupportAdminServiceError,
        match="reply was not returned",
    ):
        service.add_staff_ticket_message(
            ticket_id="ticket-1",
            staff_id="staff-1",
            message="We are investigating.",
        )
