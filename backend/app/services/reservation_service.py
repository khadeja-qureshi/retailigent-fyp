from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException

from app.core.supabase_client import supabase_admin


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_data(
    response: Any,
) -> list[dict]:
    data = getattr(
        response,
        "data",
        None,
    )

    if not data:
        return []

    if isinstance(
        data,
        list,
    ):
        return data

    return [
        data,
    ]


def _get_owned_reservation(
    reservation_id: str,
    customer_id: str,
):
    try:
        response = (
            supabase_admin
            .table(
                "reservations"
            )
            .select(
                "id, customer_id, variant_id, branch_id, "
                "quantity, status, expires_at, "
                "released_at, created_at"
            )
            .eq(
                "id",
                reservation_id,
            )
            .eq(
                "customer_id",
                customer_id,
            )
            .limit(
                1
            )
            .execute()
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to retrieve reservation: "
                f"{exc}"
            ),
        ) from exc


    rows = _safe_data(
        response
    )


    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Reservation not found",
        )


    return rows[0]

def _enrich_reservation(
    reservation: dict[str, Any],
) -> dict[str, Any]:
    variant_id = str(
        reservation.get("variant_id") or ""
    )
    branch_id = str(
        reservation.get("branch_id") or ""
    )

    variant = None
    product = None
    branch = None

    if variant_id:
        variant_response = (
            supabase_admin
            .table("product_variants")
            .select(
                "id, product_id, sku, price, "
                "color_id, size_id"
            )
            .eq("id", variant_id)
            .limit(1)
            .execute()
        )
        variant_rows = _safe_data(variant_response)
        variant = variant_rows[0] if variant_rows else None

    if variant and variant.get("product_id"):
        product_response = (
            supabase_admin
            .table("products")
            .select("id, name, sku, brand, base_price")
            .eq("id", str(variant["product_id"]))
            .limit(1)
            .execute()
        )
        product_rows = _safe_data(product_response)
        product = product_rows[0] if product_rows else None

    if branch_id:
        branch_response = (
            supabase_admin
            .table("branches")
            .select("id, name, city, area, address")
            .eq("id", branch_id)
            .limit(1)
            .execute()
        )
        branch_rows = _safe_data(branch_response)
        branch = branch_rows[0] if branch_rows else None

    return {
        **reservation,
        "variant": variant,
        "product": product,
        "branch": branch,
    }

# ---------------------------------------------------------------------------
# Get customer reservations
# ---------------------------------------------------------------------------


def get_customer_reservations(
    customer_id: str,
):
    try:
        reservation_response = (
            supabase_admin
            .table(
                "reservations"
            )
            .select(
                "id, customer_id, variant_id, branch_id, "
                "quantity, status, expires_at, "
                "released_at, created_at"
            )
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

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to load reservations: "
                f"{exc}"
            ),
        ) from exc


    reservations = _safe_data(
        reservation_response
    )


    if not reservations:
        return {
            "items": [],
            "count": 0,
        }


    variant_ids = list({
        str(
            reservation[
                "variant_id"
            ]
        )
        for reservation in reservations
        if reservation.get(
            "variant_id"
        )
    })


    branch_ids = list({
        str(
            reservation[
                "branch_id"
            ]
        )
        for reservation in reservations
        if reservation.get(
            "branch_id"
        )
    })


    # ------------------------------------------------------------------
    # Fetch variants in one query
    # ------------------------------------------------------------------

    variants: list[dict] = []


    if variant_ids:
        try:
            variant_response = (
                supabase_admin
                .table(
                    "product_variants"
                )
                .select(
                    "id, product_id, sku, price, "
                    "color_id, size_id"
                )
                .in_(
                    "id",
                    variant_ids,
                )
                .execute()
            )


            variants = _safe_data(
                variant_response
            )

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Unable to load reservation variants: "
                    f"{exc}"
                ),
            ) from exc


    variant_by_id = {
        str(
            variant["id"]
        ): variant

        for variant in variants
        if variant.get(
            "id"
        )
    }


    # ------------------------------------------------------------------
    # Fetch products in one query
    # ------------------------------------------------------------------

    product_ids = list({
        str(
            variant[
                "product_id"
            ]
        )
        for variant in variants
        if variant.get(
            "product_id"
        )
    })


    products: list[dict] = []


    if product_ids:
        try:
            product_response = (
                supabase_admin
                .table(
                    "products"
                )
                .select(
                    "id, name, sku, brand, base_price"
                )
                .in_(
                    "id",
                    product_ids,
                )
                .execute()
            )


            products = _safe_data(
                product_response
            )

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Unable to load reservation products: "
                    f"{exc}"
                ),
            ) from exc


    product_by_id = {
        str(
            product["id"]
        ): product

        for product in products
        if product.get(
            "id"
        )
    }


    # ------------------------------------------------------------------
    # Fetch branches in one query
    # ------------------------------------------------------------------

    branches: list[dict] = []


    if branch_ids:
        try:
            branch_response = (
                supabase_admin
                .table(
                    "branches"
                )
                .select(
                    "id, name, city, area, address"
                )
                .in_(
                    "id",
                    branch_ids,
                )
                .execute()
            )


            branches = _safe_data(
                branch_response
            )

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Unable to load reservation branches: "
                    f"{exc}"
                ),
            ) from exc


    branch_by_id = {
        str(
            branch["id"]
        ): branch

        for branch in branches
        if branch.get(
            "id"
        )
    }


    # ------------------------------------------------------------------
    # Merge data
    # ------------------------------------------------------------------

    result = []


    for reservation in reservations:
        variant_id = str(
            reservation.get(
                "variant_id"
            )
            or
            ""
        )


        branch_id = str(
            reservation.get(
                "branch_id"
            )
            or
            ""
        )


        variant = (
            variant_by_id.get(
                variant_id
            )
        )


        product = None


        if variant:
            product_id = str(
                variant.get(
                    "product_id"
                )
                or
                ""
            )


            if product_id:
                product = (
                    product_by_id.get(
                        product_id
                    )
                )


        branch = (
            branch_by_id.get(
                branch_id
            )
        )


        result.append({
            **reservation,
            "variant": variant,
            "product": product,
            "branch": branch,
        })


    return {
        "items": result,
        "count": len(result),
    }


