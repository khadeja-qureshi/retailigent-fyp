from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


SupportStatus = Literal[
    "open",
    "in_progress",
    "waiting_customer",
    "escalated",
    "resolved",
    "closed",
]

SupportPriority = Literal[
    "low",
    "normal",
    "high",
    "urgent",
]


class SupportTicketUpdate(BaseModel):
    status: SupportStatus | None = None
    priority: SupportPriority | None = None
    assigned_staff_id: UUID | None = None


class StaffTicketReply(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A non-empty reply is required.")
        return value
