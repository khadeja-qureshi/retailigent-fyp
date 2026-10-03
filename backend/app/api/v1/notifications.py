from fastapi import APIRouter, Depends, Query

from app.core.auth import get_current_user_id
from app.schemas.notification import (
    MarkReadRequest,
    MarkReadResponse,
    NotificationListResponse,
    UnreadCountResponse,
)
from app.services.notification_service import (
    count_unread,
    list_notifications,
    mark_read,
)


router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["Notifications"],
)


@router.get("", response_model=NotificationListResponse)
def get_notifications(
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    customer_id: str = Depends(get_current_user_id),
):
    return list_notifications(
        customer_id=customer_id,
        unread_only=unread_only,
        limit=limit,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    customer_id: str = Depends(get_current_user_id),
):
    return {"unread_count": count_unread(customer_id)}


@router.post("/read", response_model=MarkReadResponse)
def mark_notifications_read(
    payload: MarkReadRequest,
    customer_id: str = Depends(get_current_user_id),
):
    """
    Mark specific notifications read, or all when
    notification_ids is omitted.
    """
    return mark_read(
        customer_id=customer_id,
        notification_ids=payload.notification_ids,
    )
