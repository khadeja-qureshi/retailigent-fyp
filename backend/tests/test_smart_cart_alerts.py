import os
from decimal import Decimal

import pytest
from dotenv import load_dotenv

from app.agents.purchase_agent import purchase_agent
from app.core.supabase_client import supabase_admin
from app.services.alert_service import (
    cancel_customer_alert,
    create_customer_alert,
    pause_customer_alert,
    resume_customer_alert,
)
from app.services.smart_cart_service import (
    cancel_customer_smart_cart_rule,
    create_customer_smart_cart_rule,
    get_smart_cart_rule_for_system,
    pause_customer_smart_cart_rule,
    resume_customer_smart_cart_rule,
)

load_dotenv()
CUSTOMER_ID = os.getenv("TEST_CUSTOMER_ID")
VARIANT_ID = os.getenv("TEST_VARIANT_ID")


def require_test_environment():
    assert CUSTOMER_ID, (
        "TEST_CUSTOMER_ID is missing from backend/.env"
    )
    assert VARIANT_ID, (
        "TEST_VARIANT_ID is missing from backend/.env"
    )


def find_test_branch(
    min_available: int = 1,
):
    response = (
        supabase_admin
        .table("branch_inventory")
        .select(
            "branch_id, "
            "on_hand_quantity, "
            "reserved_quantity, "
            "available_quantity"
        )
        .eq("variant_id", VARIANT_ID)
        .execute()
    )

    inventory_rows = response.data or []

    assert inventory_rows, (
        "No inventory rows found for TEST_VARIANT_ID"
    )

    branch_ids = [
        row["branch_id"]
        for row in inventory_rows
    ]

    branch_response = (
        supabase_admin
        .table("branches")
        .select("id, name, is_active")
        .in_("id", branch_ids)
        .eq("is_active", True)
        .execute()
    )

    active_ids = {
        row["id"]
        for row in (
            branch_response.data or []
        )
    }

    candidates = [
        row
        for row in inventory_rows
        if (
            row["branch_id"]
            in active_ids
            and
            int(
                row[
                    "available_quantity"
                ]
            )
            >= min_available
        )
    ]

    assert candidates, (
        "No active branch has enough "
        "available inventory for the test."
    )

    return max(
        candidates,
        key=lambda row: int(
            row["available_quantity"]
        ),
    )


def inventory_snapshot(
    branch_id: str,
):
    response = (
        supabase_admin
        .table("branch_inventory")
        .select(
            "branch_id, "
            "variant_id, "
            "on_hand_quantity, "
            "reserved_quantity, "
            "available_quantity"
        )
        .eq(
            "variant_id",
            VARIANT_ID,
        )
        .eq(
            "branch_id",
            branch_id,
        )
        .single()
        .execute()
    )

    return response.data


def get_raw_variant_price():
    response = (
        supabase_admin
        .table("product_variants")
        .select("price")
        .eq("id", VARIANT_ID)
        .single()
        .execute()
    )

    return response.data["price"]


def get_effective_price():
    response = (
        supabase_admin
        .rpc(
            "get_effective_variant_price",
            {
                "p_variant_id":
                    VARIANT_ID,
            },
        )
        .execute()
    )

    assert response.data is not None

    return Decimal(
        str(response.data)
    )


def set_variant_price(
    price,
):
    (
        supabase_admin
        .table("product_variants")
        .update({
            "price": price,
        })
        .eq("id", VARIANT_ID)
        .execute()
    )


def get_rule(
    rule_id: str,
):
    response = (
        supabase_admin
        .table("smart_cart_rules")
        .select("*")
        .eq("id", rule_id)
        .single()
        .execute()
    )

    return response.data


def get_alert(
    alert_id: str,
):
    response = (
        supabase_admin
        .table("alerts")
        .select("*")
        .eq("id", alert_id)
        .single()
        .execute()
    )

    return response.data


def delete_test_rule(
    rule_id: str,
):
    try:
        (
            supabase_admin
            .table("smart_cart_rules")
            .delete()
            .eq("id", rule_id)
            .execute()
        )
    except Exception:
        # A completed rule may be referenced
        # by purchase_attempts, so preserving it
        # is acceptable test/audit history.
        pass


