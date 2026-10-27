from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from fastapi.responses import (
    StreamingResponse,
)
from starlette.concurrency import (
    run_in_threadpool,
)

from app.agents.memory_agent import (
    memory_agent,
)
from app.agents.orchestrator_agent import (
    orchestrator_agent,
)
from app.core.auth import (
    get_current_user_id,
    require_customer,
)
from app.schemas.chat import (
    ChatRequest,
)
from app.services import chat_service


logger = logging.getLogger(
    __name__
)


router = APIRouter(
    prefix="/api/v1/chat",
    tags=["chat"],
)


def _sse_event(
    event: str,
    data: Any,
) -> str:
    payload = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return (
        f"event: {event}\n"
        f"data: {payload}\n\n"
    )


def _text_chunks(
    text: str,
    chunk_size: int = 80,
) -> Iterator[str]:
    if not text:
        return

    start = 0

    while start < len(text):
        end = min(
            start + chunk_size,
            len(text),
        )

        yield text[start:end]

        start = end


@router.get(
    "/conversations"
)
def list_conversations(
    limit: int = Query(
        default=30,
        ge=1,
        le=100,
    ),
    customer_id: str = Depends(
        get_current_user_id
    ),
    _customer_role: str = Depends(
        require_customer
    ),
) -> dict:
    """
    Return recent chat conversations belonging
    to the authenticated customer.
    """

    conversations = (
        chat_service
        .list_customer_conversations(
            customer_id,
            limit=limit,
        )
    )

    return {
        "conversations":
            conversations,
    }


@router.get(
    "/conversations/{conversation_id}"
)
def get_conversation(
    conversation_id: str,
    customer_id: str = Depends(
        get_current_user_id
    ),
    _customer_role: str = Depends(
        require_customer
    ),
) -> dict:
    """
    Reopen an existing owned conversation.
    """

    return (
        chat_service
        .get_conversation_history(
            customer_id,
            conversation_id,
            limit=100,
        )
    )


@router.delete(
    "/conversations/{conversation_id}"
)
def delete_conversation(
    conversation_id: str,
    customer_id: str = Depends(
        get_current_user_id
    ),
    _customer_role: str = Depends(
        require_customer
    ),
) -> dict:
    """
    Permanently delete one chat conversation
    belonging to the authenticated customer.
    """

    return (
        chat_service
        .delete_conversation(
            customer_id,
            conversation_id,
        )
    )


@router.post(
    "/{conversation_id}/finalize"
)
async def finalize_conversation(
    conversation_id: str,
    customer_id: str = Depends(
        get_current_user_id
    ),
    _customer_role: str = Depends(
        require_customer
    ),
) -> dict:
    """
    Extract and save durable facts when the
    customer leaves a conversation.
    """

    stored = await run_in_threadpool(
        memory_agent.finalize_conversation,
        customer_id,
        conversation_id,
    )

    return {
        "conversation_id":
            conversation_id,

        "memory_saved":
            len(stored),

        "memories":
            stored,
    }


@router.post("")
async def chat(
    request: ChatRequest,
    customer_id: str = Depends(
        get_current_user_id
    ),
    _customer_role: str = Depends(
        require_customer
    ),
) -> StreamingResponse:

    async def event_stream():
        yield _sse_event(
            "turn_started",
            {
                "conversation_id":
                    request.conversation_id,
            },
        )

        try:
            # Build kwargs dynamically.
            #
            # This keeps the orchestration contract
            # backward-compatible for callers/tests
            # that do not supply browser coordinates,
            # while still forwarding location when
            # it is actually available.
            process_kwargs = {
                "customer_id":
                    customer_id,

                "message":
                    request.message,

                "conversation_id":
                    request.conversation_id,
            }


            if (
                request.latitude
                is not None
            ):
                process_kwargs[
                    "customer_latitude"
                ] = request.latitude


            if (
                request.longitude
                is not None
            ):
                process_kwargs[
                    "customer_longitude"
                ] = request.longitude


            result = await run_in_threadpool(
                orchestrator_agent.process_turn,
                **process_kwargs,
            )


            yield _sse_event(
                "conversation",
                {
                    "conversation_id":
                        result.conversation_id,
                },
            )


            yield _sse_event(
                "message_start",
                {
                    "message_id":
                        result.message_id,

                    "role":
                        "assistant",

                    "language":
                        result.language,
                },
            )


            for chunk in _text_chunks(
                result.content
            ):
                yield _sse_event(
                    "message_delta",
                    {
                        "message_id":
                            result.message_id,

                        "delta":
                            chunk,
                    },
                )


            for block in result.blocks:
                yield _sse_event(
                    "block",
                    {
                        "message_id":
                            result.message_id,

                        "block":
                            block.model_dump(
                                mode="json"
                            ),
                    },
                )


            yield _sse_event(
                "done",
                {
                    "conversation_id":
                        result.conversation_id,

                    "message_id":
                        result.message_id,

                    "language":
                        result.language,

                    "block_count":
                        len(
                            result.blocks
                        ),
                },
            )


        except Exception:
            # Do not expose internal exception
            # details to the customer.
            #
            # Also do not use "message" as a key
            # inside logging extra={} because it is
            # a reserved LogRecord field.
            logger.exception(
                "Chat orchestration failed "
                "for customer %s",
                customer_id,
            )


            yield _sse_event(
                "error",
                {
                    "message":
                        (
                            "I couldn't complete "
                            "that request right now."
                        ),
                },
            )


    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":
                "no-cache",

            "Connection":
                "keep-alive",

            "X-Accel-Buffering":
                "no",
        },
    )