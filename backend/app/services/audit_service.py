from __future__ import annotations

import logging
from typing import Any

from app.core.supabase_client import supabase_admin

logger = logging.getLogger(__name__)

MAX_LIMIT = 200

ACTOR_TYPES = ("user", "staff", "agent", "system")


class AuditServiceError(Exception):
    """Raised when the audit log cannot be read."""


def _escape_like(value: str) -> str:
    """Escape % and _ so user input is matched literally."""

    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def list_audit_logs(
    *,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_user_id: str | None = None,
    actor_type: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """
    Read-only, newest-first view of audit_logs for the admin page.

    The audit log is append-only at the database level (Phase 16); this
    service deliberately exposes no write path.
    """

    safe_limit = max(1, min(int(limit), MAX_LIMIT))
    safe_offset = max(0, int(offset))

    try:
        query = (
            supabase_admin
            .table("audit_logs")
            .select("*, actor:profiles(full_name)", count="exact")
        )

        if action:
            # Prefix match, so "role_" finds role_granted/role_revoked/...
            query = query.ilike("action", _escape_like(action) + "%")

        if entity_type:
            query = query.eq("entity_type", entity_type)

        if entity_id:
            query = query.eq("entity_id", entity_id)

        if actor_user_id:
            query = query.eq("actor_user_id", actor_user_id)

        if actor_type:
            query = query.eq("actor_type", actor_type)

        if since:
            query = query.gte("created_at", since)

        if until:
            query = query.lte("created_at", until)

        response = (
            query
            .order("created_at", desc=True)
            .order("id", desc=True)
            .range(safe_offset, safe_offset + safe_limit - 1)
            .execute()
        )

    except Exception as exc:
        logger.exception("Could not read audit_logs")
        raise AuditServiceError(
            "Could not load the audit log."
        ) from exc

    entries = []

    for row in response.data or []:
        actor = row.pop("actor", None) or {}

        entries.append(
            {
                **row,
                "id": str(row["id"]),
                "actor_user_id": (
                    str(row["actor_user_id"])
                    if row.get("actor_user_id")
                    else None
                ),
                "entity_id": (
                    str(row["entity_id"])
                    if row.get("entity_id")
                    else None
                ),
                "actor_name": actor.get("full_name"),
                "metadata": row.get("metadata") or {},
            }
        )

    return {
        "entries": entries,
        "total": int(response.count or len(entries)),
        "limit": safe_limit,
        "offset": safe_offset,
    }
