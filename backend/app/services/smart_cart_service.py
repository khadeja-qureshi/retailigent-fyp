from decimal import Decimal

from fastapi import HTTPException

from app.core.supabase_client import supabase_admin


SMART_CART_RULE_SELECT = (
    "id, customer_id, variant_id, branch_id, "
    "quantity, target_price, min_discount_percentage, "
    "authorization_mode, status, triggered_at, "
    "last_evaluated_at, created_at, updated_at"
)


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
            "id, product_id, sku, price, is_active"
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
            "id, name, sku, brand, base_price, is_active"
        )
        .eq(
            "id",
            variant["product_id"],
        )
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


def _require_active_branch(
    branch_id: str,
) -> dict:
    """
    Ensure a branch exists and is active.
    """
    response = (
        supabase_admin
        .table("branches")
        .select(
            "id, name, city, area, address, is_active"
        )
        .eq("id", branch_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Active branch not found",
        )

    return response.data[0]


def _get_owned_rule(
    customer_id: str,
    rule_id: str,
) -> dict:
    """
    Fetch one Smart Cart rule owned by the authenticated customer.
    """
    response = (
        supabase_admin
        .table("smart_cart_rules")
        .select(
            SMART_CART_RULE_SELECT
        )
        .eq("id", rule_id)
        .eq(
            "customer_id",
            customer_id,
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Smart Cart rule not found",
        )

    return response.data[0]


def _get_effective_price(
    variant_id: str,
):
    """
    Resolve the effective price from the deterministic DB function.
    """
    try:
        response = (
            supabase_admin
            .rpc(
                "get_effective_variant_price",
                {
                    "p_variant_id":
                        variant_id,
                },
            )
            .execute()
        )

        if response.data is None:
            return None

        return float(response.data)

    except Exception:
        return None


def _enrich_rule(
    rule: dict,
) -> dict:
    """
    Add product, variant, branch, and current effective price
    for frontend/chat presentation.
    """
    variant_response = (
        supabase_admin
        .table("product_variants")
        .select(
            "id, product_id, sku, price, "
            "color_id, size_id"
        )
        .eq(
            "id",
            rule["variant_id"],
        )
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

    branch = None

    if rule.get("branch_id"):
        branch_response = (
            supabase_admin
            .table("branches")
            .select(
                "id, name, city, area, address"
            )
            .eq(
                "id",
                rule["branch_id"],
            )
            .limit(1)
            .execute()
        )

        if branch_response.data:
            branch = (
                branch_response.data[0]
            )

    return {
        **rule,
        "variant": variant,
        "product": product,
        "branch": branch,
        "effective_price":
            _get_effective_price(
                rule["variant_id"]
            ),
    }


def list_customer_smart_cart_rules(
    customer_id: str,
):
    """
    Return all Smart Cart rules owned by a customer.
    """
    response = (
        supabase_admin
        .table("smart_cart_rules")
        .select(
            SMART_CART_RULE_SELECT
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

    rules = response.data or []

    enriched = [
        _enrich_rule(rule)
        for rule in rules
    ]

    return {
        "items": enriched,
        "count": len(enriched),
    }


def create_customer_smart_cart_rule(
    customer_id: str,
    variant_id: str,
    quantity: int = 1,
    target_price: (
        Decimal | float | None
    ) = None,
    min_discount_percentage: (
        Decimal | float | None
    ) = None,
    authorization_mode: str = "notify_only",
    branch_id: str | None = None,
):
    """
    Create a customer Smart Cart rule.

    Customers may define conditions and authorization mode,
    but system-controlled fields always start in their safe
    default state.
    """

    if quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Quantity must be greater "
                "than zero"
            ),
        )

    if (
        target_price is None
        and
        min_discount_percentage is None
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Set target_price or "
                "min_discount_percentage"
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

    if (
        min_discount_percentage
        is not None
        and not (
            0
            <= float(
                min_discount_percentage
            )
            <= 100
        )
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Minimum discount percentage "
                "must be between 0 and 100"
            ),
        )

    if authorization_mode not in {
        "notify_only",
        "auto_buy",
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                "authorization_mode must be "
                "'notify_only' or 'auto_buy'"
            ),
        )

    _require_active_variant(
        variant_id
    )

    if branch_id:
        _require_active_branch(
            branch_id
        )

    payload = {
        "customer_id": customer_id,
        "variant_id": variant_id,
        "branch_id": branch_id,
        "quantity": quantity,
        "target_price": (
            float(target_price)
            if target_price is not None
            else None
        ),
        "min_discount_percentage": (
            float(
                min_discount_percentage
            )
            if (
                min_discount_percentage
                is not None
            )
            else None
        ),
        "authorization_mode":
            authorization_mode,

        # Explicit safe system defaults.
        "status": "active",
        "triggered_at": None,
        "last_evaluated_at": None,
    }

    try:
        response = (
            supabase_admin
            .table("smart_cart_rules")
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
            detail=(
                "Smart Cart rule could "
                "not be created"
            ),
        )

    return _enrich_rule(
        response.data[0]
    )


def pause_customer_smart_cart_rule(
    customer_id: str,
    rule_id: str,
):
    """
    Pause an active Smart Cart rule.

    Triggered/completed rules are system-owned and may not
    be changed by this customer-facing service.
    """
    rule = _get_owned_rule(
        customer_id,
        rule_id,
    )

    if rule["status"] == "paused":
        return _enrich_rule(rule)

    if rule["status"] != "active":
        raise HTTPException(
            status_code=409,
            detail=(
                "Only an active Smart Cart "
                "rule can be paused"
            ),
        )

    response = (
        supabase_admin
        .table("smart_cart_rules")
        .update({
            "status": "paused",
        })
        .eq(
            "id",
            rule_id,
        )
        .eq(
            "customer_id",
            customer_id,
        )
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=500,
            detail=(
                "Smart Cart rule could "
                "not be paused"
            ),
        )

    return _enrich_rule(
        response.data[0]
    )


def resume_customer_smart_cart_rule(
    customer_id: str,
    rule_id: str,
):
    """
    Resume a paused Smart Cart rule.
    """
    rule = _get_owned_rule(
        customer_id,
        rule_id,
    )

    if rule["status"] == "active":
        return _enrich_rule(rule)

    if rule["status"] != "paused":
        raise HTTPException(
            status_code=409,
            detail=(
                "Only a paused Smart Cart "
                "rule can be resumed"
            ),
        )

    response = (
        supabase_admin
        .table("smart_cart_rules")
        .update({
            "status": "active",
        })
        .eq(
            "id",
            rule_id,
        )
        .eq(
            "customer_id",
            customer_id,
        )
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=500,
            detail=(
                "Smart Cart rule could "
                "not be resumed"
            ),
        )

    return _enrich_rule(
        response.data[0]
    )


def cancel_customer_smart_cart_rule(
    customer_id: str,
    rule_id: str,
):
    """
    Cancel an active or paused rule.

    Triggered/completed rules are immutable from the
    customer's perspective.
    """
    rule = _get_owned_rule(
        customer_id,
        rule_id,
    )

    if rule["status"] == "cancelled":
        return _enrich_rule(rule)

    if rule["status"] not in {
        "active",
        "paused",
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Triggered or completed "
                "Smart Cart rules cannot "
                "be cancelled"
            ),
        )

    response = (
        supabase_admin
        .table("smart_cart_rules")
        .update({
            "status": "cancelled",
        })
        .eq(
            "id",
            rule_id,
        )
        .eq(
            "customer_id",
            customer_id,
        )
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=500,
            detail=(
                "Smart Cart rule could "
                "not be cancelled"
            ),
        )

    return _enrich_rule(
        response.data[0]
    )


def get_customer_smart_cart_rule(
    customer_id: str,
    rule_id: str,
):
    """
    Customer-facing lookup for one owned rule.
    """
    rule = _get_owned_rule(
        customer_id,
        rule_id,
    )

    return _enrich_rule(rule)


def get_smart_cart_rule_for_system(
    rule_id: str,
) -> dict:
    """
    Internal trusted lookup used by the Purchase Agent.

    This deliberately does not accept a customer_id because
    the system is processing a rule that has already been
    selected by the trusted backend worker.
    """
    response = (
        supabase_admin
        .table("smart_cart_rules")
        .select(
            SMART_CART_RULE_SELECT
        )
        .eq(
            "id",
            rule_id,
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Smart Cart rule not found",
        )

    return response.data[0]


def list_triggered_auto_buy_rules(
) -> list[dict]:
    """
    Internal worker query.

    Only rules that the deterministic database evaluator
    has already placed into the 'triggered' state and that
    have explicit 'auto_buy' authorization are returned.
    """
    response = (
        supabase_admin
        .table("smart_cart_rules")
        .select(
            SMART_CART_RULE_SELECT
        )
        .eq(
            "status",
            "triggered",
        )
        .eq(
            "authorization_mode",
            "auto_buy",
        )
        .order(
            "triggered_at",
            desc=False,
        )
        .execute()
    )

    return response.data or []