def test_smart_cart_pause_resume_cancel():
    require_test_environment()

    branch = find_test_branch(
        min_available=1
    )

    rule_id = None

    try:
        rule = (
            create_customer_smart_cart_rule(
                customer_id=CUSTOMER_ID,
                variant_id=VARIANT_ID,
                branch_id=(
                    branch["branch_id"]
                ),
                quantity=1,
                target_price=Decimal(
                    "1.00"
                ),
                authorization_mode=(
                    "notify_only"
                ),
            )
        )

        rule_id = rule["id"]

        assert (
            rule["status"]
            == "active"
        )

        paused = (
            pause_customer_smart_cart_rule(
                customer_id=CUSTOMER_ID,
                rule_id=rule_id,
            )
        )

        assert (
            paused["status"]
            == "paused"
        )

        resumed = (
            resume_customer_smart_cart_rule(
                customer_id=CUSTOMER_ID,
                rule_id=rule_id,
            )
        )

        assert (
            resumed["status"]
            == "active"
        )

        cancelled = (
            cancel_customer_smart_cart_rule(
                customer_id=CUSTOMER_ID,
                rule_id=rule_id,
            )
        )

        assert (
            cancelled["status"]
            == "cancelled"
        )

    finally:
        if rule_id:
            delete_test_rule(
                rule_id
            )


def test_auto_buy_price_event_creates_one_order():
    require_test_environment()

    branch = find_test_branch(
        min_available=1
    )

    branch_id = branch["branch_id"]

    inventory_before = (
        inventory_snapshot(
            branch_id
        )
    )

    original_raw_price = (
        get_raw_variant_price()
    )

    original_effective_price = (
        get_effective_price()
    )

    assert (
        original_effective_price
        > Decimal("10")
    ), (
        "Test variant effective price "
        "must be greater than Rs 10."
    )

    target_price = (
        original_effective_price
        * Decimal("0.80")
    ).quantize(
        Decimal("0.01")
    )

    trigger_raw_price = max(
        Decimal("1.00"),
        target_price
        * Decimal("0.50"),
    ).quantize(
        Decimal("0.01")
    )

    rule_id = None

    try:
        rule = (
            create_customer_smart_cart_rule(
                customer_id=CUSTOMER_ID,
                variant_id=VARIANT_ID,
                branch_id=branch_id,
                quantity=1,
                target_price=(
                    target_price
                ),
                authorization_mode=(
                    "auto_buy"
                ),
            )
        )

        rule_id = rule["id"]

        assert (
            rule["status"]
            == "active"
        )

        # This DB update emits a price_changed
        # retail event automatically.
        set_variant_price(
            float(trigger_raw_price)
        )

        rule_after_event = (
            get_smart_cart_rule_for_system(
                rule_id
            )
        )

        # If the FastAPI background worker
        # is already running in another
        # process, the rule may already be
        # completed.
        assert (
            rule_after_event["status"]
            in {
                "triggered",
                "completed",
            }
        )

        if (
            rule_after_event["status"]
            == "triggered"
        ):
            result = (
                purchase_agent
                .process_auto_buy_rule(
                    rule_id
                )
            )

            assert (
                result["processed"]
                is True
            )

        final_rule = get_rule(
            rule_id
        )

        assert (
            final_rule["status"]
            == "completed"
        )

        assert (
            final_rule[
                "triggered_at"
            ]
            is not None
        )

        attempts_response = (
            supabase_admin
            .table(
                "purchase_attempts"
            )
            .select(
                "id, status, "
                "idempotency_key, "
                "order_id, "
                "smart_cart_rule_id"
            )
            .eq(
                "smart_cart_rule_id",
                rule_id,
            )
            .execute()
        )

        attempts = (
            attempts_response.data
            or []
        )

        assert len(attempts) == 1

        attempt = attempts[0]

        assert (
            attempt["status"]
            == "completed"
        )

        assert (
            attempt["order_id"]
            is not None
        )

        assert (
            attempt[
                "idempotency_key"
            ]
            ==
            f"smart-cart:{rule_id}"
        )

        inventory_after = (
            inventory_snapshot(
                branch_id
            )
        )

        assert (
            inventory_after[
                "on_hand_quantity"
            ]
            ==
            inventory_before[
                "on_hand_quantity"
            ] - 1
        )

        assert (
            inventory_after[
                "reserved_quantity"
            ]
            ==
            inventory_before[
                "reserved_quantity"
            ]
        )

        assert (
            inventory_after[
                "available_quantity"
            ]
            ==
            inventory_before[
                "available_quantity"
            ] - 1
        )

        # Running the same completed rule
        # again must NOT make another order.
        second_result = (
            purchase_agent
            .process_auto_buy_rule(
                rule_id
            )
        )

        assert (
            second_result[
                "processed"
            ]
            is False
        )

        attempts_again = (
            supabase_admin
            .table(
                "purchase_attempts"
            )
            .select("id")
            .eq(
                "smart_cart_rule_id",
                rule_id,
            )
            .execute()
        )

        assert len(
            attempts_again.data
            or []
        ) == 1

    finally:
        set_variant_price(
            original_raw_price
        )


