from fastapi import HTTPException

from app.core.supabase_client import supabase_admin
from app.services.shopping_read_service import enrich_variants


def _get_active_cart(customer_id: str):
    response = (
        supabase_admin
        .table("carts")
        .select("*")
        .eq("customer_id", customer_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]


def _get_or_create_active_cart(customer_id: str):
    cart = _get_active_cart(customer_id)

    if cart:
        return cart

    try:
        response = (
            supabase_admin
            .table("carts")
            .insert({
                "customer_id": customer_id,
                "status": "active",
            })
            .execute()
        )

        return response.data[0]

    except Exception:
        # The DB permits only one active cart.
        # If a concurrent request created it first,
        # simply fetch that cart.
        cart = _get_active_cart(customer_id)

        if cart:
            return cart

        raise


def _require_active_variant(variant_id: str):
    response = (
        supabase_admin
        .table("product_variants")
        .select("id, product_id")
        .eq("id", variant_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Active product variant not found",
        )


def get_cart_summary(customer_id: str):
    cart = _get_active_cart(customer_id)

    if not cart:
        return {
            "cart": None,
            "items": [],
            "item_count": 0,
        }

    response = (
        supabase_admin
        .table("cart_items")
        .select("*")
        .eq("cart_id", cart["id"])
        .order("created_at")
        .execute()
    )

    items = response.data or []

    enrichment = enrich_variants([
        item["variant_id"]
        for item in items
    ])

    result = []

    for item in items:
        result.append({
            **item,
            **enrichment.get(
                item["variant_id"],
                {},
            ),
        })

    return {
        "cart": cart,
        "items": result,
        "item_count": len(result),
    }


def add_cart_item(
    customer_id: str,
    variant_id: str,
    quantity: int,
):
    _require_active_variant(variant_id)

    cart = _get_or_create_active_cart(
        customer_id
    )

    existing = (
        supabase_admin
        .table("cart_items")
        .select("*")
        .eq("cart_id", cart["id"])
        .eq("variant_id", variant_id)
        .limit(1)
        .execute()
    )

    if existing.data:
        item = existing.data[0]

        (
            supabase_admin
            .table("cart_items")
            .update({
                "quantity":
                    item["quantity"] + quantity
            })
            .eq("id", item["id"])
            .eq("cart_id", cart["id"])
            .execute()
        )

    else:
        (
            supabase_admin
            .table("cart_items")
            .insert({
                "cart_id": cart["id"],
                "variant_id": variant_id,
                "quantity": quantity,
            })
            .execute()
        )

    return get_cart_summary(customer_id)


def update_cart_item(
    customer_id: str,
    item_id: str,
    quantity: int,
):
    cart = _get_active_cart(customer_id)

    if not cart:
        raise HTTPException(
            status_code=404,
            detail="Active cart not found",
        )

    existing = (
        supabase_admin
        .table("cart_items")
        .select("id")
        .eq("id", item_id)
        .eq("cart_id", cart["id"])
        .limit(1)
        .execute()
    )

    if not existing.data:
        raise HTTPException(
            status_code=404,
            detail="Cart item not found",
        )

    (
        supabase_admin
        .table("cart_items")
        .update({
            "quantity": quantity,
        })
        .eq("id", item_id)
        .eq("cart_id", cart["id"])
        .execute()
    )

    return get_cart_summary(customer_id)


def delete_cart_item(
    customer_id: str,
    item_id: str,
):
    cart = _get_active_cart(customer_id)

    if not cart:
        raise HTTPException(
            status_code=404,
            detail="Active cart not found",
        )

    existing = (
        supabase_admin
        .table("cart_items")
        .select("id")
        .eq("id", item_id)
        .eq("cart_id", cart["id"])
        .limit(1)
        .execute()
    )

    if not existing.data:
        raise HTTPException(
            status_code=404,
            detail="Cart item not found",
        )

    (
        supabase_admin
        .table("cart_items")
        .delete()
        .eq("id", item_id)
        .eq("cart_id", cart["id"])
        .execute()
    )