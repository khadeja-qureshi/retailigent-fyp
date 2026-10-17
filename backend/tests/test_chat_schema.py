from pydantic import (
    TypeAdapter,
    ValidationError,
)
import pytest

from app.schemas.chat import (
    ChatRequest,
    ProductCarouselBlock,
    RenderableBlock,
    StockStatusBlock,
)


block_adapter = TypeAdapter(
    RenderableBlock
)


def test_chat_request_accepts_message():
    request = ChatRequest(
        message=(
            "Show me blue kurtas "
            "size M"
        )
    )

    assert request.message.startswith(
        "Show me"
    )

    assert (
        request.conversation_id
        is None
    )


def test_product_carousel_block():
    block = ProductCarouselBlock(
        products=[
            {
                "product_id": "p1",
                "variant_id": "v1",
                "name": "Printed Lawn Kurta",
                "sku": "TEST-KURTA-M",
                "effective_price": 2500,
                "color": "Blue",
                "size": "M",
                "max_available_at_one_branch": 3,
            }
        ]
    )

    assert (
        block.type
        == "product_carousel"
    )

    assert len(
        block.products
    ) == 1

    assert (
        block.products[0].variant_id
        == "v1"
    )


def test_stock_status_block():
    block = StockStatusBlock(
        variant_id="v1",
        product_name=(
            "Printed Lawn Kurta"
        ),
        sku="TEST-KURTA-M",
        branches=[
            {
                "branch_id": "b1",
                "branch_name": "Clifton",
                "available_quantity": 3,
                "status": "available",
            }
        ],
    )

    assert (
        block.type
        == "stock_status"
    )

    assert (
        block.branches[0]
        .available_quantity
        == 3
    )


def test_renderable_block_discriminator():
    block = (
        block_adapter
        .validate_python(
            {
                "type":
                    "stock_status",
                "variant_id":
                    "v1",
                "branches": [
                    {
                        "branch_id":
                            "b1",
                        "branch_name":
                            "Clifton",
                        "available_quantity":
                            2,
                        "status":
                            "available",
                    }
                ],
            }
        )
    )

    assert isinstance(
        block,
        StockStatusBlock,
    )


def test_invalid_block_type_is_rejected():
    with pytest.raises(
        ValidationError
    ):
        (
            block_adapter
            .validate_python(
                {
                    "type":
                        "made_up_block",
                    "value":
                        "invalid",
                }
            )
        )