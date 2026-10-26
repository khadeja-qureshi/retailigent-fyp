from __future__ import annotations

from typing import Any

from app.core.supabase_client import supabase_admin


class SupportTicketError(Exception):
    """Raised when a support ticket operation cannot be completed safely."""


def get_latest_open_support_ticket(
    customer_id: str,
) -> dict[str, Any] | None:
    """
    Return the customer's most recently updated unresolved support ticket.

    Resolved and closed tickets are intentionally excluded.
    """

    try:
        response = (
            supabase_admin
            .table(
                "support_escalations"
            )
            .select(
                "id, customer_id, conversation_id, subject, description, "
                "status, priority, sentiment, assigned_staff_id, "
                "handoff_summary, agent_context, created_at, updated_at"
            )
            .eq(
                "customer_id",
                customer_id,
            )
            .in_(
                "status",
                [
                    "open",
                    "in_progress",
                    "waiting_customer",
                    "escalated",
                ],
            )
            .order(
                "updated_at",
                desc=True,
            )
            .limit(
                1
            )
            .execute()
        )

    except Exception as exc:
        raise SupportTicketError(
            "Unable to load the customer's open support ticket."
        ) from exc

    rows = (
        response.data
        or []
    )

    if not rows:
        return None

    return rows[0]


def add_customer_support_message(
    *,
    customer_id: str,
    ticket_id: str,
    message: str,
) -> dict[str, Any]:
    """
    Append a customer's follow-up message to an existing ticket.

    Ownership is verified before insertion so a customer cannot append a
    message to another customer's support ticket through the trusted backend.
    """

    clean_message = (
        " ".join(
            message.split()
        )[:4000]
    )

    if not clean_message:
        raise ValueError(
            "A support message is required."
        )

    try:
        ticket_response = (
            supabase_admin
            .table(
                "support_escalations"
            )
            .select(
                "id, customer_id, status, subject, priority, sentiment, "
                "assigned_staff_id, created_at, updated_at"
            )
            .eq(
                "id",
                ticket_id,
            )
            .eq(
                "customer_id",
                customer_id,
            )
            .limit(
                1
            )
            .execute()
        )

        rows = (
            ticket_response.data
            or []
        )

        if not rows:
            raise SupportTicketError(
                "The support ticket was not found."
            )

        ticket = rows[0]

        if str(
            ticket.get(
                "status"
            )
            or ""
        ).casefold() in {
            "resolved",
            "closed",
        }:
            raise SupportTicketError(
                "The support ticket is already closed."
            )

        message_result = (
            supabase_admin
            .table(
                "support_ticket_messages"
            )
            .insert(
                {
                    "ticket_id": ticket_id,
                    "sender_id": customer_id,
                    "sender_type": "customer",
                    "message": clean_message,
                }
            )
            .execute()
        )

        if not message_result.data:
            raise SupportTicketError(
                "The support follow-up message was not persisted."
            )

        return ticket

    except SupportTicketError:
        raise

    except Exception as exc:
        raise SupportTicketError(
            "Unable to update the support ticket."
        ) from exc


def create_support_ticket(
    *,
    customer_id: str,
    conversation_id: str,
    subject: str,
    description: str,
    sentiment: str | None = None,
    priority: str = "normal",
    handoff_summary: str | None = None,
    agent_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a customer-owned ticket and its initial customer message."""

    clean_subject = (
        subject.strip()[:200]
    )

    clean_description = (
        description.strip()[:4000]
    )

    if not clean_subject:
        raise ValueError(
            "A support ticket subject is required."
        )

    if not clean_description:
        raise ValueError(
            "A support ticket description is required."
        )

    ticket_id: (
        str | None
    ) = None

    try:
        ticket_result = (
            supabase_admin
            .table(
                "support_escalations"
            )
            .insert(
                {
                    "customer_id": customer_id,
                    "conversation_id": conversation_id,
                    "subject": clean_subject,
                    "description": clean_description,
                    "status": "open",
                    "priority": priority,
                    "sentiment": sentiment,
                    "handoff_summary": (
                        handoff_summary[:4000]
                        if handoff_summary
                        else None
                    ),
                    "agent_context": (
                        agent_context
                        or {}
                    ),
                }
            )
            .execute()
        )

        ticket_rows = (
            ticket_result.data
            or []
        )

        if (
            not ticket_rows
            or not ticket_rows[0].get(
                "id"
            )
        ):
            raise SupportTicketError(
                "The support ticket was not returned after creation."
            )

        ticket = (
            ticket_rows[0]
        )

        ticket_id = str(
            ticket[
                "id"
            ]
        )

        message_result = (
            supabase_admin
            .table(
                "support_ticket_messages"
            )
            .insert(
                {
                    "ticket_id": ticket_id,
                    "sender_id": customer_id,
                    "sender_type": "customer",
                    "message": clean_description,
                }
            )
            .execute()
        )

        if not message_result.data:
            raise SupportTicketError(
                "The initial support message was not persisted."
            )

        return {
            "ticket_id": ticket_id,
            "status": ticket.get(
                "status",
                "open",
            ),
            "subject": ticket.get(
                "subject",
                clean_subject,
            ),
        }

    except SupportTicketError:
        if ticket_id is not None:
            try:
                (
                    supabase_admin
                    .table(
                        "support_escalations"
                    )
                    .delete()
                    .eq(
                        "id",
                        ticket_id,
                    )
                    .eq(
                        "customer_id",
                        customer_id,
                    )
                    .execute()
                )

            except Exception:
                pass

        raise

    except Exception as exc:
        if ticket_id is not None:
            try:
                (
                    supabase_admin
                    .table(
                        "support_escalations"
                    )
                    .delete()
                    .eq(
                        "id",
                        ticket_id,
                    )
                    .eq(
                        "customer_id",
                        customer_id,
                    )
                    .execute()
                )

            except Exception:
                pass

        raise SupportTicketError(
            "Unable to create the support ticket."
        ) from exc
