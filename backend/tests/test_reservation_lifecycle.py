import os
import time
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from dotenv import load_dotenv
from fastapi import HTTPException

from app.core.supabase_client import (
    supabase_admin,
)
from app.services.reservation_service import (
    create_customer_reservation,
    release_customer_reservation,
    release_expired_reservations,
)


load_dotenv()


CUSTOMER_ID = os.getenv(
    "TEST_CUSTOMER_ID"
)

VARIANT_ID = os.getenv(
    "TEST_VARIANT_ID"
)


def get_active_test_branch(
    min_available: int = 1,
):
    inventory_response = (
        supabase_admin
        .table("branch_inventory")
        .select(
            "branch_id, "
            "available_quantity"
        )
        .eq(
            "variant_id",
            VARIANT_ID,
        )
        .execute()
    )

    inventory = (
        inventory_response.data
        or []
    )

    branch_ids = [
        row["branch_id"]
        for row in inventory
    ]

    assert branch_ids, (
        "No branch inventory found "
        "for TEST_VARIANT_ID"
    )

    branch_response = (
        supabase_admin
        .table("branches")
        .select(
            "id, is_active"
        )
        .in_(
            "id",
            branch_ids,
        )
        .eq(
            "is_active",
            True,
        )
        .execute()
    )

    active_ids = {
        row["id"]
        for row in (
            branch_response.data
            or []
        )
    }

    candidates = [
        row
        for row in inventory
        if (
            row["branch_id"]
            in active_ids
            and int(
                row[
                    "available_quantity"
                ]
            )
            >= min_available
        )
    ]

    assert candidates, (
        "No active branch has "
        f"{min_available} units "
        "available."
    )

    return max(
        candidates,
        key=lambda row: int(
            row[
                "available_quantity"
            ]
        ),
    )


def get_inventory_snapshot(
    branch_id: str,
):
    response = (
        supabase_admin
        .table("branch_inventory")
        .select(
            "branch_id, variant_id, "
            "on_hand_quantity, "
            "reserved_quantity, "
            "safety_stock, "
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
        .limit(1)
        .execute()
    )

    assert response.data, (
        "Inventory row not found."
    )

    return response.data[0]


def get_reservation(
    reservation_id: str,
):
    response = (
        supabase_admin
        .table("reservations")
        .select(
            "id, status"
        )
        .eq(
            "id",
            reservation_id,
        )
        .limit(1)
        .execute()
    )

    assert response.data

    return response.data[0]


def cleanup_reservation(
    reservation_id: str | None,
):
    if not reservation_id:
        return

    reservation = get_reservation(
        reservation_id
    )

    if reservation["status"] == "active":
        release_customer_reservation(
            customer_id=CUSTOMER_ID,
            reservation_id=reservation_id,
        )


def test_reservation_books_and_releases_stock():
    assert CUSTOMER_ID, (
        "TEST_CUSTOMER_ID missing"
    )
    assert VARIANT_ID, (
        "TEST_VARIANT_ID missing"
    )

    branch = get_active_test_branch(
        min_available=2
    )

    branch_id = branch["branch_id"]

    before = get_inventory_snapshot(
        branch_id
    )

    reservation_id = None

    try:
        reservation = (
            create_customer_reservation(
                customer_id=CUSTOMER_ID,
                variant_id=VARIANT_ID,
                branch_id=branch_id,
                quantity=2,
                hold_minutes=15,
            )
        )

        reservation_id = (
            reservation["id"]
        )

        after_create = (
            get_inventory_snapshot(
                branch_id
            )
        )

        assert (
            after_create[
                "on_hand_quantity"
            ]
            ==
            before[
                "on_hand_quantity"
            ]
        )

        assert (
            after_create[
                "reserved_quantity"
            ]
            ==
            before[
                "reserved_quantity"
            ]
            + 2
        )

        assert (
            after_create[
                "available_quantity"
            ]
            ==
            before[
                "available_quantity"
            ]
            - 2
        )

        release_customer_reservation(
            customer_id=CUSTOMER_ID,
            reservation_id=(
                reservation_id
            ),
        )

        final = get_inventory_snapshot(
            branch_id
        )

        assert final == before

    finally:
        cleanup_reservation(
            reservation_id
        )


def test_reservation_rejects_overselling():
    assert CUSTOMER_ID
    assert VARIANT_ID

    branch = get_active_test_branch(
        min_available=1
    )

    branch_id = branch["branch_id"]

    before = get_inventory_snapshot(
        branch_id
    )

    too_many = (
        int(
            before[
                "available_quantity"
            ]
        )
        + 1
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        create_customer_reservation(
            customer_id=CUSTOMER_ID,
            variant_id=VARIANT_ID,
            branch_id=branch_id,
            quantity=too_many,
            hold_minutes=15,
        )

    assert (
        exc_info.value.status_code
        == 409
    )

    after = get_inventory_snapshot(
        branch_id
    )

    assert after == before


def test_expired_reservation_releases_stock():
    assert CUSTOMER_ID
    assert VARIANT_ID

    branch = get_active_test_branch(
        min_available=1
    )

    branch_id = branch["branch_id"]

    before = get_inventory_snapshot(
        branch_id
    )

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(seconds=2)
    )

    reservation_id = None

    try:
        response = (
            supabase_admin
            .rpc(
                "create_reservation",
                {
                    "p_customer_id":
                        CUSTOMER_ID,
                    "p_variant_id":
                        VARIANT_ID,
                    "p_branch_id":
                        branch_id,
                    "p_quantity":
                        1,
                    "p_expires_at":
                        expires_at.isoformat(),
                },
            )
            .execute()
        )

        reservation_id = str(
            response.data
        )

        after_create = (
            get_inventory_snapshot(
                branch_id
            )
        )

        assert (
            after_create[
                "reserved_quantity"
            ]
            ==
            before[
                "reserved_quantity"
            ]
            + 1
        )

        assert (
            after_create[
                "available_quantity"
            ]
            ==
            before[
                "available_quantity"
            ]
            - 1
        )

        time.sleep(3)

        release_expired_reservations()

        reservation = get_reservation(
            reservation_id
        )

        assert (
            reservation["status"]
            == "expired"
        )

        final = get_inventory_snapshot(
            branch_id
        )

        assert final == before

    finally:
        cleanup_reservation(
            reservation_id
        )