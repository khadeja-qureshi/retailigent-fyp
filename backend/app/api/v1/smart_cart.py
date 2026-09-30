from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    status,
)

from app.core.auth import get_current_user_id
from app.schemas.smart_cart import (
    CreateSmartCartRuleRequest,
)
from app.services.smart_cart_service import (
    cancel_customer_smart_cart_rule,
    create_customer_smart_cart_rule,
    get_customer_smart_cart_rule,
    list_customer_smart_cart_rules,
    pause_customer_smart_cart_rule,
    resume_customer_smart_cart_rule,
)


router = APIRouter(
    prefix="/api/v1/smart-cart",
    tags=["Smart Cart"],
)


@router.get("")
def list_smart_cart_rules(
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    """
    Return all Smart Cart rules owned by the
    authenticated customer.
    """
    return list_customer_smart_cart_rules(
        customer_id=customer_id,
    )


@router.get("/{rule_id}")
def get_smart_cart_rule(
    rule_id: UUID,
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    """
    Return one Smart Cart rule owned by the
    authenticated customer.
    """
    return get_customer_smart_cart_rule(
        customer_id=customer_id,
        rule_id=str(rule_id),
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_smart_cart_rule(
    payload: CreateSmartCartRuleRequest,
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    """
    Create a Smart Cart rule.

    The customer controls the condition and whether
    it is notify-only or auto-buy.

    System-managed state such as triggered/completed
    cannot be supplied by the client.
    """
    return create_customer_smart_cart_rule(
        customer_id=customer_id,
        variant_id=str(
            payload.variant_id
        ),
        branch_id=(
            str(payload.branch_id)
            if payload.branch_id
            else None
        ),
        quantity=payload.quantity,
        target_price=payload.target_price,
        min_discount_percentage=(
            payload.min_discount_percentage
        ),
        authorization_mode=(
            payload.authorization_mode
        ),
    )


@router.post(
    "/{rule_id}/pause",
)
def pause_smart_cart_rule(
    rule_id: UUID,
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    """
    Pause an active Smart Cart rule.
    """
    return pause_customer_smart_cart_rule(
        customer_id=customer_id,
        rule_id=str(rule_id),
    )


@router.post(
    "/{rule_id}/resume",
)
def resume_smart_cart_rule(
    rule_id: UUID,
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    """
    Resume a paused Smart Cart rule.
    """
    return resume_customer_smart_cart_rule(
        customer_id=customer_id,
        rule_id=str(rule_id),
    )


@router.post(
    "/{rule_id}/cancel",
)
def cancel_smart_cart_rule(
    rule_id: UUID,
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    """
    Cancel an active or paused Smart Cart rule.

    Triggered/completed rules remain system-managed.
    """
    return cancel_customer_smart_cart_rule(
        customer_id=customer_id,
        rule_id=str(rule_id),
    )