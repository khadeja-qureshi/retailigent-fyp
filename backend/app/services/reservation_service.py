from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.core.supabase_client import supabase_admin


def _get_owned_reservation(
    reservation_id: str,
    customer_id: str,
):
    response = (
        supabase_admin
        .table("reservations")
        .select(
            "id, customer_id, variant_id, branch_id, "
            "quantity, status, expires_at, "
            "released_at, created_at"
        )
        .eq("id", reservation_id)
        .eq("customer_id", customer_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Reservation not found",
        )

    return response.data[0]


def get_customer_reservations(
    customer_id: str,
):
    response = (
        supabase_admin
        .table("reservations")
        .select(
            "id, customer_id, variant_id, branch_id, "
            "quantity, status, expires_at, "
            "released_at, created_at"
        )
        .eq("customer_id", customer_id)
        .order("created_at", desc=True)
        .execute()
    )

    reservations = response.data or []

    result = []

    for reservation in reservations:
        variant = (
            supabase_admin
            .table("product_variants")
            .select(
                "id, product_id, sku, price, "
                "color_id, size_id"
            )
            .eq("id", reservation["variant_id"])
            .limit(1)
            .execute()
        )

        branch = (
            supabase_admin
            .table("branches")
            .select(
                "id, name, city, area, address"
            )
            .eq("id", reservation["branch_id"])
            .limit(1)
            .execute()
        )

        product = None

        if variant.data:
            product_response = (
                supabase_admin
                .table("products")
                .select(
                    "id, name, sku, brand, base_price"
                )
                .eq(
                    "id",
                    variant.data[0]["product_id"],
                )
                .limit(1)
                .execute()
            )

            if product_response.data:
                product = product_response.data[0]

        result.append({
            **reservation,
            "variant": (
                variant.data[0]
                if variant.data
                else None
            ),
            "product": product,
            "branch": (
                branch.data[0]
                if branch.data
                else None
            ),
        })

    return {
        "items": result,
        "count": len(result),
    }


def create_customer_reservation(
    customer_id: str,
    variant_id: str,
    branch_id: str,
    quantity: int,
    hold_minutes: int = 15,
):
    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=hold_minutes)
    )

    try:
        response = (
            supabase_admin
            .rpc(
                "create_reservation",
                {
                    "p_customer_id": customer_id,
                    "p_variant_id": variant_id,
                    "p_branch_id": branch_id,
                    "p_quantity": quantity,
                    "p_expires_at":
                        expires_at.isoformat(),
                },
            )
            .execute()
        )

    except Exception as exc:
        message = str(exc)

        if (
            "insufficient" in message.lower()
            or "available" in message.lower()
            or "sellable" in message.lower()
        ):
            raise HTTPException(
                status_code=409,
                detail="Not enough stock available",
            )

        raise HTTPException(
            status_code=400,
            detail=message,
        )

    reservation_id = response.data

    if not reservation_id:
        raise HTTPException(
            status_code=500,
            detail="Reservation could not be created",
        )

    reservation = _get_owned_reservation(
        str(reservation_id),
        customer_id,
    )

    return reservation


def release_customer_reservation(
    customer_id: str,
    reservation_id: str,
):
    reservation = _get_owned_reservation(
        reservation_id,
        customer_id,
    )

    if reservation["status"] != "active":
        raise HTTPException(
            status_code=409,
            detail="Reservation is not active",
        )

    try:
        response = (
            supabase_admin
            .rpc(
                "release_reservation",
                {
                    "p_reservation_id":
                        reservation_id,
                    "p_status": "released",
                },
            )
            .execute()
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    if response.data is not True:
        raise HTTPException(
            status_code=409,
            detail="Reservation could not be released",
        )

    return {
        "released": True,
        "reservation_id": reservation_id,
    }


def release_expired_reservations():
    response = (
        supabase_admin
        .rpc(
            "release_expired_reservations"
        )
        .execute()
    )

    return {
        "released_count": response.data or 0,
    }