from uuid import UUID

from pydantic import BaseModel, Field


class AddCartItemRequest(BaseModel):
    variant_id: UUID
    quantity: int = Field(default=1, ge=1)


class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(ge=1)