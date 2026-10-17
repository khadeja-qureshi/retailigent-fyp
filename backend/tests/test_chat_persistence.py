import os

import pytest
from dotenv import load_dotenv
from fastapi import HTTPException

from app.core.supabase_client import (
    supabase_admin,
)
from app.services.chat_service import (
    append_message,
    complete_agent_run,
    complete_agent_task,
    complete_agent_tool_call,
    create_agent_run,
    create_agent_task,
    create_agent_tool_call,
    create_conversation,
    get_conversation_state,
    get_owned_conversation,
    list_recent_messages,
    merge_conversation_state,
)


load_dotenv()

CUSTOMER_ID = os.getenv(
    "TEST_CUSTOMER_ID"
)


def require_test_customer():
    assert CUSTOMER_ID, (
        "TEST_CUSTOMER_ID is missing "
        "from backend/.env"
    )


def delete_conversation(
    conversation_id: str,
):
    (
        supabase_admin
        .table("conversations")
        .delete()
        .eq(
            "id",
            conversation_id,
        )
        .execute()
    )


def delete_agent_run(
    run_id: str,
):
    # agent_tasks and agent_tool_calls
    # cascade from agent_runs.
    (
        supabase_admin
        .table("agent_runs")
        .delete()
        .eq(
            "id",
            run_id,
        )
        .execute()
    )


def test_conversation_messages_and_state_round_trip():
    require_test_customer()

    conversation_id = None

    try:
        conversation = (
            create_conversation(
                CUSTOMER_ID,
                language="mixed",
                title=(
                    "Phase 11 "
                    "persistence test"
                ),
            )
        )

        conversation_id = (
            conversation["id"]
        )

        assert (
            conversation[
                "customer_id"
            ]
            == CUSTOMER_ID
        )

        assert (
            conversation[
                "language"
            ]
            == "mixed"
        )

        # State row must exist from the
        # moment conversation is created.
        assert (
            get_conversation_state(
                CUSTOMER_ID,
                conversation_id,
            )
            == {}
        )

        user_message = (
            append_message(
                CUSTOMER_ID,
                conversation_id,
                role="user",
                content=(
                    "Mujhe blue "
                    "kurta dikhao"
                ),
                metadata={
                    "language":
                        "roman_urdu",
                },
            )
        )

        assistant_message = (
            append_message(
                CUSTOMER_ID,
                conversation_id,
                role="assistant",
                content=(
                    "Yeh options "
                    "available hain."
                ),
                agent_key=(
                    "customer_"
                    "interaction_agent"
                ),
                metadata={
                    "blocks": [
                        {
                            "type":
                                "product_carousel",
                        }
                    ],
                },
            )
        )

        assert (
            user_message["role"]
            == "user"
        )

        assert (
            assistant_message["role"]
            == "assistant"
        )

        messages = (
            list_recent_messages(
                CUSTOMER_ID,
                conversation_id,
                limit=20,
            )
        )

        assert len(messages) == 2

        # Must be chronological.
        assert (
            messages[0]["role"]
            == "user"
        )

        assert (
            messages[1]["role"]
            == "assistant"
        )

        state = (
            merge_conversation_state(
                CUSTOMER_ID,
                conversation_id,
                {
                    "last_intent":
                        "product_search",
                    "last_variant_id":
                        "variant-test-1",
                    "last_search_variant_ids":
                        [
                            "variant-test-1",
                            "variant-test-2",
                        ],
                    "language":
                        "mixed",
                },
            )
        )

        assert (
            state["last_intent"]
            == "product_search"
        )

        assert (
            state[
                "last_variant_id"
            ]
            == "variant-test-1"
        )

        saved = (
            get_conversation_state(
                CUSTOMER_ID,
                conversation_id,
            )
        )

        assert (
            saved[
                "last_search_variant_ids"
            ]
            ==
            [
                "variant-test-1",
                "variant-test-2",
            ]
        )

    finally:
        if conversation_id:
            delete_conversation(
                conversation_id
            )


def test_conversation_ownership_is_enforced():
    require_test_customer()

    conversation_id = None

    try:
        conversation = (
            create_conversation(
                CUSTOMER_ID
            )
        )

        conversation_id = (
            conversation["id"]
        )

        fake_other_customer = (
            "00000000-0000-0000-"
            "0000-000000000001"
        )

        with pytest.raises(
            HTTPException
        ) as exc_info:
            get_owned_conversation(
                fake_other_customer,
                conversation_id,
            )

        assert (
            exc_info.value.status_code
            == 404
        )

    finally:
        if conversation_id:
            delete_conversation(
                conversation_id
            )


def test_agent_trace_lifecycle():
    require_test_customer()

    conversation_id = None
    run_id = None

    try:
        conversation = (
            create_conversation(
                CUSTOMER_ID,
                language="english",
            )
        )

        conversation_id = (
            conversation["id"]
        )

        run = create_agent_run(
            CUSTOMER_ID,
            conversation_id,
            input_text=(
                "Is the first one "
                "available?"
            ),
        )

        run_id = run["id"]

        assert (
            run["status"]
            == "running"
        )

        task = create_agent_task(
            run_id,
            agent_key=(
                "inventory_agent"
            ),
            task_type=(
                "check_stock"
            ),
            input_payload={
                "variant_id":
                    "variant-test-1",
            },
        )

        assert (
            task["status"]
            == "running"
        )

        tool_call = (
            create_agent_tool_call(
                agent_run_id=
                    run_id,
                agent_task_id=
                    task["id"],
                agent_key=
                    "inventory_agent",
                tool_name=
                    "get_stock_status",
                arguments={
                    "variant_id":
                        "variant-test-1",
                },
            )
        )

        finished_tool = (
            complete_agent_tool_call(
                tool_call["id"],
                result={
                    "available_quantity":
                        3,
                    "status":
                        "available",
                },
            )
        )

        assert (
            finished_tool["success"]
            is True
        )

        assert (
            finished_tool[
                "completed_at"
            ]
            is not None
        )

        finished_task = (
            complete_agent_task(
                task["id"],
                output_payload={
                    "available_quantity":
                        3,
                    "status":
                        "available",
                },
            )
        )

        assert (
            finished_task["status"]
            == "completed"
        )

        finished_run = (
            complete_agent_run(
                run_id,
                final_response=(
                    "Yes, it is "
                    "available."
                ),
                metadata={
                    "language":
                        "english",
                    "intent":
                        "stock_check",
                },
            )
        )

        assert (
            finished_run["status"]
            == "completed"
        )

        assert (
            finished_run[
                "final_response"
            ]
            ==
            "Yes, it is available."
        )

        # Verify persisted task.
        task_row = (
            supabase_admin
            .table("agent_tasks")
            .select(
                "status, "
                "output_payload"
            )
            .eq(
                "id",
                task["id"],
            )
            .single()
            .execute()
            .data
        )

        assert (
            task_row["status"]
            == "completed"
        )

        # Verify persisted tool call.
        tool_row = (
            supabase_admin
            .table(
                "agent_tool_calls"
            )
            .select(
                "success, result"
            )
            .eq(
                "id",
                tool_call["id"],
            )
            .single()
            .execute()
            .data
        )

        assert (
            tool_row["success"]
            is True
        )

        assert (
            tool_row["result"][
                "available_quantity"
            ]
            == 3
        )

    finally:
        if run_id:
            delete_agent_run(
                run_id
            )

        if conversation_id:
            delete_conversation(
                conversation_id
            )