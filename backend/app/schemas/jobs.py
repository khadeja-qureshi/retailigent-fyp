from typing import Optional

from pydantic import BaseModel, Field


class RequeueRequest(BaseModel):
    """delivery_ids omitted/null = requeue every dead-lettered delivery."""

    delivery_ids: Optional[list[str]] = Field(default=None, max_length=500)


class RequeueResponse(BaseModel):
    requeued: int
