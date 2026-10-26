import os

import pytest
from dotenv import load_dotenv

from app.core.supabase_client import (
    supabase_admin,
)
from app.services import (
    notification_service,
)
from app.services.notification_service import (
    count_unread,
    list_notifications,
    mark_read,
)
from app.workers import (
    notification_worker,
)


load_dotenv()


CUSTOMER_ID = os.getenv(
    "TEST_CUSTOMER_ID"
)


# ============================================================================
# Worker unit tests
# ============================================================================


def test_worker_marks_sent_and_failed_independently(
    monkeypatch,
):
    completed = []
    failed = []


    deliveries = [
        {
            "id":
                "d1",

            "notification_id":
                "n1",

            "channel":
                "in_app",
        },
        {
            "id":
                "d2",

            "notification_id":
                "n2",

            "channel":
                "email",
        },
        {
            "id":
                "d3",

            "notification_id":
                "n3",

            "channel":
                "in_app",
        },
    ]


    def fake_deliver(
        delivery,
    ):
        if (
            delivery[
                "id"
            ]
            ==
            "d2"
        ):
            raise RuntimeError(
                "smtp down"
            )


    monkeypatch.setattr(
        notification_worker,
        "claim_deliveries",
        lambda:
            deliveries,
    )


    monkeypatch.setattr(
        notification_worker,
        "deliver",
        fake_deliver,
    )


    monkeypatch.setattr(
        notification_worker,
        "complete_delivery",
        completed.append,
    )


    monkeypatch.setattr(
        notification_worker,
        "fail_delivery",
        (
            lambda
            delivery_id,
            error:
                failed.append(
                    (
                        delivery_id,
                        error,
                    )
                )
        ),
    )


    summary = (
        notification_worker
        .process_pending_deliveries()
    )


    assert (
        summary
        ==
        {
            "claimed":
                3,

            "sent":
                2,

            "failed":
                1,

            "dead_lettered":
                0,
        }
    )


    assert (
        completed
        ==
        [
            "d1",
            "d3",
        ]
    )


    assert (
        failed
        ==
        [
            (
                "d2",
                "smtp down",
            ),
        ]
    )


def test_worker_survives_claim_failure(
    monkeypatch,
):
    def boom():
        raise RuntimeError(
            "db unreachable"
        )


    monkeypatch.setattr(
        notification_worker,
        "claim_deliveries",
        boom,
    )


    assert (
        notification_worker
        .process_pending_deliveries()
        ==
        {
            "claimed":
                0,

            "sent":
                0,

            "failed":
                0,

            "dead_lettered":
                0,
        }
    )


def test_worker_dead_letters_final_attempt(
    monkeypatch,
):
    dead_lettered = []
    failed = []


    deliveries = [
        {
            "id":
                "d-final",

            "notification_id":
                "n-final",

            "channel":
                "email",

            "attempts":
                (
                    notification_worker
                    .settings
                    .notification_max_attempts
                ),
        },
    ]


    monkeypatch.setattr(
        notification_worker,
        "claim_deliveries",
        lambda:
            deliveries,
    )


    def fail_delivery_attempt(
        delivery,
    ):
        raise RuntimeError(
            "permanent delivery failure"
        )


    monkeypatch.setattr(
        notification_worker,
        "deliver",
        fail_delivery_attempt,
    )


    monkeypatch.setattr(
        notification_worker,
        "dead_letter_delivery",
        (
            lambda
            delivery_id,
            error:
                dead_lettered.append(
                    (
                        delivery_id,
                        error,
                    )
                )
        ),
    )


    monkeypatch.setattr(
        notification_worker,
        "fail_delivery",
        (
            lambda
            delivery_id,
            error:
                failed.append(
                    (
                        delivery_id,
                        error,
                    )
                )
        ),
    )


    summary = (
        notification_worker
        .process_pending_deliveries()
    )


    assert (
        summary
        ==
        {
            "claimed":
                1,

            "sent":
                0,

            "failed":
                0,

            "dead_lettered":
                1,
        }
    )


    assert (
        dead_lettered
        ==
        [
            (
                "d-final",
                (
                    "permanent "
                    "delivery failure"
                ),
            ),
        ]
    )


    assert (
        failed
        == []
    )


def test_email_without_opt_in_is_skipped_not_sent(
    monkeypatch,
):
    sent = []


    monkeypatch.setattr(
        notification_service,
        "_get_notification",
        lambda _id:
            {
                "id":
                    "n1",

                "customer_id":
                    "c1",

                "title":
                    "t",

                "message":
                    "m",
            },
    )


    monkeypatch.setattr(
        notification_service,
        "_email_allowed",
        lambda _c:
            False,
    )


    monkeypatch.setattr(
        notification_service,
        "send_email",
        (
            lambda *args:
                sent.append(
                    args
                )
        ),
    )


    notification_service.deliver(
        {
            "id":
                "d1",

            "notification_id":
                "n1",

            "channel":
                "email",
        }
    )


    assert (
        sent
        == []
    )


