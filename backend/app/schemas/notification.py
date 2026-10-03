from typing import Literal, Optional

from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: str
    type: str
    title: str
    message: str
    metadata: dict = Field(default_factory=dict)
    read_at: Optional[str] = None
    created_at: str


class NotificationListResponse(BaseModel):
    type: Literal["notification_list"] = "notification_list"
    notifications: list[NotificationResponse]
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkReadRequest(BaseModel):
    notification_ids: Optional[list[str]] = None


class MarkReadResponse(BaseModel):
    updated: int
    unread_count: int
