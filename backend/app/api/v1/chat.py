from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
)
from fastapi.responses import (
    StreamingResponse,
)
from starlette.concurrency import (
    run_in_threadpool,
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
    """
    Encode one Server-Sent Event.

    JSON encoding ensures embedded newlines in
    assistant content do not break the SSE frame.
    """

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
    """
    Split final assistant text into small chunks
    for the frontend streaming experience.

    The agent currently completes its deterministic
    orchestration first, then the completed response
    is streamed to the client.
    """

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
    """
    Execute one authenticated Retailigent chat turn.

    Authentication and role validation happen before
    the SSE stream begins.

    Stream event contract:

    turn_started
    conversation
    message_start
    message_delta
    block
    done
    error
    """

    async def event_stream():
        # The connection opens immediately even though
        # orchestration itself may take some time.
        yield _sse_event(
            "turn_started",
            {
                "conversation_id":
                    request.conversation_id,
            },
        )

        try:
            # process_turn is currently synchronous
            # because the underlying service wrappers
            # are synchronous. Run it off the asyncio
            # event loop.
            result = await run_in_threadpool(
                orchestrator_agent.process_turn,
                customer_id=customer_id,
                message=request.message,
                conversation_id=(
                    request.conversation_id
                ),
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
            logger.exception(
                "Chat orchestration failed "
                "for customer %s",
                customer_id,
            )

            # Do not expose stack traces, Supabase
            # internals, or implementation details to
            # the browser.
            yield _sse_event(
                "error",
                {
                    "message": (
                        "I couldn't complete "
                        "that request right now."
                    ),
                },
            )

    return StreamingResponse(
        event_stream(),
        media_type=(
            "text/event-stream"
        ),
        headers={
            "Cache-Control":
                "no-cache",
            "Connection":
                "keep-alive",
            "X-Accel-Buffering":
                "no",
        },
    )