from decimal import Decimal
from typing import Any

from app.core.supabase_client import supabase_admin


def get_effective_price(variant_id: str) -> Decimal | None:
    """
    Get the authoritative effective price for a single product variant.

    Pricing is calculated by the Supabase RPC
    `get_effective_variant_price`.
    """

    response = (
        supabase_admin.rpc(
            "get_effective_variant_price",
            {"p_variant_id": variant_id},
        )
        .execute()
    )

    if response.data is None:
        return None

    return Decimal(str(response.data))


def get_effective_price_raw(variant_id: str) -> dict[str, Any]:
    """
    Return pricing information for a single variant
    in a JSON-friendly format.
    """

    effective_price = get_effective_price(variant_id)

    if effective_price is None:
        return {
            "variant_id": variant_id,
            "effective_price": None,
        }

    return {
        "variant_id": variant_id,
        "effective_price": float(effective_price),
    }


def get_effective_prices(
    variant_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """
    Get authoritative effective pricing for multiple variants
    in a single Supabase RPC call.
    """

    if not variant_ids:
        return {}

    response = (
        supabase_admin.rpc(
            "get_effective_variant_prices",
            {
                "p_variant_ids": variant_ids,
            },
        )
        .execute()
    )

    pricing_by_variant: dict[str, dict[str, Any]] = {}

    for row in response.data or []:
        variant_id = str(row["variant_id"])

        pricing_by_variant[variant_id] = {
            "base_price": float(row["base_price"]),
            "effective_price": float(row["effective_price"]),
            "discount_amount": float(row["discount_amount"]),
        }

    return pricing_by_variant