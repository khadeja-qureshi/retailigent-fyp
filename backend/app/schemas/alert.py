from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)


class CreateAlertRequest(BaseModel):
    variant_id: UUID

    alert_type: Literal[
        "price_drop",
        "restock",
        "sale",
    ]

    target_price: Decimal | None = Field(
        default=None,
        ge=0,
    )

    @model_validator(mode="after")
    def validate_target(self):
        if (
            self.alert_type == "price_drop"
            and self.target_price is None
        ):
            raise ValueError(
                "Price-drop alerts require "
                "a target_price."
            )

        return self