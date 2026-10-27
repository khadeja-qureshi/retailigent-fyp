from typing import (
    Annotated,
    Any,
    Literal,
)

from pydantic import (
    BaseModel,
    Field,
)


# ---------------------------------------------------------------------------
# Product/search blocks
# ---------------------------------------------------------------------------


class ProductCard(BaseModel):
    product_id: str
    variant_id: str

    name: str
    sku: str

    brand: str | None = None
    material: str | None = None
    color: str | None = None
    size: str | None = None

    effective_price: float | None = None

    image_url: str | None = None

    max_available_at_one_branch: int | None = None


class ProductCarouselBlock(BaseModel):
    type: Literal[
        "product_carousel"
    ] = "product_carousel"

    title: str = "Products"

    products: list[ProductCard]


# ---------------------------------------------------------------------------
# Inventory / location blocks
# ---------------------------------------------------------------------------


class BranchLocationItem(BaseModel):
    branch_id: str

    name: str
    city: str

    area: str | None = None

    address: str | None = None

    latitude: float | None = None
    longitude: float | None = None

    distance_km: float | None = None

    phone: str | None = None

    opening_time: str | None = None
    closing_time: str | None = None


class BranchMapBlock(BaseModel):
    type: Literal[
        "branch_map"
    ] = "branch_map"

    title: str = "Store locations"

    branches: list[
        BranchLocationItem
    ] = Field(
        default_factory=list
    )


class StockBranchItem(BaseModel):
    branch_id: str
    branch_name: str

    city: str | None = None
    area: str | None = None
    address: str | None = None

    available_quantity: int

    status: Literal[
        "out_of_stock",
        "low_stock",
        "available",
    ]


class RecommendationBlock(BaseModel):
    type: Literal[
        "recommendation"
    ] = "recommendation"

    title: str = "Recommended for you"

    products: list[
        ProductCard
    ] = Field(
        default_factory=list
    )


class StockStatusBlock(BaseModel):
    type: Literal[
        "stock_status"
    ] = "stock_status"

    variant_id: str

    product_name: str | None = None

    sku: str | None = None

    color: str | None = None

    size: str | None = None

    branches: list[
        StockBranchItem
    ]


# ---------------------------------------------------------------------------
# Existing Phase 6-10 commerce blocks
# ---------------------------------------------------------------------------


class CartSummaryBlock(BaseModel):
    type: Literal[
        "cart_summary"
    ] = "cart_summary"

    data: dict[
        str,
        Any,
    ]


class WishlistBlock(BaseModel):
    type: Literal[
        "wishlist"
    ] = "wishlist"

    data: dict[
        str,
        Any,
    ]


class ReservationBlock(BaseModel):
    type: Literal[
        "reservation"
    ] = "reservation"

    reservation: dict[
        str,
        Any,
    ]


class SmartCartRuleBlock(BaseModel):
    type: Literal[
        "smart_cart_rule"
    ] = "smart_cart_rule"

    rule: dict[
        str,
        Any,
    ]


class AlertBlock(BaseModel):
    type: Literal[
        "alert"
    ] = "alert"

    alert: dict[
        str,
        Any,
    ]


class OrderConfirmationBlock(BaseModel):
    type: Literal[
        "order_confirmation"
    ] = "order_confirmation"

    order: dict[
        str,
        Any,
    ]


class NotificationListBlock(BaseModel):
    type: Literal[
        "notification_list"
    ] = "notification_list"

    data: dict[
        str,
        Any,
    ]


class SupportEscalationBlock(BaseModel):
    type: Literal[
        "support_escalation"
    ] = "support_escalation"

    ticket_id: str

    status: Literal[
        "open",
        "in_progress",
        "waiting_customer",
        "escalated",
        "resolved",
        "closed",
    ] = "open"

    subject: str

    message: str


# ---------------------------------------------------------------------------
# Discriminated union
#
# Every chat block uses the "type" field as the discriminator.
# ---------------------------------------------------------------------------


RenderableBlock = Annotated[
    (
        ProductCarouselBlock
        | RecommendationBlock
        | BranchMapBlock
        | StockStatusBlock
        | CartSummaryBlock
        | WishlistBlock
        | ReservationBlock
        | SmartCartRuleBlock
        | AlertBlock
        | OrderConfirmationBlock
        | NotificationListBlock
        | SupportEscalationBlock
    ),
    Field(
        discriminator="type"
    ),
]


# ---------------------------------------------------------------------------
# Chat request / response contracts
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=4000,
    )

    conversation_id: str | None = None

    # Optional browser location.
    # These are only populated when the frontend
    # has location permission and the query needs it.
    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
    )

    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
    )


class ChatTurnResponse(BaseModel):
    conversation_id: str

    message_id: str

    content: str

    language: Literal[
        "english",
        "roman_urdu",
        "mixed",
    ] = "english"

    blocks: list[
        RenderableBlock
    ] = Field(
        default_factory=list
    )


# ---------------------------------------------------------------------------
# Internal normalized understanding produced by CustomerInteractionAgent
# ---------------------------------------------------------------------------


class ExtractedEntities(BaseModel):
    product_name: str | None = None

    category: str | None = None

    variant_id: str | None = None

    color: str | None = None
    size: str | None = None
    material: str | None = None

    branch_name: str | None = None

    min_price: float | None = None
    max_price: float | None = None
    target_price: float | None = None

    min_discount_percentage: float | None = None

    quantity: int | None = None

    authorization_mode: Literal[
        "notify_only",
        "auto_buy",
    ] | None = None

    ordinal_reference: int | None = None

    ordinal_references: list[
        int
    ] = Field(
        default_factory=list
    )


class ParsedCustomerMessage(BaseModel):
    raw_message: str

    language: Literal[
        "english",
        "roman_urdu",
        "mixed",
    ]

    intent: str

    entities: ExtractedEntities = Field(
        default_factory=ExtractedEntities
    )

    context_used: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    requires_clarification: bool = False

    clarification_question: str | None = None