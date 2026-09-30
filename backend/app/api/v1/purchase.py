from fastapi import APIRouter, Depends

from app.api.v1.auth import get_current_user_id
from app.schemas.purchase import (
    MockPurchaseRequest,
    PurchaseResponse,
    ReservationPurchaseRequest,
)

from app.agents.purchase_agent import purchase_agent

router = APIRouter(
    prefix="/purchases",
    tags=["purchases"],
)


@router.post(
    "",
    response_model=PurchaseResponse,
)
def create_purchase(
    request: MockPurchaseRequest,
    customer_id: str = Depends(get_current_user_id),
):
    result = purchase_agent.purchase_direct(
        customer_id=customer_id,
        variant_id=request.variant_id,
        quantity=request.quantity,
        idempotency_key=request.idempotency_key,
        branch_id=request.branch_id,
        smart_cart_rule_id=request.smart_cart_rule_id,
)
    return result


@router.post(
    "/from-reservation",
    response_model=PurchaseResponse,
)
def purchase_from_reservation(
    request: ReservationPurchaseRequest,
    customer_id: str = Depends(get_current_user_id),
):
    result = purchase_agent.purchase_from_reservation(
        customer_id=customer_id,
        reservation_id=request.reservation_id,
        idempotency_key=request.idempotency_key,
        quantity=request.quantity,
)

    return result