# ---------------------------------------------------------------------------
# Create reservation
# ---------------------------------------------------------------------------


def create_customer_reservation(
    customer_id: str,
    variant_id: str,
    branch_id: str,
    quantity: int,
    hold_minutes: int = 15,
):
    if quantity < 1:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be at least 1",
        )


    if (
        hold_minutes < 1
        or hold_minutes > 30
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Hold duration must be between "
                "1 and 30 minutes"
            ),
        )


    expires_at = (
        datetime.now(
            timezone.utc
        )
        +
        timedelta(
            minutes=hold_minutes
        )
    )


    try:
        response = (
            supabase_admin
            .rpc(
                "create_reservation",
                {
                    "p_customer_id":
                        customer_id,

                    "p_variant_id":
                        variant_id,

                    "p_branch_id":
                        branch_id,

                    "p_quantity":
                        quantity,

                    "p_expires_at":
                        expires_at.isoformat(),
                },
            )
            .execute()
        )

    except Exception as exc:
        message = str(
            exc
        )

        lowered = (
            message.lower()
        )


        if (
            "insufficient" in lowered
            or "available" in lowered
            or "sellable" in lowered
            or "stock" in lowered
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Not enough stock available"
                ),
            ) from exc


        raise HTTPException(
            status_code=400,
            detail=message,
        ) from exc


    reservation_id = (
        response.data
    )


    if (
        isinstance(
            reservation_id,
            list,
        )
        and reservation_id
    ):
        reservation_id = (
            reservation_id[0]
        )


    if isinstance(
        reservation_id,
        dict,
    ):
        reservation_id = (
            reservation_id.get(
                "create_reservation"
            )
            or
            reservation_id.get(
                "id"
            )
        )


    if not reservation_id:
        raise HTTPException(
            status_code=500,
            detail=(
                "Reservation could not be created"
            ),
        )


    reservation = (
        _get_owned_reservation(
            str(
                reservation_id
            ),
            customer_id,
        )
    )


    return _enrich_reservation(reservation)


# ---------------------------------------------------------------------------
# Release reservation
# ---------------------------------------------------------------------------


def release_customer_reservation(
    customer_id: str,
    reservation_id: str,
):
    reservation = (
        _get_owned_reservation(
            reservation_id,
            customer_id,
        )
    )


    if (
        reservation.get(
            "status"
        )
        !=
        "active"
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Reservation is not active"
            ),
        )


    try:
        response = (
            supabase_admin
            .rpc(
                "release_reservation",
                {
                    "p_reservation_id":
                        reservation_id,

                    "p_status":
                        "released",
                },
            )
            .execute()
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc


    released = (
        response.data
    )


    if (
        isinstance(
            released,
            list,
        )
        and released
    ):
        released = (
            released[0]
        )


    if released is not True:
        raise HTTPException(
            status_code=409,
            detail=(
                "Reservation could not be released"
            ),
        )


    return {
        "released": True,
        "reservation_id":
            reservation_id,
    }


# ---------------------------------------------------------------------------
# Release expired reservations
# ---------------------------------------------------------------------------


def release_expired_reservations():
    try:
        response = (
            supabase_admin
            .rpc(
                "release_expired_reservations"
            )
            .execute()
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to release expired reservations: "
                f"{exc}"
            ),
        ) from exc


    released_count = (
        response.data
        or
        0
    )


    if (
        isinstance(
            released_count,
            list,
        )
        and released_count
    ):
        released_count = (
            released_count[0]
        )


    return {
        "released_count":
            released_count,
    }