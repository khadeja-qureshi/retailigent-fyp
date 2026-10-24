from typing import Any, Optional

from pydantic import BaseModel, Field


class AuditLogEntry(BaseModel):
    id: str
    created_at: str
    actor_user_id: Optional[str] = None
    actor_name: Optional[str] = None
    actor_type: str
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    before_data: Optional[dict[str, Any]] = None
    after_data: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditLogListResponse(BaseModel):
    entries: list[AuditLogEntry]
    total: int
    limit: int
    offset: int