def test_email_with_opt_in_is_sent(
    monkeypatch,
):
    sent = []


    monkeypatch.setattr(
        notification_service,
        "_get_notification",
        lambda _id:
            {
                "id":
                    "n1",

                "customer_id":
                    "c1",

                "title":
                    "Price drop",

                "message":
                    "Now Rs. 2500",
            },
    )


    monkeypatch.setattr(
        notification_service,
        "_email_allowed",
        lambda _c:
            True,
    )


    monkeypatch.setattr(
        notification_service,
        "_get_customer_email",
        lambda _c:
            "a@b.co",
    )


    monkeypatch.setattr(
        notification_service,
        "send_email",
        (
            lambda *args:
                sent.append(
                    args
                )
        ),
    )


    notification_service.deliver(
        {
            "id":
                "d1",

            "notification_id":
                "n1",

            "channel":
                "email",
        }
    )


    assert (
        sent
        ==
        [
            (
                "a@b.co",
                "Price drop",
                "Now Rs. 2500",
            ),
        ]
    )


def test_email_without_address_raises_for_retry(
    monkeypatch,
):
    monkeypatch.setattr(
        notification_service,
        "_get_notification",
        lambda _id:
            {
                "id":
                    "n1",

                "customer_id":
                    "c1",

                "title":
                    "t",

                "message":
                    "m",
            },
    )


    monkeypatch.setattr(
        notification_service,
        "_email_allowed",
        lambda _c:
            True,
    )


    monkeypatch.setattr(
        notification_service,
        "_get_customer_email",
        lambda _c:
            None,
    )


    with pytest.raises(
        ValueError
    ):
        notification_service.deliver(
            {
                "id":
                    "d1",

                "notification_id":
                    "n1",

                "channel":
                    "email",
            }
        )


# ============================================================================
# Integration helpers
# ============================================================================


def _get_email_preference_state():
    response = (
        supabase_admin
        .table(
            "customer_preferences"
        )
        .select(
            "allow_email_notifications"
        )
        .eq(
            "customer_id",
            CUSTOMER_ID,
        )
        .limit(
            1
        )
        .execute()
    )


    if (
        not response.data
    ):
        return (
            False,
            False,
        )


    return (
        True,

        bool(
            response.data[
                0
            ][
                "allow_email_notifications"
            ]
        ),
    )


def _set_email_preference(
    enabled: bool,
):
    response = (
        supabase_admin
        .table(
            "customer_preferences"
        )
        .select(
            "customer_id"
        )
        .eq(
            "customer_id",
            CUSTOMER_ID,
        )
        .limit(
            1
        )
        .execute()
    )


    if (
        response.data
    ):
        (
            supabase_admin
            .table(
                "customer_preferences"
            )
            .update(
                {
                    "allow_email_notifications":
                        enabled,
                }
            )
            .eq(
                "customer_id",
                CUSTOMER_ID,
            )
            .execute()
        )

    else:
        (
            supabase_admin
            .table(
                "customer_preferences"
            )
            .insert(
                {
                    "customer_id":
                        CUSTOMER_ID,

                    "allow_email_notifications":
                        enabled,
                }
            )
            .execute()
        )


def _restore_email_preference(
    existed: bool,
    original_value: bool,
):
    if (
        existed
    ):
        (
            supabase_admin
            .table(
                "customer_preferences"
            )
            .update(
                {
                    "allow_email_notifications":
                        original_value,
                }
            )
            .eq(
                "customer_id",
                CUSTOMER_ID,
            )
            .execute()
        )

    else:
        (
            supabase_admin
            .table(
                "customer_preferences"
            )
            .delete()
            .eq(
                "customer_id",
                CUSTOMER_ID,
            )
            .execute()
        )


# ============================================================================
# Integration tests
# ============================================================================


