from fastapi import APIRouter, Depends

from app.api.v1.auth import get_current_user_id
from app.schemas.order import OrderResponse
from app.services.order_service import get_customer_orders


router = APIRouter(
    prefix="/api/v1/orders",
    tags=["orders"],
)


@router.get(
    "",
    response_model=list[OrderResponse],
)
def list_orders(
    customer_id: str = Depends(get_current_user_id),
):
    return get_customer_orders(customer_id)