import os
import time

from collections.abc import Callable
from typing import TypeVar

import httpx
from dotenv import load_dotenv

from app.core.supabase_client import supabase_admin
from app.services.cart_service import (
    add_cart_item,
    delete_cart_item,
    update_cart_item,
)
from app.services.wishlist_service import (
    add_wishlist_item,
    delete_wishlist_item,
)


load_dotenv()


CUSTOMER_ID = os.getenv(
    "TEST_CUSTOMER_ID"
)

VARIANT_ID = os.getenv(
    "TEST_VARIANT_ID"
)


T = TypeVar("T")


def _with_retry(
    operation: Callable[[], T],
    *,
    attempts: int = 3,
    delay_seconds: float = 0.75,
) -> T:
    """
    Retry only transient HTTP timeout failures
    from hosted Supabase.

    Real application/database errors are not
    swallowed or retried.
    """

    last_error: httpx.TimeoutException | None = None

    for attempt in range(attempts):
        try:
            return operation()

        except httpx.TimeoutException as exc:
            last_error = exc

            if attempt == attempts - 1:
                raise

            time.sleep(
                delay_seconds
            )

    if last_error is not None:
        raise last_error

    raise RuntimeError(
        "Retry operation ended unexpectedly."
    )


def get_inventory_snapshot():
    def query():
        response = (
            supabase_admin
            .table(
                "branch_inventory"
            )
            .select(
                (
                    "id,"
                    "branch_id,"
                    "variant_id,"
                    "on_hand_quantity,"
                    "reserved_quantity,"
                    "safety_stock,"
                    "available_quantity"
                )
            )
            .eq(
                "variant_id",
                VARIANT_ID,
            )
            .order(
                "branch_id"
            )
            .execute()
        )

        return response.data or []

    return _with_retry(
        query
    )


def test_cart_and_wishlist_do_not_change_inventory():
    assert CUSTOMER_ID, (
        "TEST_CUSTOMER_ID is missing"
    )

    assert VARIANT_ID, (
        "TEST_VARIANT_ID is missing"
    )

    before = get_inventory_snapshot()

    assert before, (
        "No inventory rows found "
        "for test variant"
    )

    cart_item_id = None
    wishlist_item_id = None

    try:
        cart = _with_retry(
            lambda: add_cart_item(
                customer_id=CUSTOMER_ID,
                variant_id=VARIANT_ID,
                quantity=1,
            )
        )

        cart_item = next(
            item
            for item in cart["items"]
            if item["variant_id"] == VARIANT_ID
        )

        cart_item_id = cart_item["id"]

        _with_retry(
            lambda: update_cart_item(
                customer_id=CUSTOMER_ID,
                item_id=cart_item_id,
                quantity=100,
            )
        )

        wishlist = _with_retry(
            lambda: add_wishlist_item(
                customer_id=CUSTOMER_ID,
                variant_id=VARIANT_ID,
            )
        )

        wishlist_item = next(
            item
            for item in wishlist["items"]
            if item["variant_id"] == VARIANT_ID
        )

        wishlist_item_id = wishlist_item["id"]

        after_operations = (
            get_inventory_snapshot()
        )

        assert (
            after_operations
            ==
            before
        )

    finally:
        if wishlist_item_id:
            _with_retry(
                lambda: delete_wishlist_item(
                    customer_id=CUSTOMER_ID,
                    item_id=wishlist_item_id,
                )
            )

        if cart_item_id:
            _with_retry(
                lambda: delete_cart_item(
                    customer_id=CUSTOMER_ID,
                    item_id=cart_item_id,
                )
            )

    final_snapshot = (
        get_inventory_snapshot()
    )

    assert (
        final_snapshot
        ==
        before
    )