def test_notification_end_to_end():
    assert (
        CUSTOMER_ID
    ), (
        "TEST_CUSTOMER_ID is missing "
        "from backend/.env"
    )


    unread_before = (
        count_unread(
            CUSTOMER_ID
        )
    )


    notification_id = (
        supabase_admin
        .rpc(
            "create_notification",
            {
                "p_customer_id":
                    CUSTOMER_ID,

                "p_type":
                    "general",

                "p_title":
                    "Phase 10 test",

                "p_message":
                    (
                        "Integration test "
                        "notification"
                    ),

                "p_metadata":
                    {},

                "p_email":
                    False,
            },
        )
        .execute()
        .data
    )


    try:
        assert (
            count_unread(
                CUSTOMER_ID
            )
            ==
            unread_before + 1
        )


        listed = (
            list_notifications(
                CUSTOMER_ID
            )
        )


        assert any(
            (
                notification[
                    "id"
                ]
                ==
                notification_id
            )
            for notification
            in listed[
                "notifications"
            ]
        )


        delivery = (
            supabase_admin
            .table(
                "notification_deliveries"
            )
            .select(
                (
                    "id, status, "
                    "attempts"
                )
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


        assert (
            delivery[
                "status"
            ]
            ==
            "pending"
        )


        assert (
            delivery[
                "attempts"
            ]
            == 0
        )


        # Older queued rows may exist, so drain
        # multiple batches until this row is sent.
        for _ in range(
            10
        ):
            (
                notification_worker
                .process_pending_deliveries()
            )


            delivery = (
                supabase_admin
                .table(
                    "notification_deliveries"
                )
                .select(
                    (
                        "status, "
                        "attempts"
                    )
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


            if (
                delivery[
                    "status"
                ]
                ==
                "sent"
            ):
                break


        assert (
            delivery[
                "status"
            ]
            ==
            "sent"
        )


        assert (
            delivery[
                "attempts"
            ]
            == 1
        )


        result = (
            mark_read(
                CUSTOMER_ID,
                [
                    notification_id,
                ],
            )
        )


        assert (
            result[
                "updated"
            ]
            == 1
        )


        assert (
            count_unread(
                CUSTOMER_ID
            )
            ==
            unread_before
        )


    finally:
        (
            supabase_admin
            .table(
                "notifications"
            )
            .delete()
            .eq(
                "id",
                notification_id,
            )
            .execute()
        )


def test_commerce_notification_queues_email_when_opted_in():
    assert (
        CUSTOMER_ID
    ), (
        "TEST_CUSTOMER_ID is missing "
        "from backend/.env"
    )


    (
        existed,
        original_value,
    ) = (
        _get_email_preference_state()
    )


    notification_id = (
        None
    )


    try:
        _set_email_preference(
            True
        )


        notification_id = (
            supabase_admin
            .rpc(
                "create_notification",
                {
                    "p_customer_id":
                        CUSTOMER_ID,

                    "p_type":
                        "price_drop",

                    "p_title":
                        (
                            "Phase 10 email "
                            "queue test"
                        ),

                    "p_message":
                        (
                            "Opted-in customer "
                            "should get email "
                            "queue row"
                        ),

                    "p_metadata": {
                        "test":
                            True,
                    },

                    # The DB should automatically
                    # queue email for an opted-in
                    # commerce notification.
                    "p_email":
                        False,
                },
            )
            .execute()
            .data
        )


        response = (
            supabase_admin
            .table(
                "notification_deliveries"
            )
            .select(
                (
                    "channel, status, "
                    "attempts"
                )
            )
            .eq(
                "notification_id",
                notification_id,
            )
            .execute()
        )


        deliveries = (
            response.data
            or []
        )


        channels = {
            row[
                "channel"
            ]
            for row
            in deliveries
        }


        assert (
            channels
            ==
            {
                "in_app",
                "email",
            }
        )


        by_channel = {
            row[
                "channel"
            ]:
                row
            for row
            in deliveries
        }


        assert (
            by_channel[
                "in_app"
            ][
                "status"
            ]
            ==
            "pending"
        )


        assert (
            by_channel[
                "email"
            ][
                "status"
            ]
            ==
            "pending"
        )


        assert (
            by_channel[
                "in_app"
            ][
                "attempts"
            ]
            == 0
        )


        assert (
            by_channel[
                "email"
            ][
                "attempts"
            ]
            == 0
        )


    finally:
        if (
            notification_id
        ):
            (
                supabase_admin
                .table(
                    "notifications"
                )
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
    assert (
        CUSTOMER_ID
    ), (
        "TEST_CUSTOMER_ID is missing "
        "from backend/.env"
    )


    (
        existed,
        original_value,
    ) = (
        _get_email_preference_state()
    )


    notification_id = (
        None
    )


    try:
        _set_email_preference(
            False
        )


        notification_id = (
            supabase_admin
            .rpc(
                "create_notification",
                {
                    "p_customer_id":
                        CUSTOMER_ID,

                    "p_type":
                        "smart_cart_match",

                    "p_title":
                        (
                            "Phase 10 "
                            "opt-out test"
                        ),

                    "p_message":
                        (
                            "Opted-out customer "
                            "should not get email"
                        ),

                    "p_metadata": {
                        "test":
                            True,
                    },

                    "p_email":
                        False,
                },
            )
            .execute()
            .data
        )


        response = (
            supabase_admin
            .table(
                "notification_deliveries"
            )
            .select(
                (
                    "channel, status, "
                    "attempts"
                )
            )
            .eq(
                "notification_id",
                notification_id,
            )
            .execute()
        )


        deliveries = (
            response.data
            or []
        )


        channels = {
            row[
                "channel"
            ]
            for row
            in deliveries
        }


        assert (
            channels
            ==
            {
                "in_app",
            }
        )


        assert (
            len(
                deliveries
            )
            == 1
        )


        assert (
            deliveries[
                0
            ][
                "status"
            ]
            ==
            "pending"
        )


        assert (
            deliveries[
                0
            ][
                "attempts"
            ]
            == 0
        )


    finally:
        if (
            notification_id
        ):
            (
                supabase_admin
                .table(
                    "notifications"
                )
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