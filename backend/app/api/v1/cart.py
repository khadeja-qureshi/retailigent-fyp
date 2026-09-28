from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Response,
    status,
)

from app.core.auth import get_current_user_id
from app.schemas.cart import (
    AddCartItemRequest,
    UpdateCartItemRequest,
)
from app.services.cart_service import (
    add_cart_item,
    delete_cart_item,
    get_cart_summary,
    update_cart_item,
)


router = APIRouter(
    prefix="/api/v1/cart",
    tags=["Cart"],
)


@router.get("")
def get_cart(
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    return get_cart_summary(customer_id)


@router.post(
    "/items",
    status_code=status.HTTP_201_CREATED,
)
def add_item(
    payload: AddCartItemRequest,
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    return add_cart_item(
        customer_id=customer_id,
        variant_id=str(payload.variant_id),
        quantity=payload.quantity,
    )


@router.patch("/items/{item_id}")
def update_item(
    item_id: UUID,
    payload: UpdateCartItemRequest,
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    return update_cart_item(
        customer_id=customer_id,
        item_id=str(item_id),
        quantity=payload.quantity,
    )


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_item(
    item_id: UUID,
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    delete_cart_item(
        customer_id=customer_id,
        item_id=str(item_id),
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )