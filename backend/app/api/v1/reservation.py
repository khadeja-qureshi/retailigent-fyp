from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    status,
)

from app.core.auth import get_current_user_id
from app.schemas.reservation import (
    CreateReservationRequest,
)
from app.services.reservation_service import (
    create_customer_reservation,
    get_customer_reservations,
    release_customer_reservation,
)


router = APIRouter(
    prefix="/api/v1/reservations",
    tags=["Reservations"],
)


@router.get("")
def list_reservations(
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    return get_customer_reservations(
        customer_id
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_reservation(
    payload: CreateReservationRequest,
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    return create_customer_reservation(
        customer_id=customer_id,
        variant_id=str(payload.variant_id),
        branch_id=str(payload.branch_id),
        quantity=payload.quantity,
        hold_minutes=payload.hold_minutes,
    )


@router.delete(
    "/{reservation_id}",
)
def release_reservation(
    reservation_id: UUID,
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    return release_customer_reservation(
        customer_id=customer_id,
        reservation_id=str(reservation_id),
    )