def test_price_drop_alert_triggers_once():
    require_test_environment()

    original_raw_price = (
        get_raw_variant_price()
    )

    effective_price = (
        get_effective_price()
    )

    assert (
        effective_price
        > Decimal("10")
    )

    target_price = (
        effective_price
        * Decimal("0.80")
    ).quantize(
        Decimal("0.01")
    )

    trigger_price = max(
        Decimal("1.00"),
        target_price
        * Decimal("0.50"),
    ).quantize(
        Decimal("0.01")
    )

    alert_id = None

    try:
        alert = (
            create_customer_alert(
                customer_id=CUSTOMER_ID,
                variant_id=VARIANT_ID,
                alert_type="price_drop",
                target_price=(
                    target_price
                ),
            )
        )

        alert_id = alert["id"]

        assert (
            alert["is_active"]
            is True
        )

        assert (
            alert["triggered_at"]
            is None
        )

        set_variant_price(
            float(trigger_price)
        )

        triggered = get_alert(
            alert_id
        )

        assert (
            triggered["is_active"]
            is False
        )

        assert (
            triggered[
                "triggered_at"
            ]
            is not None
        )

        first_triggered_at = (
            triggered[
                "triggered_at"
            ]
        )

        # Generate another price event.
        second_price = max(
            Decimal("0.50"),
            trigger_price
            - Decimal("0.50"),
        )

        if (
            second_price
            == trigger_price
        ):
            second_price = (
                trigger_price
                + Decimal("0.50")
            )

        set_variant_price(
            float(second_price)
        )

        after_second_event = (
            get_alert(
                alert_id
            )
        )

        # One-shot behavior:
        # it must remain triggered once.
        assert (
            after_second_event[
                "is_active"
            ]
            is False
        )

        assert (
            after_second_event[
                "triggered_at"
            ]
            ==
            first_triggered_at
        )

    finally:
        set_variant_price(
            original_raw_price
        )

        if alert_id:
            try:
                (
                    supabase_admin
                    .table("alerts")
                    .delete()
                    .eq(
                        "id",
                        alert_id,
                    )
                    .execute()
                )
            except Exception:
                pass


def test_alert_pause_resume_delete():
    require_test_environment()

    alert_id = None

    alert = (
        create_customer_alert(
            customer_id=CUSTOMER_ID,
            variant_id=VARIANT_ID,
            alert_type="restock",
        )
    )

    alert_id = alert["id"]

    assert (
        alert["is_active"]
        is True
    )

    paused = (
        pause_customer_alert(
            customer_id=CUSTOMER_ID,
            alert_id=alert_id,
        )
    )

    assert (
        paused["is_active"]
        is False
    )

    resumed = (
        resume_customer_alert(
            customer_id=CUSTOMER_ID,
            alert_id=alert_id,
        )
    )

    assert (
        resumed["is_active"]
        is True
    )

    deleted = (
        cancel_customer_alert(
            customer_id=CUSTOMER_ID,
            alert_id=alert_id,
        )
    )

    assert (
        deleted["deleted"]
        is True
    )

    response = (
        supabase_admin
        .table("alerts")
        .select("id")
        .eq(
            "id",
            alert_id,
        )
        .execute()
    )

    assert not response.data