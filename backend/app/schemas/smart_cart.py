from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)


class CreateSmartCartRuleRequest(
    BaseModel
):
    variant_id: UUID

    branch_id: UUID | None = None

    quantity: int = Field(
        default=1,
        ge=1,
    )

    target_price: (
        Decimal | None
    ) = Field(
        default=None,
        ge=0,
    )

    min_discount_percentage: (
        Decimal | None
    ) = Field(
        default=None,
        ge=0,
        le=100,
    )

    authorization_mode: Literal[
        "notify_only",
        "auto_buy",
    ] = "notify_only"

    @model_validator(mode="after")
    def require_condition(self):
        if (
            self.target_price is None
            and
            self.min_discount_percentage
            is None
        ):
            raise ValueError(
                "Set target_price or "
                "min_discount_percentage."
            )

        return self