from typing import Optional

from pydantic import BaseModel


class OrderItemResponse(BaseModel):
    variant_id: str
    quantity: int
    unit_price: float
    line_total: float
    product_snapshot: dict


class OrderResponse(BaseModel):
    id: str
    branch_id: Optional[str] = None
    status: str
    subtotal: float
    discount: float
    total: float
    currency: str
    source: str
    created_at: str
    items: list[OrderItemResponse]