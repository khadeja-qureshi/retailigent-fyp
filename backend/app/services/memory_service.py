from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import Any

from fastapi import HTTPException

from app.config import settings
from app.core.supabase_client import (
    supabase_admin,
)


VALID_MEMORY_TYPES = {
    "product_interest",
    "occasion_context",
    "communication_style",
    "fabric_or_style_note",
    "other",
}


def _parse_datetime(
    value: str | None,
) -> datetime | None:
    if not value:
        return None

    normalized = value.strip()

    if normalized.endswith("Z"):
        normalized = (
            normalized[:-1]
            + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            normalized
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def _apply_memory_staleness(
    snapshot: dict,
) -> dict:
    """
    Apply application-configurable staleness rules.

    The database currently returns stale/effective-confidence
    values too, but Phase 12 requires the window to be
    configurable. The application layer therefore becomes
    authoritative for the values exposed to agents.
    """

    now = datetime.now(
        timezone.utc
    )

    stale_cutoff = (
        now
        - timedelta(
            days=settings.memory_stale_days
        )
    )

    multiplier = max(
        0.0,
        min(
            1.0,
            settings
            .memory_stale_confidence_multiplier,
        ),
    )

    facts = []

    for row in (
        snapshot.get(
            "remembered_facts"
        )
        or []
    ):
        fact = dict(row)

        confidence = float(
            fact.get("confidence")
            or 0.0
        )

        last_confirmed = (
            _parse_datetime(
                fact.get(
                    "last_confirmed_at"
                )
            )
        )

        is_stale = (
            last_confirmed is None
            or last_confirmed
            < stale_cutoff
        )

        effective_confidence = (
            confidence * multiplier
            if is_stale
            else confidence
        )

        fact["is_stale"] = (
            is_stale
        )

        fact[
            "effective_confidence"
        ] = round(
            max(
                0.0,
                min(
                    1.0,
                    effective_confidence,
                ),
            ),
            4,
        )

        facts.append(
            fact
        )

    facts.sort(
        key=lambda fact: (
            float(
                fact.get(
                    "effective_confidence"
                )
                or 0.0
            ),
            str(
                fact.get(
                    "last_confirmed_at"
                )
                or ""
            ),
        ),
        reverse=True,
    )

    enriched = dict(
        snapshot
    )

    enriched[
        "remembered_facts"
    ] = facts

    enriched[
        "memory_policy"
    ] = {
        "stale_after_days":
            settings.memory_stale_days,
        "stale_confidence_multiplier":
            multiplier,
    }

    return enriched


def get_customer_context_snapshot(
    customer_id: str,
) -> dict:
    """
    Load the durable context used at the beginning
    of a new conversation.
    """

    try:
        response = (
            supabase_admin
            .rpc(
                "get_customer_context_snapshot",
                {
                    "p_customer_id":
                        customer_id,
                },
            )
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    snapshot = response.data

    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Customer context "
                "could not be found."
            ),
        )

    if not isinstance(
        snapshot,
        dict,
    ):
        raise HTTPException(
            status_code=500,
            detail=(
                "Customer context snapshot "
                "returned an invalid payload."
            ),
        )

    return _apply_memory_staleness(
        snapshot
    )


def upsert_customer_memory(
    customer_id: str,
    *,
    memory_type: str,
    memory_key: str,
    memory_value: Any,
    confidence: float = 1.0,
    source_conversation_id: (
        str | None
    ) = None,
) -> str:
    """
    Store or refresh one durable fact.

    Memory writes are performed only through the
    service-role RPC.
    """

    if memory_type not in (
        VALID_MEMORY_TYPES
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported memory type."
            ),
        )

    memory_key = (
        memory_key.strip()
    )

    if not memory_key:
        raise HTTPException(
            status_code=400,
            detail=(
                "Memory key is required."
            ),
        )

    if not (
        0.0
        <= confidence
        <= 1.0
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Memory confidence must "
                "be between 0 and 1."
            ),
        )

    try:
        response = (
            supabase_admin
            .rpc(
                "upsert_customer_memory",
                {
                    "p_customer_id":
                        customer_id,
                    "p_memory_type":
                        memory_type,
                    "p_memory_key":
                        memory_key,
                    "p_memory_value":
                        memory_value,
                    "p_confidence":
                        confidence,
                    "p_source_conversation_id":
                        source_conversation_id,
                },
            )
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    memory_id = response.data

    if not memory_id:
        raise HTTPException(
            status_code=500,
            detail=(
                "Memory could not "
                "be stored."
            ),
        )

    return str(
        memory_id
    )


def list_customer_memory(
    customer_id: str,
) -> list[dict]:
    """
    Return active remembered facts for the customer's
    privacy/settings view.

    Explicit customer_id filtering is mandatory because
    the backend Supabase client uses service_role.
    """

    try:
        response = (
            supabase_admin
            .table(
                "customer_memory"
            )
            .select(
                "id, memory_type, memory_key, "
                "memory_value, confidence, "
                "source_conversation_id, "
                "is_active, last_confirmed_at, "
                "created_at, updated_at"
            )
            .eq(
                "customer_id",
                customer_id,
            )
            .eq(
                "is_active",
                True,
            )
            .order(
                "last_confirmed_at",
                desc=True,
            )
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return (
        response.data
        or []
    )


def delete_customer_memory(
    customer_id: str,
    memory_id: str,
) -> dict:
    """
    Permanently delete one remembered fact owned
    by the customer.
    """

    existing = (
        supabase_admin
        .table(
            "customer_memory"
        )
        .select("id")
        .eq(
            "id",
            memory_id,
        )
        .eq(
            "customer_id",
            customer_id,
        )
        .limit(1)
        .execute()
    )

    if not existing.data:
        raise HTTPException(
            status_code=404,
            detail=(
                "Remembered fact "
                "not found."
            ),
        )

    try:
        (
            supabase_admin
            .table(
                "customer_memory"
            )
            .delete()
            .eq(
                "id",
                memory_id,
            )
            .eq(
                "customer_id",
                customer_id,
            )
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "deleted": True,
        "id": memory_id,
    }