from __future__ import annotations

from datetime import (
    date,
    datetime,
    timezone,
)
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel

from app.core.supabase_client import (
    supabase_admin,
)


# ============================================================================
# Helpers
# ============================================================================


VALID_MESSAGE_ROLES = {
    "user",
    "assistant",
    "system",
    "agent",
    "tool",
}

VALID_LANGUAGES = {
    "english",
    "roman_urdu",
    "mixed",
}


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _json_safe(
    value: Any,
) -> Any:
    """
    Convert common Python/Pydantic values into values safe for jsonb.
    """

    if value is None:
        return None

    if isinstance(
        value,
        BaseModel,
    ):
        return value.model_dump(
            mode="json"
        )

    if isinstance(
        value,
        Decimal,
    ):
        return float(value)

    if isinstance(
        value,
        UUID,
    ):
        return str(value)

    if isinstance(
        value,
        (datetime, date),
    ):
        return value.isoformat()

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): _json_safe(
                item
            )
            for key, item
            in value.items()
        }

    if isinstance(
        value,
        (list, tuple, set),
    ):
        return [
            _json_safe(item)
            for item in value
        ]

    return value


def _touch_conversation(
    conversation_id: str,
):
    (
        supabase_admin
        .table("conversations")
        .update(
            {
                "updated_at":
                    _utc_now(),
            }
        )
        .eq(
            "id",
            conversation_id,
        )
        .execute()
    )


# ============================================================================
# Conversations
# ============================================================================


def create_conversation(
    customer_id: str,
    *,
    language: str = "english",
    title: str | None = None,
) -> dict:
    if language not in VALID_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported conversation "
                "language."
            ),
        )

    response = (
        supabase_admin
        .table("conversations")
        .insert(
            {
                "customer_id":
                    customer_id,
                "title":
                    title,
                "language":
                    language,
            }
        )
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise HTTPException(
            status_code=500,
            detail=(
                "Conversation could not "
                "be created."
            ),
        )

    conversation = rows[0]

    # Every conversation gets a state row immediately.
    (
        supabase_admin
        .table("conversation_state")
        .insert(
            {
                "conversation_id":
                    conversation["id"],
                "state": {},
            }
        )
        .execute()
    )

    return conversation


def get_owned_conversation(
    customer_id: str,
    conversation_id: str,
) -> dict:
    """
    Explicit ownership validation is required because the backend uses
    service_role and therefore does not rely on customer RLS for writes.
    """

    response = (
        supabase_admin
        .table("conversations")
        .select("*")
        .eq(
            "id",
            conversation_id,
        )
        .eq(
            "customer_id",
            customer_id,
        )
        .limit(1)
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                "Conversation not found."
            ),
        )

    return rows[0]


def get_or_create_conversation(
    customer_id: str,
    *,
    conversation_id: (
        str | None
    ) = None,
    language: str = "english",
    title: str | None = None,
) -> dict:
    if conversation_id:
        return get_owned_conversation(
            customer_id,
            conversation_id,
        )

    return create_conversation(
        customer_id,
        language=language,
        title=title,
    )


