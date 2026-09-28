import os

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

CUSTOMER_ID = os.getenv("TEST_CUSTOMER_ID")
VARIANT_ID = os.getenv("TEST_VARIANT_ID")


def get_inventory_snapshot():
    response = (
        supabase_admin
        .table("branch_inventory")
        .select(
            "id, branch_id, variant_id, "
            "on_hand_quantity, reserved_quantity, "
            "safety_stock, available_quantity"
        )
        .eq("variant_id", VARIANT_ID)
        .order("branch_id")
        .execute()
    )

    return response.data or []


def test_cart_and_wishlist_do_not_change_inventory():
    assert CUSTOMER_ID, "TEST_CUSTOMER_ID is missing"
    assert VARIANT_ID, "TEST_VARIANT_ID is missing"

    before = get_inventory_snapshot()
    assert before, "No inventory rows found for test variant"

    cart_item_id = None
    wishlist_item_id = None

    try:
        cart = add_cart_item(
            customer_id=CUSTOMER_ID,
            variant_id=VARIANT_ID,
            quantity=1,
        )

        cart_item = next(
            item
            for item in cart["items"]
            if item["variant_id"] == VARIANT_ID
        )

        cart_item_id = cart_item["id"]

        update_cart_item(
            customer_id=CUSTOMER_ID,
            item_id=cart_item_id,
            quantity=100,
        )

        wishlist = add_wishlist_item(
            customer_id=CUSTOMER_ID,
            variant_id=VARIANT_ID,
        )

        wishlist_item = next(
            item
            for item in wishlist["items"]
            if item["variant_id"] == VARIANT_ID
        )

        wishlist_item_id = wishlist_item["id"]

        after_operations = get_inventory_snapshot()

        assert after_operations == before

    finally:
        if wishlist_item_id:
            delete_wishlist_item(
                customer_id=CUSTOMER_ID,
                item_id=wishlist_item_id,
            )

        if cart_item_id:
            delete_cart_item(
                customer_id=CUSTOMER_ID,
                item_id=cart_item_id,
            )

    final_snapshot = get_inventory_snapshot()

    assert final_snapshot == before