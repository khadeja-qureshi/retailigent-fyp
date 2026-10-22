from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

FeedbackCategory = Literal[
    "product", "service", "delivery", "store",
    "website", "agent", "general",
]
FeedbackSentiment = Literal["positive", "neutral", "negative"]
FeedbackType = Literal[
    "product", "service", "delivery", "store",
    "website", "agent", "general",
]


class FeedbackCreate(BaseModel):
    feedback_type: FeedbackType = "general"
    rating: int | None = Field(default=None, ge=1, le=5)
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None


class FeedbackClassificationCorrection(BaseModel):
    staff_category: FeedbackCategory
    staff_sentiment: FeedbackSentiment
