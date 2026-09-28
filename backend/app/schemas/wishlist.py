from uuid import UUID

from pydantic import BaseModel


class AddWishlistItemRequest(BaseModel):
    variant_id: UUID