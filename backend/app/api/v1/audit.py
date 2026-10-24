from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import require_admin
from app.schemas.audit import AuditLogListResponse
from app.services import audit_service
from app.services.audit_service import ACTOR_TYPES, AuditServiceError

router = APIRouter(
    prefix="/api/v1/admin/audit-logs",
    tags=["audit"],
)


@router.get("", response_model=AuditLogListResponse)
def get_audit_logs(
    action: str | None = Query(default=None, max_length=100),
    entity_type: str | None = Query(default=None, max_length=100),
    entity_id: UUID | None = None,
    actor_user_id: UUID | None = None,
    actor_type: str | None = Query(default=None, max_length=20),
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _role: str = Depends(require_admin),
) -> dict:
    """
    Read-only audit trail. Administrators only: the log contains role
    changes and staff activity. The log itself is append-only in the
    database (see migration 20261026000000).
    """

    if actor_type is not None and actor_type not in ACTOR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"actor_type must be one of: {', '.join(ACTOR_TYPES)}",
        )

    try:
        return audit_service.list_audit_logs(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            actor_user_id=str(actor_user_id) if actor_user_id else None,
            actor_type=actor_type,
            since=since.isoformat() if since else None,
            until=until.isoformat() if until else None,
            limit=limit,
            offset=offset,
        )
    except AuditServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
