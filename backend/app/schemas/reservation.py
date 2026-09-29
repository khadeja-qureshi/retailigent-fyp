from uuid import UUID

from pydantic import BaseModel, Field


class CreateReservationRequest(BaseModel):
    variant_id: UUID
    branch_id: UUID
    quantity: int = Field(ge=1)
    hold_minutes: int = Field(default=15, ge=1, le=30)