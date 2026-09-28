from typing import Any

from app.core.supabase_client import supabase_admin
from app.services.pricing_service import get_effective_prices


def enrich_variants(
    variant_ids: list[str],
) -> dict[str, dict[str, Any]]:
    if not variant_ids:
        return {}

    variant_response = (
        supabase_admin
        .table("product_variants")
        .select(
            "id, product_id, sku, color_id, size_id, "
            "price, attributes, is_active"
        )
        .in_("id", variant_ids)
        .execute()
    )

    variants = variant_response.data or []

    product_ids = list({
        row["product_id"]
        for row in variants
    })

    product_response = (
        supabase_admin
        .table("products")
        .select(
            "id, name, slug, sku, brand, base_price, "
            "material, attributes, is_active"
        )
        .in_("id", product_ids)
        .execute()
        if product_ids
        else None
    )

    products = {
        row["id"]: row
        for row in (
            product_response.data
            if product_response
            else []
        )
    }

    pricing = get_effective_prices(variant_ids)

    inventory_response = (
        supabase_admin
        .table("branch_inventory")
        .select(
            "variant_id, branch_id, available_quantity"
        )
        .in_("variant_id", variant_ids)
        .execute()
    )

    inventory_by_variant: dict[str, list[dict]] = {}

    for row in inventory_response.data or []:
        inventory_by_variant.setdefault(
            row["variant_id"],
            [],
        ).append(row)

    result: dict[str, dict[str, Any]] = {}

    for variant in variants:
        variant_id = variant["id"]

        availability_rows = inventory_by_variant.get(
            variant_id,
            [],
        )

        # Branch-agnostic cart hint:
        # largest quantity available at any single branch.
        max_available = max(
            (
                int(row["available_quantity"])
                for row in availability_rows
            ),
            default=0,
        )

        result[variant_id] = {
            "variant": variant,
            "product": products.get(
                variant["product_id"]
            ),
            "pricing": pricing.get(variant_id),
            "availability_hint": {
                "max_available_at_one_branch":
                    max_available,
                "has_stock": max_available > 0,
            },
        }

    return result