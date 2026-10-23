from __future__ import annotations

import logging
from typing import Any

from app.core.supabase_client import supabase_admin

logger = logging.getLogger(__name__)

PRIORITY_ORDER = {
    "urgent": 0,
    "high": 1,
    "normal": 2,
    "low": 3,
}


class SupportAdminServiceError(Exception):
    """Raised when a staff support operation fails."""


def list_support_tickets(
    *,
    status: str | None = None,
    priority: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return a bounded staff ticket queue in priority order."""

    safe_limit = max(1, min(limit, 100))

    try:
        query = (
            supabase_admin
            .table("support_escalations")
            .select("*")
        )

        if status is not None:
            query = query.eq("status", status)

        if priority is not None:
            query = query.eq("priority", priority)

        response = (
            query
            .order("updated_at", desc=True)
            .limit(safe_limit)
            .execute()
        )

        tickets = list(response.data or [])

        # Sort timestamps first, newest first. Python's sort is stable,
        # so sorting by priority afterwards preserves timestamp order
        # among tickets with the same priority.
        tickets.sort(
            key=lambda ticket: str(ticket.get("updated_at") or ""),
            reverse=True,
        )
        tickets.sort(
            key=lambda ticket: PRIORITY_ORDER.get(
                str(ticket.get("priority", "normal")).lower(),
                2,
            )
        )

        return tickets

    except Exception as exc:
        logger.exception("Could not load the staff support queue.")
        raise SupportAdminServiceError(
            "The support ticket queue could not be loaded."
        ) from exc


def get_support_ticket(
    ticket_id: str,
) -> dict[str, Any] | None:
    """Fetch one support ticket for the staff detail view."""

    if not ticket_id.strip():
        raise ValueError("A ticket ID is required.")

    try:
        response = (
            supabase_admin
            .table("support_escalations")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )

        rows = response.data or []
        return rows[0] if rows else None

    except Exception as exc:
        logger.exception("Could not load support ticket %s.", ticket_id)
        raise SupportAdminServiceError(
            "The support ticket could not be loaded."
        ) from exc


def list_support_ticket_messages(
    ticket_id: str,
) -> list[dict[str, Any]]:
    """Fetch the conversation for a ticket in chronological order."""

    if not ticket_id.strip():
        raise ValueError("A ticket ID is required.")

    try:
        response = (
            supabase_admin
            .table("support_ticket_messages")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order("created_at", desc=False)
            .limit(500)
            .execute()
        )

        return list(response.data or [])

    except Exception as exc:
        logger.exception(
            "Could not load messages for support ticket %s.",
            ticket_id,
        )
        raise SupportAdminServiceError(
            "The support ticket conversation could not be loaded."
        ) from exc

SUPPORT_STATUSES = {
    "open",
    "in_progress",
    "waiting_customer",
    "escalated",
    "resolved",
    "closed",
}

SUPPORT_PRIORITIES = {
    "low",
    "normal",
    "high",
    "urgent",
}


def update_support_ticket(
    *,
    ticket_id: str,
    status: str | None = None,
    priority: str | None = None,
    assigned_staff_id: str | None = None,
    update_assignment: bool = False,
) -> dict[str, Any] | None:
    """Update staff-managed ticket fields.

    Set update_assignment=True to assign or explicitly unassign a ticket.
    Returns None if the ticket does not exist.
    """

    if not ticket_id.strip():
        raise ValueError("A ticket ID is required.")

    payload: dict[str, Any] = {}

    if status is not None:
        if status not in SUPPORT_STATUSES:
            raise ValueError("Unsupported support ticket status.")
        payload["status"] = status

    if priority is not None:
        if priority not in SUPPORT_PRIORITIES:
            raise ValueError("Unsupported support ticket priority.")
        payload["priority"] = priority

    if update_assignment:
        payload["assigned_staff_id"] = assigned_staff_id

    if not payload:
        raise ValueError("At least one ticket field must be updated.")

    try:
        response = (
            supabase_admin
            .table("support_escalations")
            .update(payload)
            .eq("id", ticket_id)
            .execute()
        )

        rows = response.data or []
        return rows[0] if rows else None

    except Exception as exc:
        logger.exception("Could not update support ticket %s.", ticket_id)
        raise SupportAdminServiceError(
            "The support ticket could not be updated."
        ) from exc


def add_staff_ticket_message(
    *,
    ticket_id: str,
    staff_id: str,
    message: str,
) -> dict[str, Any]:
    """Persist a reply from an authenticated staff member."""

    clean_message = message.strip()[:4000]

    if not ticket_id.strip():
        raise ValueError("A ticket ID is required.")

    if not staff_id.strip():
        raise ValueError("A staff ID is required.")

    if not clean_message:
        raise ValueError("A non-empty reply is required.")

    try:
        response = (
            supabase_admin
            .table("support_ticket_messages")
            .insert(
                {
                    "ticket_id": ticket_id,
                    "sender_id": staff_id,
                    "sender_type": "staff",
                    "message": clean_message,
                }
            )
            .execute()
        )

        rows = response.data or []
        if not rows:
            raise SupportAdminServiceError(
                "The staff reply was not returned after creation."
            )

        return rows[0]

    except SupportAdminServiceError:
        raise
    except Exception as exc:
        logger.exception(
            "Could not add staff reply to ticket %s.",
            ticket_id,
        )
        raise SupportAdminServiceError(
            "The staff reply could not be saved."
        ) from exc
