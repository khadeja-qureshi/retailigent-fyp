from fastapi import APIRouter, Depends, Query

from app.core.auth import get_current_user_id, require_customer
from app.schemas.notification import (
    MarkReadRequest,
    MarkReadResponse,
    NotificationListResponse,
    UnreadCountResponse,
    EmailNotificationPreference,
    EmailNotificationPreferenceUpdate,
)
from app.services.notification_service import (
    count_unread,
    get_email_notification_preference,
    list_notifications,
    mark_read,
    set_email_notification_preference,
)


router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["Notifications"],
)


@router.get(
    "/preferences",
    response_model=EmailNotificationPreference,
)
def get_notification_preferences(
    customer_id: str = Depends(get_current_user_id),
    _role: str = Depends(require_customer),
):
    return get_email_notification_preference(customer_id)


@router.patch(
    "/preferences",
    response_model=EmailNotificationPreference,
)
def update_notification_preferences(
    payload: EmailNotificationPreferenceUpdate,
    customer_id: str = Depends(get_current_user_id),
    _role: str = Depends(require_customer),
):
    return set_email_notification_preference(
        customer_id,
        payload.allow_email_notifications,
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
