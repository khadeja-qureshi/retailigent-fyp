from fastapi import HTTPException

from app.core.supabase_client import supabase_admin
from app.services.shopping_read_service import enrich_variants


def _require_active_variant(variant_id: str):
    response = (
        supabase_admin
        .table("product_variants")
        .select("id")
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


def get_wishlist(customer_id: str):
    response = (
        supabase_admin
        .table("wishlists")
        .select("*")
        .eq("customer_id", customer_id)
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
        "items": result,
        "count": len(result),
    }


def add_wishlist_item(
    customer_id: str,
    variant_id: str,
):
    _require_active_variant(variant_id)

    existing = (
        supabase_admin
        .table("wishlists")
        .select("*")
        .eq("customer_id", customer_id)
        .eq("variant_id", variant_id)
        .limit(1)
        .execute()
    )

    if not existing.data:
        (
            supabase_admin
            .table("wishlists")
            .insert({
                "customer_id": customer_id,
                "variant_id": variant_id,
            })
            .execute()
        )

    return get_wishlist(customer_id)


def delete_wishlist_item(
    customer_id: str,
    item_id: str,
):
    existing = (
        supabase_admin
        .table("wishlists")
        .select("id")
        .eq("id", item_id)
        .eq("customer_id", customer_id)
        .limit(1)
        .execute()
    )

    if not existing.data:
        raise HTTPException(
            status_code=404,
            detail="Wishlist item not found",
        )

    (
        supabase_admin
        .table("wishlists")
        .delete()
        .eq("id", item_id)
        .eq("customer_id", customer_id)
        .execute()
    )