from decimal import Decimal

from fastapi import HTTPException

from app.core.supabase_client import supabase_admin


ALERT_SELECT = (
    "id, customer_id, variant_id, alert_type, "
    "target_price, is_active, created_at, triggered_at"
)


def _get_owned_alert(
    customer_id: str,
    alert_id: str,
) -> dict:
    """
    Fetch one alert owned by the authenticated customer.
    """
    response = (
        supabase_admin
        .table("alerts")
        .select(ALERT_SELECT)
        .eq("id", alert_id)
        .eq("customer_id", customer_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Alert not found",
        )

    return response.data[0]


def _require_active_variant(
    variant_id: str,
) -> dict:
    """
    Ensure the variant and its parent product are active.
    """
    variant_response = (
        supabase_admin
        .table("product_variants")
        .select(
            "id, product_id, sku, price, "
            "color_id, size_id, is_active"
        )
        .eq("id", variant_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not variant_response.data:
        raise HTTPException(
            status_code=404,
            detail="Active product variant not found",
        )

    variant = variant_response.data[0]

    product_response = (
        supabase_admin
        .table("products")
        .select(
            "id, name, sku, brand, "
            "base_price, is_active"
        )
        .eq("id", variant["product_id"])
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not product_response.data:
        raise HTTPException(
            status_code=404,
            detail="Active parent product not found",
        )

    return {
        "variant": variant,
        "product": product_response.data[0],
    }


def _get_effective_price(
    variant_id: str,
):
    """
    Get the deterministic current effective price.
    """
    try:
        response = (
            supabase_admin
            .rpc(
                "get_effective_variant_price",
                {
                    "p_variant_id": variant_id,
                },
            )
            .execute()
        )

        if response.data is None:
            return None

        return float(response.data)

    except Exception:
        return None


def _enrich_alert(
    alert: dict,
) -> dict:
    """
    Add product, variant, and live effective-price data
    for frontend/chat presentation.
    """
    variant_response = (
        supabase_admin
        .table("product_variants")
        .select(
            "id, product_id, sku, price, "
            "color_id, size_id"
        )
        .eq("id", alert["variant_id"])
        .limit(1)
        .execute()
    )

    variant = (
        variant_response.data[0]
        if variant_response.data
        else None
    )

    product = None

    if variant:
        product_response = (
            supabase_admin
            .table("products")
            .select(
                "id, name, sku, brand, base_price"
            )
            .eq(
                "id",
                variant["product_id"],
            )
            .limit(1)
            .execute()
        )

        if product_response.data:
            product = (
                product_response.data[0]
            )

    return {
        **alert,
        "variant": variant,
        "product": product,
        "effective_price":
            _get_effective_price(
                alert["variant_id"]
            ),
    }


def list_customer_alerts(
    customer_id: str,
):
    """
    Return all alerts belonging to the customer.
    """
    response = (
        supabase_admin
        .table("alerts")
        .select(ALERT_SELECT)
        .eq(
            "customer_id",
            customer_id,
        )
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    alerts = response.data or []

    enriched = [
        _enrich_alert(alert)
        for alert in alerts
    ]

    return {
        "items": enriched,
        "count": len(enriched),
    }


def create_customer_alert(
    customer_id: str,
    variant_id: str,
    alert_type: str,
    target_price: (
        Decimal | float | None
    ) = None,
):
    """
    Create a new one-shot customer alert.

    Supported:
    - price_drop
    - restock
    - sale
    """

    if alert_type not in {
        "price_drop",
        "restock",
        "sale",
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                "alert_type must be "
                "'price_drop', 'restock', "
                "or 'sale'"
            ),
        )

    if (
        alert_type == "price_drop"
        and target_price is None
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Price-drop alerts require "
                "a target_price"
            ),
        )

    if (
        target_price is not None
        and float(target_price) < 0
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Target price cannot "
                "be negative"
            ),
        )

    _require_active_variant(
        variant_id
    )

    payload = {
        "customer_id": customer_id,
        "variant_id": variant_id,
        "alert_type": alert_type,
        "target_price": (
            float(target_price)
            if target_price is not None
            else None
        ),
        "is_active": True,

        # System-managed field.
        "triggered_at": None,
    }

    try:
        response = (
            supabase_admin
            .table("alerts")
            .insert(payload)
            .execute()
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    if not response.data:
        raise HTTPException(
            status_code=500,
            detail="Alert could not be created",
        )

    return _enrich_alert(
        response.data[0]
    )


def pause_customer_alert(
    customer_id: str,
    alert_id: str,
):
    """
    Pause an untriggered active alert.

    Since alerts use an is_active flag rather than a separate
    paused status, pausing sets is_active=false.
    """
    alert = _get_owned_alert(
        customer_id,
        alert_id,
    )

    if alert["triggered_at"] is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "A triggered alert cannot "
                "be paused"
            ),
        )

    if not alert["is_active"]:
        return _enrich_alert(alert)

    response = (
        supabase_admin
        .table("alerts")
        .update({
            "is_active": False,
        })
        .eq("id", alert_id)
        .eq(
            "customer_id",
            customer_id,
        )
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=500,
            detail="Alert could not be paused",
        )

    return _enrich_alert(
        response.data[0]
    )


def resume_customer_alert(
    customer_id: str,
    alert_id: str,
):
    """
    Resume an untriggered paused alert.

    Triggered alerts are one-shot and must not be reactivated.
    """
    alert = _get_owned_alert(
        customer_id,
        alert_id,
    )

    if alert["triggered_at"] is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "A triggered alert is one-shot. "
                "Create a new alert instead."
            ),
        )

    if alert["is_active"]:
        return _enrich_alert(alert)

    response = (
        supabase_admin
        .table("alerts")
        .update({
            "is_active": True,
        })
        .eq("id", alert_id)
        .eq(
            "customer_id",
            customer_id,
        )
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=500,
            detail="Alert could not be resumed",
        )

    return _enrich_alert(
        response.data[0]
    )


def cancel_customer_alert(
    customer_id: str,
    alert_id: str,
):
    """
    Delete/cancel an alert owned by the customer.

    The backend checks ownership before deleting.
    """
    alert = _get_owned_alert(
        customer_id,
        alert_id,
    )

    response = (
        supabase_admin
        .table("alerts")
        .delete()
        .eq("id", alert_id)
        .eq(
            "customer_id",
            customer_id,
        )
        .execute()
    )

    return {
        "deleted": True,
        "alert_id": alert["id"],
    }