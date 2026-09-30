from typing import Optional

from pydantic import BaseModel, Field


class MockPurchaseRequest(BaseModel):
    variant_id: str
    branch_id: Optional[str] = None
    quantity: int = Field(gt=0)
    idempotency_key: str = Field(min_length=1)


class ReservationPurchaseRequest(BaseModel):
    reservation_id: str
    quantity: Optional[int] = Field(default=None, gt=0)
    idempotency_key: str = Field(min_length=1)


class PurchaseResponse(BaseModel):
    success: bool
    order_id: Optional[str] = None
    purchase_attempt_id: Optional[str] = None
    reservation_id: Optional[str] = None
    reason: Optional[str] = None
    reason_code: Optional[str] = None
    already_completed: bool = False