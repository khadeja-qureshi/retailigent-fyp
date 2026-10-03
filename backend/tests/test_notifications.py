import os

import pytest
from dotenv import load_dotenv

from app.core.supabase_client import supabase_admin
from app.services import notification_service
from app.services.notification_service import (
    count_unread,
    list_notifications,
    mark_read,
)
from app.workers import notification_worker


load_dotenv()
CUSTOMER_ID = os.getenv("TEST_CUSTOMER_ID")


# ---------------------------------------------------------------------------
# Worker unit tests (no database)
# ---------------------------------------------------------------------------

def test_worker_marks_sent_and_failed_independently(monkeypatch):
    completed, failed = [], []

    deliveries = [
        {"id": "d1", "notification_id": "n1", "channel": "in_app"},
        {"id": "d2", "notification_id": "n2", "channel": "email"},
        {"id": "d3", "notification_id": "n3", "channel": "in_app"},
    ]

    def fake_deliver(delivery):
        if delivery["id"] == "d2":
            raise RuntimeError("smtp down")

    monkeypatch.setattr(
        notification_worker, "claim_deliveries", lambda: deliveries
    )
    monkeypatch.setattr(notification_worker, "deliver", fake_deliver)
    monkeypatch.setattr(
        notification_worker, "complete_delivery", completed.append
    )
    monkeypatch.setattr(
        notification_worker,
        "fail_delivery",
        lambda delivery_id, error: failed.append((delivery_id, error)),
    )

    summary = notification_worker.process_pending_deliveries()

    assert summary == {"sent": 2, "failed": 1}
    assert completed == ["d1", "d3"]
    assert failed == [("d2", "smtp down")]


def test_worker_survives_claim_failure(monkeypatch):
    def boom():
        raise RuntimeError("db unreachable")

    monkeypatch.setattr(notification_worker, "claim_deliveries", boom)

    assert notification_worker.process_pending_deliveries() == {
        "sent": 0,
        "failed": 0,
    }


def test_email_without_opt_in_is_skipped_not_sent(monkeypatch):
    sent = []

    monkeypatch.setattr(
        notification_service,
        "_get_notification",
        lambda _id: {
            "id": "n1",
            "customer_id": "c1",
            "title": "t",
            "message": "m",
        },
    )
    monkeypatch.setattr(
        notification_service, "_email_allowed", lambda _c: False
    )
    monkeypatch.setattr(
        notification_service,
        "send_email",
        lambda *args: sent.append(args),
    )

    notification_service.deliver(
        {"id": "d1", "notification_id": "n1", "channel": "email"}
    )

    assert sent == []


def test_email_with_opt_in_is_sent(monkeypatch):
    sent = []

    monkeypatch.setattr(
        notification_service,
        "_get_notification",
        lambda _id: {
            "id": "n1",
            "customer_id": "c1",
            "title": "Price drop",
            "message": "Now Rs. 2500",
        },
    )
    monkeypatch.setattr(
        notification_service, "_email_allowed", lambda _c: True
    )
    monkeypatch.setattr(
        notification_service, "_get_customer_email", lambda _c: "a@b.co"
    )
    monkeypatch.setattr(
        notification_service,
        "send_email",
        lambda *args: sent.append(args),
    )

    notification_service.deliver(
        {"id": "d1", "notification_id": "n1", "channel": "email"}
    )

    assert sent == [("a@b.co", "Price drop", "Now Rs. 2500")]


def test_email_without_address_raises_for_retry(monkeypatch):
    monkeypatch.setattr(
        notification_service,
        "_get_notification",
        lambda _id: {
            "id": "n1",
            "customer_id": "c1",
            "title": "t",
            "message": "m",
        },
    )
    monkeypatch.setattr(
        notification_service, "_email_allowed", lambda _c: True
    )
    monkeypatch.setattr(
        notification_service, "_get_customer_email", lambda _c: None
    )

    with pytest.raises(ValueError):
        notification_service.deliver(
            {"id": "d1", "notification_id": "n1", "channel": "email"}
        )


# ---------------------------------------------------------------------------
# Integration test (requires TEST_CUSTOMER_ID in backend/.env and the
# phase 10 migration applied)
# ---------------------------------------------------------------------------

def test_notification_end_to_end():
    assert CUSTOMER_ID, "TEST_CUSTOMER_ID is missing from backend/.env"

    unread_before = count_unread(CUSTOMER_ID)

    notification_id = (
        supabase_admin
        .rpc(
            "create_notification",
            {
                "p_customer_id": CUSTOMER_ID,
                "p_type": "general",
                "p_title": "Phase 10 test",
                "p_message": "Integration test notification",
                "p_metadata": {},
                "p_email": False,
            },
        )
        .execute()
        .data
    )

    try:
        assert count_unread(CUSTOMER_ID) == unread_before + 1

        listed = list_notifications(CUSTOMER_ID)
        assert any(
            n["id"] == notification_id for n in listed["notifications"]
        )

        # in_app delivery is queued, then drained by the worker
        notification_worker.process_pending_deliveries()

        delivery = (
            supabase_admin
            .table("notification_deliveries")
            .select("status, attempts")
            .eq("notification_id", notification_id)
            .eq("channel", "in_app")
            .single()
            .execute()
            .data
        )
        assert delivery["status"] == "sent"
        assert delivery["attempts"] == 1

        result = mark_read(CUSTOMER_ID, [notification_id])
        assert result["updated"] == 1
        assert count_unread(CUSTOMER_ID) == unread_before

    finally:
        (
            supabase_admin
            .table("notifications")
            .delete()
            .eq("id", notification_id)
            .execute()
        )
