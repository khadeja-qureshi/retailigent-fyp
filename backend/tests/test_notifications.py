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
        lambda delivery_id, error, permanent=False: failed.append(
            (delivery_id, error, permanent)
        ),
    )

    summary = notification_worker.process_pending_deliveries()

    assert summary == {"sent": 2, "failed": 1, "dead_lettered": 0}
    assert completed == ["d1", "d3"]
    assert failed == [("d2", "smtp down", False)]


def test_worker_dead_letters_permanent_errors_immediately(monkeypatch):
    failed = []

    def fake_deliver(delivery):
        if delivery["id"] == "d1":
            raise notification_service.PermanentDeliveryError(
                "Customer has no email address"
            )

    monkeypatch.setattr(
        notification_worker,
        "claim_deliveries",
        lambda: [
            {"id": "d1", "notification_id": "n1", "channel": "email"},
            {"id": "d2", "notification_id": "n2", "channel": "in_app"},
        ],
    )
    monkeypatch.setattr(notification_worker, "deliver", fake_deliver)
    monkeypatch.setattr(notification_worker, "complete_delivery", lambda _id: None)
    monkeypatch.setattr(
        notification_worker,
        "fail_delivery",
        lambda delivery_id, error, permanent=False: failed.append(
            (delivery_id, error, permanent)
        ),
    )

    summary = notification_worker.process_pending_deliveries()

    assert summary == {"sent": 1, "failed": 1, "dead_lettered": 1}
    assert failed == [("d1", "Customer has no email address", True)]


