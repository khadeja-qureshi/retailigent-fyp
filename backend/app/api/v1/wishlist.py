from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Response,
    status,
)

from app.core.auth import get_current_user_id
from app.schemas.wishlist import (
    AddWishlistItemRequest,
)
from app.services.wishlist_service import (
    add_wishlist_item,
    delete_wishlist_item,
    get_wishlist,
)


router = APIRouter(
    prefix="/api/v1/wishlist",
    tags=["Wishlist"],
)


@router.get("")
def list_wishlist(
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    return get_wishlist(customer_id)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def add_to_wishlist(
    payload: AddWishlistItemRequest,
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    return add_wishlist_item(
        customer_id=customer_id,
        variant_id=str(payload.variant_id),
    )


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_from_wishlist(
    item_id: UUID,
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    delete_wishlist_item(
        customer_id=customer_id,
        item_id=str(item_id),
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )