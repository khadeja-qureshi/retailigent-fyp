from fastapi import APIRouter, HTTPException

from app.services.pricing_service import get_effective_price_raw


router = APIRouter(
    prefix="/api/v1/pricing",
    tags=["Pricing"],
)


@router.get("/{variant_id}")
def get_variant_price(variant_id: str):
    """
    Get the current effective price for a product variant.

    The price is calculated by the authoritative
    Supabase pricing RPC.
    """

    result = get_effective_price_raw(variant_id)

    if result["effective_price"] is None:
        raise HTTPException(
            status_code=404,
            detail="Active product variant not found",
        )

    return result