def test_worker_survives_failure_to_record_failure(monkeypatch):
    monkeypatch.setattr(
        notification_worker,
        "claim_deliveries",
        lambda: [{"id": "d1", "notification_id": "n1", "channel": "in_app"}],
    )
    monkeypatch.setattr(
        notification_worker,
        "deliver",
        lambda _d: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    def broken_fail(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(notification_worker, "fail_delivery", broken_fail)

    summary = notification_worker.process_pending_deliveries()

    assert summary["failed"] == 1


def test_claim_failure_propagates_so_the_scheduler_can_record_it(monkeypatch):
    def boom():
        raise RuntimeError("db unreachable")

    monkeypatch.setattr(notification_worker, "claim_deliveries", boom)

    with pytest.raises(RuntimeError):
        notification_worker.process_pending_deliveries()


def test_fail_delivery_sends_permanence_and_attempt_limit(monkeypatch):
    calls = []

    class FakeRpc:
        def execute(self):
            return None

    class FakeClient:
        def rpc(self, name, params):
            calls.append((name, params))
            return FakeRpc()

    monkeypatch.setattr(notification_service, "supabase_admin", FakeClient())
    monkeypatch.setattr(
        notification_service.settings, "notification_max_attempts", 4
    )

    notification_service.fail_delivery("d1", "boom", permanent=True)

    assert calls == [
        (
            "fail_notification_delivery",
            {
                "p_delivery_id": "d1",
                "p_error": "boom",
                "p_permanent": True,
                "p_max_attempts": 4,
            },
        )
    ]


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
        # ---------------------------------------------------------------
        # 1. Notification was created and appears as unread
        # ---------------------------------------------------------------
        assert count_unread(CUSTOMER_ID) == unread_before + 1

        listed = list_notifications(CUSTOMER_ID)

        assert any(
            notification["id"] == notification_id
            for notification in listed["notifications"]
        )

        # ---------------------------------------------------------------
        # 2. Confirm its in-app delivery was queued
        # ---------------------------------------------------------------
        delivery = (
            supabase_admin
            .table("notification_deliveries")
            .select(
                "id, status, attempts"
            )
            .eq(
                "notification_id",
                notification_id,
            )
            .eq(
                "channel",
                "in_app",
            )
            .single()
            .execute()
            .data
        )

        assert delivery["status"] == "pending"
        assert delivery["attempts"] == 0

        # ---------------------------------------------------------------
        # 3. Drain worker batches until THIS delivery is processed.
        #
        # The database may already contain older pending deliveries.
        # claim_notification_deliveries() intentionally processes the
        # oldest rows first, so one worker call is not guaranteed to
        # reach the notification created by this test.
        # ---------------------------------------------------------------
        for _ in range(10):
            notification_worker.process_pending_deliveries()

            delivery = (
                supabase_admin
                .table("notification_deliveries")
                .select(
                    "status, attempts"
                )
                .eq(
                    "notification_id",
                    notification_id,
                )
                .eq(
                    "channel",
                    "in_app",
                )
                .single()
                .execute()
                .data
            )

            if delivery["status"] == "sent":
                break

        assert delivery["status"] == "sent"
        assert delivery["attempts"] == 1

        # ---------------------------------------------------------------
        # 4. Mark it read
        # ---------------------------------------------------------------
        result = mark_read(
            CUSTOMER_ID,
            [notification_id],
        )

        assert result["updated"] == 1
        assert count_unread(CUSTOMER_ID) == unread_before

    finally:
        # notification_deliveries rows are deleted automatically because
        # they reference notifications(id) ON DELETE CASCADE.
        (
            supabase_admin
            .table("notifications")
            .delete()
            .eq(
                "id",
                notification_id,
            )
            .execute()
        )

def _get_email_preference_state():
    response = (
        supabase_admin
        .table("customer_preferences")
        .select("allow_email_notifications")
        .eq("customer_id", CUSTOMER_ID)
        .limit(1)
        .execute()
    )

    if not response.data:
        return False, False

    return (
        True,
        bool(
            response.data[0]["allow_email_notifications"]
        ),
    )


def _set_email_preference(enabled: bool):
    response = (
        supabase_admin
        .table("customer_preferences")
        .select("customer_id")
        .eq("customer_id", CUSTOMER_ID)
        .limit(1)
        .execute()
    )

    if response.data:
        (
            supabase_admin
            .table("customer_preferences")
            .update(
                {
                    "allow_email_notifications": enabled,
                }
            )
            .eq("customer_id", CUSTOMER_ID)
            .execute()
        )
    else:
        (
            supabase_admin
            .table("customer_preferences")
            .insert(
                {
                    "customer_id": CUSTOMER_ID,
                    "allow_email_notifications": enabled,
                }
            )
            .execute()
        )


def _restore_email_preference(
    existed: bool,
    original_value: bool,
):
    if existed:
        (
            supabase_admin
            .table("customer_preferences")
            .update(
                {
                    "allow_email_notifications":
                        original_value,
                }
            )
            .eq("customer_id", CUSTOMER_ID)
            .execute()
        )
    else:
        (
            supabase_admin
            .table("customer_preferences")
            .delete()
            .eq("customer_id", CUSTOMER_ID)
            .execute()
        )


def test_commerce_notification_queues_email_when_opted_in():
    assert CUSTOMER_ID, (
        "TEST_CUSTOMER_ID is missing from backend/.env"
    )

    existed, original_value = (
        _get_email_preference_state()
    )

    notification_id = None

    try:
        _set_email_preference(True)

        notification_id = (
            supabase_admin
            .rpc(
                "create_notification",
                {
                    "p_customer_id": CUSTOMER_ID,
                    "p_type": "price_drop",
                    "p_title": "Phase 10 email queue test",
                    "p_message":
                        "Opted-in customer should get email queue row",
                    "p_metadata": {
                        "test": True,
                    },

                    # Important:
                    # We deliberately keep this False.
                    # The migration should auto-queue email
                    # because price_drop is a commerce event
                    # and the customer opted in.
                    "p_email": False,
                },
            )
            .execute()
            .data
        )

        response = (
            supabase_admin
            .table("notification_deliveries")
            .select("channel, status, attempts")
            .eq(
                "notification_id",
                notification_id,
            )
            .execute()
        )

        deliveries = response.data or []

        channels = {
            row["channel"]
            for row in deliveries
        }

        assert channels == {
            "in_app",
            "email",
        }

        by_channel = {
            row["channel"]: row
            for row in deliveries
        }

        assert (
            by_channel["in_app"]["status"]
            == "pending"
        )

        assert (
            by_channel["email"]["status"]
            == "pending"
        )

        assert (
            by_channel["in_app"]["attempts"]
            == 0
        )

        assert (
            by_channel["email"]["attempts"]
            == 0
        )

    finally:
        if notification_id:
            (
                supabase_admin
                .table("notifications")
                .delete()
                .eq(
                    "id",
                    notification_id,
                )
                .execute()
            )

        _restore_email_preference(
            existed,
            original_value,
        )


def test_commerce_notification_respects_email_opt_out():
    assert CUSTOMER_ID, (
        "TEST_CUSTOMER_ID is missing from backend/.env"
    )

    existed, original_value = (
        _get_email_preference_state()
    )

    notification_id = None

    try:
        _set_email_preference(False)

        notification_id = (
            supabase_admin
            .rpc(
                "create_notification",
                {
                    "p_customer_id": CUSTOMER_ID,
                    "p_type": "smart_cart_match",
                    "p_title": "Phase 10 opt-out test",
                    "p_message":
                        "Opted-out customer should not get email",
                    "p_metadata": {
                        "test": True,
                    },
                    "p_email": False,
                },
            )
            .execute()
            .data
        )

        response = (
            supabase_admin
            .table("notification_deliveries")
            .select("channel, status, attempts")
            .eq(
                "notification_id",
                notification_id,
            )
            .execute()
        )

        deliveries = response.data or []

        channels = {
            row["channel"]
            for row in deliveries
        }

        assert channels == {
            "in_app",
        }

        assert len(deliveries) == 1

        assert (
            deliveries[0]["status"]
            == "pending"
        )

        assert (
            deliveries[0]["attempts"]
            == 0
        )

    finally:
        if notification_id:
            (
                supabase_admin
                .table("notifications")
                .delete()
                .eq(
                    "id",
                    notification_id,
                )
                .execute()
            )

        _restore_email_preference(
            existed,
            original_value,
        )