def update_conversation_language(
    customer_id: str,
    conversation_id: str,
    language: str,
) -> dict:
    get_owned_conversation(
        customer_id,
        conversation_id,
    )

    if language not in VALID_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported conversation "
                "language."
            ),
        )

    response = (
        supabase_admin
        .table("conversations")
        .update(
            {
                "language":
                    language,
                "updated_at":
                    _utc_now(),
            }
        )
        .eq(
            "id",
            conversation_id,
        )
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise HTTPException(
            status_code=500,
            detail=(
                "Conversation language "
                "could not be updated."
            ),
        )

    return rows[0]

def list_customer_conversations(
    customer_id: str,
    *,
    limit: int = 30,
) -> list[dict]:
    """
    Return the customer's recent conversations,
    newest activity first.
    """

    safe_limit = max(
        1,
        min(limit, 100),
    )

    response = (
        supabase_admin
        .table("conversations")
        .select(
            "id, title, language, "
            "created_at, updated_at"
        )
        .eq(
            "customer_id",
            customer_id,
        )
        .order(
            "updated_at",
            desc=True,
        )
        .limit(
            safe_limit
        )
        .execute()
    )

    return response.data or []


def delete_conversation(
    customer_id: str,
    conversation_id: str,
) -> dict:
    """
    Permanently delete one owned conversation.

    The ownership check is mandatory because this
    backend uses the Supabase service_role client.
    Related messages and conversation_state rows
    are removed by database ON DELETE CASCADE
    constraints.
    """

    conversation = (
        get_owned_conversation(
            customer_id,
            conversation_id,
        )
    )

    # Support tickets are business records and must survive
    # chat deletion. The current schema keeps a nullable
    # conversation_id on support_escalations without
    # ON DELETE SET NULL, so explicitly detach owned tickets
    # before deleting the conversation.
    (
        supabase_admin
        .table("support_escalations")
        .update(
            {
                "conversation_id":
                    None,
            }
        )
        .eq(
            "customer_id",
            customer_id,
        )
        .eq(
            "conversation_id",
            conversation_id,
        )
        .execute()
    )

    (
        supabase_admin
        .table("conversations")
        .delete()
        .eq(
            "id",
            conversation_id,
        )
        .eq(
            "customer_id",
            customer_id,
        )
        .execute()
    )

    return {
        "id":
            str(conversation["id"]),
        "deleted":
            True,
    }


def get_conversation_history(
    customer_id: str,
    conversation_id: str,
    *,
    limit: int = 100,
) -> dict:
    """
    Return one owned conversation together with
    customer/assistant messages suitable for
    reopening in the chat UI.
    """

    conversation = (
        get_owned_conversation(
            customer_id,
            conversation_id,
        )
    )

    messages = (
        list_recent_messages(
            customer_id,
            conversation_id,
            limit=limit,
        )
    )

    visible_messages: list[dict] = []

    for message in messages:
        role = message.get("role")

        if role not in {
            "user",
            "assistant",
        }:
            continue

        metadata = (
            message.get("metadata")
            or {}
        )

        blocks = (
            metadata.get("blocks")
            or []
        )

        if not isinstance(
            blocks,
            list,
        ):
            blocks = []

        visible_messages.append(
            {
                "id":
                    str(message["id"]),
                "role":
                    role,
                "content":
                    message.get("content")
                    or "",
                "language": (
                    metadata.get(
                        "language"
                    )
                    or conversation.get(
                        "language"
                    )
                    or "english"
                ),
                "blocks":
                    blocks,
                "created_at":
                    message.get(
                        "created_at"
                    ),
            }
        )

    return {
        "conversation":
            conversation,
        "messages":
            visible_messages,
    }
# ============================================================================
# Messages
# ============================================================================


def append_message(
    customer_id: str,
    conversation_id: str,
    *,
    role: str,
    content: str | None,
    agent_key: str | None = None,
    tool_name: str | None = None,
    metadata: dict | None = None,
) -> dict:
    get_owned_conversation(
        customer_id,
        conversation_id,
    )

    if role not in VALID_MESSAGE_ROLES:
        raise HTTPException(
            status_code=400,
            detail="Invalid message role.",
        )

    response = (
        supabase_admin
        .table("messages")
        .insert(
            {
                "conversation_id":
                    conversation_id,
                "role":
                    role,
                "content":
                    content,
                "agent_key":
                    agent_key,
                "tool_name":
                    tool_name,
                "metadata":
                    _json_safe(
                        metadata or {}
                    ),
            }
        )
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise HTTPException(
            status_code=500,
            detail=(
                "Message could not be "
                "saved."
            ),
        )

    _touch_conversation(
        conversation_id
    )

    return rows[0]


def list_recent_messages(
    customer_id: str,
    conversation_id: str,
    *,
    limit: int = 20,
) -> list[dict]:
    get_owned_conversation(
        customer_id,
        conversation_id,
    )

    safe_limit = max(
        1,
        min(limit, 100),
    )

    response = (
        supabase_admin
        .table("messages")
        .select("*")
        .eq(
            "conversation_id",
            conversation_id,
        )
        .order(
            "created_at",
            desc=True,
        )
        .limit(
            safe_limit
        )
        .execute()
    )

    # DB query returns newest first.
    # Agents want conversation order.
    return list(
        reversed(
            response.data or []
        )
    )


# ============================================================================
# Conversation state
# ============================================================================


def get_conversation_state(
    customer_id: str,
    conversation_id: str,
) -> dict:
    get_owned_conversation(
        customer_id,
        conversation_id,
    )

    response = (
        supabase_admin
        .table("conversation_state")
        .select("state")
        .eq(
            "conversation_id",
            conversation_id,
        )
        .limit(1)
        .execute()
    )

    rows = response.data or []

    if not rows:
        return {}

    return rows[0].get(
        "state"
    ) or {}


def save_conversation_state(
    customer_id: str,
    conversation_id: str,
    state: dict,
) -> dict:
    get_owned_conversation(
        customer_id,
        conversation_id,
    )

    state = _json_safe(
        state
    )

    existing = (
        supabase_admin
        .table("conversation_state")
        .select("conversation_id")
        .eq(
            "conversation_id",
            conversation_id,
        )
        .limit(1)
        .execute()
    )

    if existing.data:
        response = (
            supabase_admin
            .table(
                "conversation_state"
            )
            .update(
                {
                    "state":
                        state,
                    "updated_at":
                        _utc_now(),
                }
            )
            .eq(
                "conversation_id",
                conversation_id,
            )
            .execute()
        )
    else:
        response = (
            supabase_admin
            .table(
                "conversation_state"
            )
            .insert(
                {
                    "conversation_id":
                        conversation_id,
                    "state":
                        state,
                }
            )
            .execute()
        )

    _touch_conversation(
        conversation_id
    )

    rows = response.data or []

    if not rows:
        raise HTTPException(
            status_code=500,
            detail=(
                "Conversation state "
                "could not be saved."
            ),
        )

    return rows[0].get(
        "state"
    ) or {}


def merge_conversation_state(
    customer_id: str,
    conversation_id: str,
    updates: dict,
) -> dict:
    """
    Shallow merge used by the orchestrator for turn-to-turn references.

    Example state:
    {
        "last_intent": "product_search",
        "last_variant_id": "...",
        "last_product_ids": [...],
        "last_search_variant_ids": [...],
        "language": "mixed"
    }
    """

    current = (
        get_conversation_state(
            customer_id,
            conversation_id,
        )
    )

    merged = {
        **current,
        **_json_safe(updates),
    }

    return save_conversation_state(
        customer_id,
        conversation_id,
        merged,
    )


# ============================================================================
# Agent runs
# ============================================================================


def create_agent_run(
    customer_id: str,
    conversation_id: str,
    *,
    input_text: str,
    root_agent_key: str = (
        "orchestrator_agent"
    ),
    metadata: dict | None = None,
) -> dict:
    get_owned_conversation(
        customer_id,
        conversation_id,
    )

    now = _utc_now()

    response = (
        supabase_admin
        .table("agent_runs")
        .insert(
            {
                "customer_id":
                    customer_id,
                "conversation_id":
                    conversation_id,
                "root_agent_key":
                    root_agent_key,
                "input_text":
                    input_text,
                "status":
                    "running",
                "metadata":
                    _json_safe(
                        metadata or {}
                    ),
                "started_at":
                    now,
            }
        )
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise HTTPException(
            status_code=500,
            detail=(
                "Agent run could not "
                "be created."
            ),
        )

    return rows[0]


def complete_agent_run(
    run_id: str,
    *,
    final_response: str,
    metadata: (
        dict | None
    ) = None,
) -> dict:
    values: dict[str, Any] = {
        "status":
            "completed",
        "final_response":
            final_response,
        "completed_at":
            _utc_now(),
    }

    if metadata is not None:
        values["metadata"] = (
            _json_safe(metadata)
        )

    response = (
        supabase_admin
        .table("agent_runs")
        .update(values)
        .eq(
            "id",
            run_id,
        )
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Agent run not found.",
        )

    return rows[0]


def fail_agent_run(
    run_id: str,
    *,
    error_message: str,
) -> dict:
    response = (
        supabase_admin
        .table("agent_runs")
        .update(
            {
                "status":
                    "failed",
                "metadata": {
                    "error":
                        error_message,
                },
                "completed_at":
                    _utc_now(),
            }
        )
        .eq(
            "id",
            run_id,
        )
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Agent run not found.",
        )

    return rows[0]


# ============================================================================
# Agent tasks
# ============================================================================


def create_agent_task(
    agent_run_id: str,
    *,
    agent_key: str,
    task_type: str,
    input_payload: (
        dict | None
    ) = None,
) -> dict:
    response = (
        supabase_admin
        .table("agent_tasks")
        .insert(
            {
                "agent_run_id":
                    agent_run_id,
                "agent_key":
                    agent_key,
                "task_type":
                    task_type,
                "input_payload":
                    _json_safe(
                        input_payload
                        or {}
                    ),
                "output_payload":
                    {},
                "status":
                    "running",
                "started_at":
                    _utc_now(),
            }
        )
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise HTTPException(
            status_code=500,
            detail=(
                "Agent task could not "
                "be created."
            ),
        )

    return rows[0]


def complete_agent_task(
    task_id: str,
    *,
    output_payload: (
        dict | None
    ) = None,
) -> dict:
    response = (
        supabase_admin
        .table("agent_tasks")
        .update(
            {
                "status":
                    "completed",
                "output_payload":
                    _json_safe(
                        output_payload
                        or {}
                    ),
                "completed_at":
                    _utc_now(),
            }
        )
        .eq(
            "id",
            task_id,
        )
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Agent task not found.",
        )

    return rows[0]


def fail_agent_task(
    task_id: str,
    *,
    error_message: str,
) -> dict:
    response = (
        supabase_admin
        .table("agent_tasks")
        .update(
            {
                "status":
                    "failed",
                "error_message":
                    error_message,
                "completed_at":
                    _utc_now(),
            }
        )
        .eq(
            "id",
            task_id,
        )
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Agent task not found.",
        )

    return rows[0]


# ============================================================================
# Agent tool calls
# ============================================================================


def create_agent_tool_call(
    *,
    agent_run_id: str,
    agent_task_id: (
        str | None
    ),
    agent_key: str,
    tool_name: str,
    arguments: (
        dict | None
    ) = None,
) -> dict:
    response = (
        supabase_admin
        .table("agent_tool_calls")
        .insert(
            {
                "agent_run_id":
                    agent_run_id,
                "agent_task_id":
                    agent_task_id,
                "agent_key":
                    agent_key,
                "tool_name":
                    tool_name,
                "arguments":
                    _json_safe(
                        arguments or {}
                    ),
                "started_at":
                    _utc_now(),
            }
        )
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise HTTPException(
            status_code=500,
            detail=(
                "Agent tool call could "
                "not be created."
            ),
        )

    return rows[0]


def complete_agent_tool_call(
    tool_call_id: str,
    *,
    result: Any = None,
) -> dict:
    response = (
        supabase_admin
        .table("agent_tool_calls")
        .update(
            {
                "result":
                    _json_safe(result),
                "success":
                    True,
                "completed_at":
                    _utc_now(),
            }
        )
        .eq(
            "id",
            tool_call_id,
        )
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                "Agent tool call "
                "not found."
            ),
        )

    return rows[0]


def fail_agent_tool_call(
    tool_call_id: str,
    *,
    error_message: str,
) -> dict:
    response = (
        supabase_admin
        .table("agent_tool_calls")
        .update(
            {
                "success":
                    False,
                "error_message":
                    error_message,
                "completed_at":
                    _utc_now(),
            }
        )
        .eq(
            "id",
            tool_call_id,
        )
        .execute()
    )

    rows = response.data or []

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                "Agent tool call "
                "not found."
            ),
        )

    return rows[0]