from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import get_current_user_id, require_staff
from app.schemas.support import (
    StaffTicketReply,
    SupportPriority,
    SupportStatus,
    SupportTicketUpdate,
)
from app.services import support_admin_service
from app.services.support_admin_service import SupportAdminServiceError

router = APIRouter(
    prefix="/api/v1/support",
    tags=["support"],
)


@router.get("/tickets")
def list_tickets(
    ticket_status: SupportStatus | None = Query(default=None, alias="status"),
    priority: SupportPriority | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    _role: str = Depends(require_staff),
) -> dict:
    try:
        tickets = support_admin_service.list_support_tickets(
            status=ticket_status,
            priority=priority,
            limit=limit,
        )
        return {"tickets": tickets, "count": len(tickets)}
    except SupportAdminServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: UUID,
    _role: str = Depends(require_staff),
) -> dict:
    try:
        ticket = support_admin_service.get_support_ticket(str(ticket_id))
        if ticket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Support ticket not found.",
            )
        return ticket
    except SupportAdminServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/tickets/{ticket_id}/messages")
def get_ticket_messages(
    ticket_id: UUID,
    _role: str = Depends(require_staff),
) -> dict:
    try:
        ticket = support_admin_service.get_support_ticket(str(ticket_id))
        if ticket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Support ticket not found.",
            )

        messages = support_admin_service.list_support_ticket_messages(
            str(ticket_id)
        )
        return {"messages": messages, "count": len(messages)}
    except SupportAdminServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.patch("/tickets/{ticket_id}")
def update_ticket(
    ticket_id: UUID,
    request: SupportTicketUpdate,
    _role: str = Depends(require_staff),
) -> dict:
    fields = request.model_fields_set
    update_assignment = "assigned_staff_id" in fields

    if not fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one ticket field must be provided.",
        )

    try:
        ticket = support_admin_service.update_support_ticket(
            ticket_id=str(ticket_id),
            status=request.status,
            priority=request.priority,
            assigned_staff_id=(
                str(request.assigned_staff_id)
                if request.assigned_staff_id is not None
                else None
            ),
            update_assignment=update_assignment,
        )

        if ticket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Support ticket not found.",
            )
        return ticket
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except SupportAdminServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post(
    "/tickets/{ticket_id}/messages",
    status_code=status.HTTP_201_CREATED,
)
def reply_to_ticket(
    ticket_id: UUID,
    request: StaffTicketReply,
    staff_id: str = Depends(get_current_user_id),
    _role: str = Depends(require_staff),
) -> dict:
    try:
        ticket = support_admin_service.get_support_ticket(str(ticket_id))
        if ticket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Support ticket not found.",
            )

        return support_admin_service.add_staff_ticket_message(
            ticket_id=str(ticket_id),
            staff_id=staff_id,
            message=request.message,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except SupportAdminServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
