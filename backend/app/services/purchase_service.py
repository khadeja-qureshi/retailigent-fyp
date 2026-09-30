from fastapi import HTTPException

from app.core.supabase_client import supabase_admin


def _handle_purchase_error(exc: Exception):
    message = str(exc)
    lowered = message.lower()

    if (
        "insufficient" in lowered
        or "available" in lowered
        or "stock" in lowered
        or "sellable" in lowered
    ):
        raise HTTPException(
            status_code=409,
            detail="Not enough stock available",
        )

    if "reservation" in lowered:
        raise HTTPException(
            status_code=409,
            detail=message,
        )

    if "idempotency" in lowered:
        raise HTTPException(
            status_code=409,
            detail=message,
        )

    raise HTTPException(
        status_code=400,
        detail=message,
    )


def find_purchase_branch(
    variant_id: str,
    quantity: int,
    preferred_branch_id: str | None = None,
):
    if quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than zero",
        )

    try:
        response = (
            supabase_admin
            .rpc(
                "find_branch_for_purchase",
                {
                    "p_variant_id": variant_id,
                    "p_quantity": quantity,
                    "p_preferred_branch_id": preferred_branch_id,
                },
            )
            .execute()
        )

    except Exception as exc:
        _handle_purchase_error(exc)

    branch_id = response.data

    if not branch_id:
        raise HTTPException(
            status_code=409,
            detail="No branch has enough stock available",
        )

    return str(branch_id)


def execute_customer_purchase(
    customer_id: str,
    variant_id: str,
    quantity: int,
    idempotency_key: str,
    branch_id: str | None = None,
    smart_cart_rule_id: str | None = None,
):
    """
    Execute a direct customer purchase.

    Direct purchases are handled by the deterministic
    execute_mock_purchase() database function.

    This path does NOT create a reservation first.
    Reservations are handled separately by
    convert_customer_reservation_to_purchase().
    """

    if quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than zero",
        )

    if not idempotency_key.strip():
        raise HTTPException(
            status_code=400,
            detail="Idempotency key is required",
        )

    # Check whether this idempotency key has already been used.
    existing_response = (
        supabase_admin
        .table("purchase_attempts")
        .select(
            "id, customer_id, reservation_id, variant_id, "
            "branch_id, quantity, status, order_id, "
            "smart_cart_rule_id"
        )
        .eq("idempotency_key", idempotency_key)
        .limit(1)
        .execute()
    )

    existing_attempt = (
        existing_response.data[0]
        if existing_response.data
        else None
    )

    if existing_attempt:
        # The same idempotency key cannot represent a different
        # customer, variant, branch, or quantity.
        if (
            existing_attempt["customer_id"] != customer_id
            or existing_attempt["variant_id"] != variant_id
            or (
                branch_id is not None
                and existing_attempt["branch_id"] != branch_id
            )
            or existing_attempt["quantity"] != quantity
            or existing_attempt["smart_cart_rule_id"] != smart_cart_rule_id
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "This idempotency key was already used "
                    "for a different request"
                ),
            )

        # If the original request already completed, return
        # the existing purchase without creating anything new.
        if (
            existing_attempt["status"] == "completed"
            and existing_attempt["order_id"]
        ):
            return {
                "success": True,
                "order_id": existing_attempt["order_id"],
                "purchase_attempt_id": existing_attempt["id"],
                "reservation_id": existing_attempt["reservation_id"],
                "reason": "Idempotency key already fulfilled",
                "reason_code": "already_completed",
                "already_completed": True,
            }

        # An incomplete direct purchase should not silently
        # reuse a reservation. Direct purchases are handled
        # atomically by execute_mock_purchase().
        raise HTTPException(
            status_code=409,
            detail="Existing purchase attempt is not completed",
        )

    # If no branch was supplied, deterministically select one
    # with enough available stock.
    if not branch_id:
        branch_id = find_purchase_branch(
            variant_id=variant_id,
            quantity=quantity,
        )

    try:
        response = (
            supabase_admin
            .rpc(
                "execute_mock_purchase",
                {
                    "p_customer_id": customer_id,
                    "p_variant_id": variant_id,
                    "p_branch_id": branch_id,
                    "p_quantity": quantity,
                    "p_idempotency_key": idempotency_key,
                    "p_smart_cart_rule_id": smart_cart_rule_id,
                },
            )
            .execute()
        )

    except Exception as exc:
        _handle_purchase_error(exc)

    result = response.data

    if not result:
        raise HTTPException(
            status_code=500,
            detail="Purchase could not be completed",
        )

    if not result.get("success", False):
        reason = (
            result.get("reason")
            or "Purchase could not be completed"
        )

        raise HTTPException(
            status_code=409,
            detail=reason,
        )

    if result.get("reason_code") == "already_completed":
        result["already_completed"] = True

    # Direct purchases do not create reservations.
    result["reservation_id"] = None

    return result


def convert_customer_reservation_to_purchase(
    customer_id: str,
    reservation_id: str,
    idempotency_key: str,
    quantity: int | None = None,
):
    """
    Convert an existing customer reservation into a purchase.

    This is intentionally separate from direct purchases.
    """

    if not idempotency_key.strip():
        raise HTTPException(
            status_code=400,
            detail="Idempotency key is required",
        )

    # Verify ownership before calling the SECURITY DEFINER RPC.
    reservation_response = (
        supabase_admin
        .table("reservations")
        .select(
            "id, customer_id, variant_id, branch_id, "
            "quantity, status, expires_at"
        )
        .eq("id", reservation_id)
        .eq("customer_id", customer_id)
        .limit(1)
        .execute()
    )

    if not reservation_response.data:
        raise HTTPException(
            status_code=404,
            detail="Reservation not found",
        )

    reservation = reservation_response.data[0]

    if quantity is not None:
        if quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail="Quantity must be greater than zero",
            )

        if quantity > reservation["quantity"]:
            raise HTTPException(
                status_code=409,
                detail="Purchase quantity exceeds reserved quantity",
            )

    try:
        response = (
            supabase_admin
            .rpc(
                "convert_reservation_to_purchase",
                {
                    "p_reservation_id": reservation_id,
                    "p_idempotency_key": idempotency_key,
                    "p_quantity": quantity,
                },
            )
            .execute()
        )

    except Exception as exc:
        _handle_purchase_error(exc)

    result = response.data

    if not result:
        raise HTTPException(
            status_code=500,
            detail="Reservation purchase could not be completed",
        )

    if not result.get("success", False):
        reason = (
            result.get("reason")
            or "Purchase could not be completed"
        )

        raise HTTPException(
            status_code=409,
            detail=reason,
        )

    if result.get("reason_code") == "already_completed":
        result["already_completed"] = True

    return result
