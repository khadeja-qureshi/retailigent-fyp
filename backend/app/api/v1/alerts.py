from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    status,
)

from app.core.auth import get_current_user_id
from app.schemas.alert import CreateAlertRequest
from app.agents.alert_agent import alert_agent


router = APIRouter(
    prefix="/api/v1/alerts",
    tags=["Alerts"],
)


@router.get("")
def list_alerts(
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    """
    Return all alerts owned by the
    authenticated customer.
    """
    return alert_agent.list(
        customer_id=customer_id,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_alert(
    payload: CreateAlertRequest,
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    """
    Create a customer alert.

    Supported alert types:
    - price_drop
    - restock
    - sale
    """
    return alert_agent.create(
        customer_id=customer_id,
        variant_id=str(
            payload.variant_id
        ),
        alert_type=payload.alert_type,
        target_price=payload.target_price,
    )


@router.post(
    "/{alert_id}/pause",
)
def pause_alert(
    alert_id: UUID,
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    """
    Pause an active alert.
    """
    return alert_agent.pause(
        customer_id=customer_id,
        alert_id=str(alert_id),
    )


@router.post(
    "/{alert_id}/resume",
)
def resume_alert(
    alert_id: UUID,
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    """
    Resume a paused alert.

    A previously triggered one-shot alert should
    not be resumed; a new alert should be created.
    """
    return alert_agent.resume(
        customer_id=customer_id,
        alert_id=str(alert_id),
    )


@router.delete(
    "/{alert_id}",
)
def cancel_alert(
    alert_id: UUID,
    customer_id: str = Depends(
        get_current_user_id
    ),
):
    """
    Cancel/delete a customer-owned alert.
    """
    return alert_agent.cancel(
        customer_id=customer_id,
        alert_id=str(alert_id),
    )