import logging
import smtplib
from email.message import EmailMessage

from fastapi import HTTPException

from app.config import settings
from app.core.supabase_client import supabase_admin


logger = logging.getLogger(__name__)

NOTIFICATION_SELECT = (
    "id, type, title, message, metadata, read_at, created_at"
)


# ---------------------------------------------------------------------------
# Customer-facing reads / actions
# ---------------------------------------------------------------------------

def count_unread(customer_id: str) -> int:
    try:
        response = (
            supabase_admin
            .table("notifications")
            .select("id", count="exact")
            .eq("customer_id", customer_id)
            .is_("read_at", "null")
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return int(response.count or 0)


def list_notifications(
    customer_id: str,
    unread_only: bool = False,
    limit: int = 50,
) -> dict:
    limit = max(1, min(limit, 100))

    try:
        query = (
            supabase_admin
            .table("notifications")
            .select(NOTIFICATION_SELECT)
            .eq("customer_id", customer_id)
            .order("created_at", desc=True)
            .limit(limit)
        )

        if unread_only:
            query = query.is_("read_at", "null")

        response = query.execute()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    rows = response.data or []

    return {
        "type": "notification_list",
        "notifications": [
            {
                "id": str(row["id"]),
                "type": row["type"],
                "title": row["title"],
                "message": row["message"],
                "metadata": row.get("metadata") or {},
                "read_at": row.get("read_at"),
                "created_at": row["created_at"],
            }
            for row in rows
        ],
        "unread_count": count_unread(customer_id),
    }


def mark_read(
    customer_id: str,
    notification_ids: list[str] | None = None,
) -> dict:
    try:
        response = supabase_admin.rpc(
            "mark_notifications_read",
            {
                "p_customer_id": customer_id,
                "p_notification_ids": notification_ids,
            },
        ).execute()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "updated": int(response.data or 0),
        "unread_count": count_unread(customer_id),
    }


# ---------------------------------------------------------------------------
# Delivery pipeline (used by the worker)
# ---------------------------------------------------------------------------

def claim_deliveries() -> list[dict]:
    response = supabase_admin.rpc(
        "claim_notification_deliveries",
        {
            "p_limit": settings.notification_batch_size,
            "p_max_attempts": settings.notification_max_attempts,
            "p_base_backoff_seconds": settings.notification_backoff_seconds,
        },
    ).execute()

    return response.data or []


def _get_notification(notification_id: str) -> dict | None:
    response = (
        supabase_admin
        .table("notifications")
        .select("id, customer_id, type, title, message, metadata")
        .eq("id", notification_id)
        .limit(1)
        .execute()
    )

    return response.data[0] if response.data else None


def _get_customer_email(customer_id: str) -> str | None:
    response = supabase_admin.auth.admin.get_user_by_id(customer_id)
    user = getattr(response, "user", None)

    return getattr(user, "email", None) if user else None


def _email_allowed(customer_id: str) -> bool:
    """
    Email is opt-in: customer_preferences.allow_email_notifications.
    """
    response = (
        supabase_admin
        .table("customer_preferences")
        .select("allow_email_notifications")
        .eq("customer_id", customer_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        return False

    return bool(response.data[0]["allow_email_notifications"])


def send_email(to_address: str, subject: str, body: str) -> None:
    if settings.email_backend == "smtp":
        message = EmailMessage()
        message["From"] = settings.email_from
        message["To"] = to_address
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=15,
        ) as server:
            if settings.smtp_use_tls:
                server.starttls()

            if settings.smtp_username:
                server.login(
                    settings.smtp_username,
                    settings.smtp_password,
                )

            server.send_message(message)
        return

    # Dev backend: no external dependency.
    logger.info(
        "[email:log] to=%s subject=%s body=%s",
        to_address,
        subject,
        body,
    )


def deliver(delivery: dict) -> None:
    """
    Deliver one claimed delivery row.
    Raises on failure so the caller can record it.
    """
    notification = _get_notification(str(delivery["notification_id"]))

    if notification is None:
        raise ValueError("Notification no longer exists")

    channel = delivery["channel"]

    if channel == "in_app":
        # The notifications row itself is what the customer sees;
        # nothing further to push.
        return

    if channel == "email":
        customer_id = str(notification["customer_id"])

        if not _email_allowed(customer_id):
            # Customer has not opted in. Treated as delivered-by-skip
            # so it is not retried forever.
            logger.info(
                "Email skipped (no opt-in) for notification %s",
                notification["id"],
            )
            return

        address = _get_customer_email(customer_id)

        if not address:
            raise ValueError("Customer has no email address")

        send_email(
            address,
            notification["title"],
            notification["message"],
        )
        return

    raise ValueError(f"Unsupported channel: {channel}")


def complete_delivery(delivery_id: str) -> None:
    supabase_admin.rpc(
        "complete_notification_delivery",
        {"p_delivery_id": delivery_id},
    ).execute()


def fail_delivery(delivery_id: str, error: str) -> None:
    supabase_admin.rpc(
        "fail_notification_delivery",
        {"p_delivery_id": delivery_id, "p_error": error},
    ).execute()
