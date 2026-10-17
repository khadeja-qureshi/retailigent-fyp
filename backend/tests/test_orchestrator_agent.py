
import pytest

from app.agents import (
    orchestrator_agent as orchestrator_module,
)
from app.agents.customer_interaction_agent import (
    customer_interaction_agent,
)
from app.agents.orchestrator_agent import (
    build_product_carousel,
    orchestrator_agent,
    resolve_variant_reference,
)
from app.schemas.chat import (
    CartSummaryBlock,
    ProductCarouselBlock,
    SmartCartRuleBlock,
    StockStatusBlock,
    WishlistBlock,
    OrderConfirmationBlock,
)


@pytest.fixture
def fake_persistence(monkeypatch):
    state = {}

    counters = {
        "task": 0,
        "tool": 0,
        "message": 0,
    }

    def next_id(key):
        counters[key] += 1
        return f"{key}-{counters[key]}"

    monkeypatch.setattr(
        orchestrator_module.chat_service,
        "get_or_create_conversation",
        lambda *args, **kwargs: {
            "id": "conversation-1",
            "language": kwargs.get("language", "english"),
        },
    )

    monkeypatch.setattr(
        orchestrator_module.chat_service,
        "update_conversation_language",
        lambda *args, **kwargs: {},
    )

    def append_message(*args, **kwargs):
        return {
            "id": next_id("message"),
            "role": kwargs.get("role"),
            "content": kwargs.get("content"),
        }

    monkeypatch.setattr(
        orchestrator_module.chat_service,
        "append_message",
        append_message,
    )

    monkeypatch.setattr(
        orchestrator_module.chat_service,
        "create_agent_run",
        lambda *args, **kwargs: {"id": "run-1"},
    )

    monkeypatch.setattr(
        orchestrator_module.chat_service,
        "complete_agent_run",
        lambda *args, **kwargs: {},
    )

    monkeypatch.setattr(
        orchestrator_module.chat_service,
        "fail_agent_run",
        lambda *args, **kwargs: {},
    )

    def create_task(*args, **kwargs):
        return {"id": next_id("task")}

    monkeypatch.setattr(
        orchestrator_module.chat_service,
        "create_agent_task",
        create_task,
    )

    monkeypatch.setattr(
        orchestrator_module.chat_service,
        "complete_agent_task",
        lambda *args, **kwargs: {},
    )

    monkeypatch.setattr(
        orchestrator_module.chat_service,
        "fail_agent_task",
        lambda *args, **kwargs: {},
    )

    def create_tool(*args, **kwargs):
        return {"id": next_id("tool")}

    monkeypatch.setattr(
        orchestrator_module.chat_service,
        "create_agent_tool_call",
        create_tool,
    )

    monkeypatch.setattr(
        orchestrator_module.chat_service,
        "complete_agent_tool_call",
        lambda *args, **kwargs: {},
    )

    monkeypatch.setattr(
        orchestrator_module.chat_service,
        "fail_agent_tool_call",
        lambda *args, **kwargs: {},
    )

    monkeypatch.setattr(
        orchestrator_module.chat_service,
        "get_conversation_state",
        lambda *args, **kwargs: dict(state),
    )

    def merge_state(customer_id, conversation_id, updates):
        state.update(updates)
        return dict(state)

    monkeypatch.setattr(
        orchestrator_module.chat_service,
        "merge_conversation_state",
        merge_state,
    )

    return state


def test_resolves_first_search_result():
    parsed = customer_interaction_agent.parse(
        "Is the first one available?"
    )

    result = resolve_variant_reference(
        parsed,
        {
            "last_search_variant_ids": [
                "variant-1",
                "variant-2",
            ],
        },
    )

    assert result == "variant-1"


def test_resolves_second_search_result():
    parsed = customer_interaction_agent.parse(
        "Is the second one available?"
    )

    result = resolve_variant_reference(
        parsed,
        {
            "last_search_variant_ids": [
                "variant-1",
                "variant-2",
            ],
        },
    )

    assert result == "variant-2"


def test_context_pronoun_uses_last_variant():
    parsed = customer_interaction_agent.parse(
        "Is it available?"
    )

    result = resolve_variant_reference(
        parsed,
        {
            "last_variant_id": "variant-9",
        },
    )

    assert result == "variant-9"


def test_out_of_range_ordinal_is_not_invented():
    parsed = customer_interaction_agent.parse(
        "Is the third one available?"
    )

    result = resolve_variant_reference(
        parsed,
        {
            "last_search_variant_ids": [
                "variant-1",
            ],
        },
    )

    assert result is None


def test_build_product_carousel():
    block = build_product_carousel(
        [
            {
                "product_id": "product-1",
                "variant_id": "variant-1",
                "product": {
                    "name": "Printed Lawn Kurta",
                    "brand": "Khaadi",
                    "material": "Lawn",
                },
                "variant": {
                    "sku": "KURTA-BLU-M",
                    "price": 3000,
                    "color": {"name": "Blue"},
                    "size": {"name": "M"},
                },
                "pricing": {
                    "effective_price": 2500,
                },
                "images": [],
                "inventory": [
                    {"available_quantity": 4},
                    {"available_quantity": 1},
                ],
            }
        ]
    )

    assert isinstance(block, ProductCarouselBlock)
    assert len(block.products) == 1

    product = block.products[0]

    assert product.variant_id == "variant-1"
    assert product.effective_price == 2500
    assert product.max_available_at_one_branch == 4


def test_orchestrator_product_search(
    monkeypatch,
    fake_persistence,
):
    def fake_search(**kwargs):
        assert kwargs["color"] == "Blue"
        assert kwargs["size"] == "M"

        return [
            {
                "product_id": "product-1",
                "variant_id": "variant-1",
                "product": {
                    "name": "Printed Lawn Kurta",
                    "brand": "Khaadi",
                    "material": "Lawn",
                },
                "variant": {
                    "sku": "KURTA-BLU-M",
                    "price": 3000,
                    "color": {"name": "Blue"},
                    "size": {"name": "M"},
                },
                "pricing": {
                    "effective_price": 2500,
                },
                "images": [],
                "inventory": [
                    {"available_quantity": 4}
                ],
            }
        ]

    monkeypatch.setattr(
        orchestrator_module.product_agent,
        "search",
        fake_search,
    )

    response = orchestrator_agent.process_turn(
        customer_id="customer-1",
        message="Show me blue kurtas size M",
    )

    assert response.conversation_id == "conversation-1"
    assert len(response.blocks) == 1
    assert isinstance(response.blocks[0], ProductCarouselBlock)

    assert fake_persistence["last_search_variant_ids"] == [
        "variant-1"
    ]
    assert fake_persistence["last_variant_id"] == "variant-1"


def test_orchestrator_stock_check_from_second_result(
    monkeypatch,
    fake_persistence,
):
    fake_persistence["last_search_variant_ids"] = [
        "variant-1",
        "variant-2",
    ]

    def fake_stock(variant_id):
        assert variant_id == "variant-2"

        return [
            {
                "branch_id": "branch-1",
                "variant_id": variant_id,
                "available_quantity": 3,
                "status": "available",
                "branch": {
                    "id": "branch-1",
                    "name": "Gulberg",
                    "city": "Lahore",
                    "area": "Gulberg",
                    "address": "Test address",
                },
            }
        ]

    monkeypatch.setattr(
        orchestrator_module.inventory_agent,
        "get_stock_snapshot_with_branches",
        fake_stock,
    )

    response = orchestrator_agent.process_turn(
        customer_id="customer-1",
        conversation_id="conversation-1",
        message="Is the second one available?",
    )

    assert len(response.blocks) == 1
    assert isinstance(response.blocks[0], StockStatusBlock)
    assert response.blocks[0].variant_id == "variant-2"
    assert response.blocks[0].branches[0].available_quantity == 3
    assert fake_persistence["last_variant_id"] == "variant-2"


def test_orchestrator_creates_auto_buy_smart_cart(
    monkeypatch,
    fake_persistence,
):
    fake_persistence["last_search_variant_ids"] = [
        "variant-1",
        "variant-2",
    ]

    called = {}

    def fake_create_rule(
        customer_id,
        variant_id,
        quantity,
        target_price,
        min_discount_percentage,
        authorization_mode,
        branch_id,
    ):
        called.update(
            {
                "customer_id": customer_id,
                "variant_id": variant_id,
                "quantity": quantity,
                "target_price": target_price,
                "min_discount_percentage": min_discount_percentage,
                "authorization_mode": authorization_mode,
                "branch_id": branch_id,
            }
        )

        return {
            "id": "rule-1",
            "customer_id": customer_id,
            "variant_id": variant_id,
            "branch_id": branch_id,
            "quantity": quantity,
            "target_price": target_price,
            "min_discount_percentage": min_discount_percentage,
            "authorization_mode": authorization_mode,
            "status": "active",
        }

    monkeypatch.setattr(
        orchestrator_module,
        "create_customer_smart_cart_rule",
        fake_create_rule,
    )

    response = orchestrator_agent.process_turn(
        customer_id="customer-1",
        conversation_id="conversation-1",
        message=(
            "Auto buy the second one if the price drops below Rs 2500"
        ),
    )

    assert called["variant_id"] == "variant-2"
    assert called["target_price"] == 2500
    assert called["authorization_mode"] == "auto_buy"
    assert len(response.blocks) == 1
    assert isinstance(response.blocks[0], SmartCartRuleBlock)
    assert fake_persistence["last_smart_cart_rule_id"] == "rule-1"


def test_orchestrator_creates_notify_only_discount_rule(
    monkeypatch,
    fake_persistence,
):
    fake_persistence["last_search_variant_ids"] = [
        "variant-1",
    ]

    called = {}

    def fake_create_rule(
        customer_id,
        variant_id,
        quantity,
        target_price,
        min_discount_percentage,
        authorization_mode,
        branch_id,
    ):
        called["variant_id"] = variant_id
        called["discount"] = min_discount_percentage
        called["mode"] = authorization_mode

        return {
            "id": "rule-2",
            "customer_id": customer_id,
            "variant_id": variant_id,
            "branch_id": branch_id,
            "quantity": quantity,
            "target_price": target_price,
            "min_discount_percentage": min_discount_percentage,
            "authorization_mode": authorization_mode,
            "status": "active",
        }

    monkeypatch.setattr(
        orchestrator_module,
        "create_customer_smart_cart_rule",
        fake_create_rule,
    )

    response = orchestrator_agent.process_turn(
        customer_id="customer-1",
        conversation_id="conversation-1",
        message="First wala 20% discount pe notify karna",
    )

    assert called["variant_id"] == "variant-1"
    assert called["discount"] == 20
    assert called["mode"] == "notify_only"
    assert isinstance(response.blocks[0], SmartCartRuleBlock)


def test_smart_cart_without_authorization_asks_clarification(
    monkeypatch,
    fake_persistence,
):
    fake_persistence["last_search_variant_ids"] = [
        "variant-1",
    ]

    called = {"value": False}

    def fake_create_rule(*args, **kwargs):
        called["value"] = True
        raise AssertionError("Smart Cart service must not be called.")

    monkeypatch.setattr(
        orchestrator_module,
        "create_customer_smart_cart_rule",
        fake_create_rule,
    )

    response = orchestrator_agent.process_turn(
        customer_id="customer-1",
        conversation_id="conversation-1",
        message=(
            "Put the first one in Smart Cart if it drops below Rs 2500"
        ),
    )

    assert called["value"] is False
    assert response.blocks == []
    assert (
        "notify" in response.content.lower()
        or "automatic" in response.content.lower()
    )


def test_orchestrator_adds_second_result_to_cart(
    monkeypatch,
    fake_persistence,
):
    fake_persistence["last_search_variant_ids"] = [
        "variant-1",
        "variant-2",
    ]

    called = {}

    def fake_add_cart_item(customer_id, variant_id, quantity):
        called["customer_id"] = customer_id
        called["variant_id"] = variant_id
        called["quantity"] = quantity

        return {
            "cart": {"id": "cart-1"},
            "items": [
                {
                    "id": "item-1",
                    "variant_id": variant_id,
                    "quantity": quantity,
                }
            ],
            "item_count": 1,
        }

    monkeypatch.setattr(
        orchestrator_module,
        "add_cart_item",
        fake_add_cart_item,
    )

    response = orchestrator_agent.process_turn(
        customer_id="customer-1",
        conversation_id="conversation-1",
        message="Add the second one to cart",
    )

    assert called["variant_id"] == "variant-2"
    assert called["quantity"] == 1
    assert len(response.blocks) == 1
    assert isinstance(response.blocks[0], CartSummaryBlock)
    assert fake_persistence["last_variant_id"] == "variant-2"


def test_orchestrator_adds_context_item_to_wishlist(
    monkeypatch,
    fake_persistence,
):
    fake_persistence["last_variant_id"] = "variant-9"

    called = {}

    def fake_add_wishlist_item(customer_id, variant_id):
        called["customer_id"] = customer_id
        called["variant_id"] = variant_id

        return {
            "items": [
                {
                    "id": "wishlist-1",
                    "variant_id": variant_id,
                }
            ],
            "count": 1,
        }

    monkeypatch.setattr(
        orchestrator_module,
        "add_wishlist_item",
        fake_add_wishlist_item,
    )

    response = orchestrator_agent.process_turn(
        customer_id="customer-1",
        conversation_id="conversation-1",
        message="Put it in my wishlist",
    )

    assert called["variant_id"] == "variant-9"
    assert len(response.blocks) == 1
    assert isinstance(response.blocks[0], WishlistBlock)


def test_cart_out_of_range_reference_asks_clarification(
    monkeypatch,
    fake_persistence,
):
    fake_persistence["last_search_variant_ids"] = [
        "variant-1",
    ]

    called = {"value": False}

    def fake_add_cart_item(*args, **kwargs):
        called["value"] = True
        raise AssertionError("Cart service must not be called.")

    monkeypatch.setattr(
        orchestrator_module,
        "add_cart_item",
        fake_add_cart_item,
    )

    response = orchestrator_agent.process_turn(
        customer_id="customer-1",
        conversation_id="conversation-1",
        message="Add the third one to cart",
    )

    assert called["value"] is False
    assert response.blocks == []
    assert (
        "which" in response.content.lower()
        or "kaunsa" in response.content.lower()
    )


def test_orchestrator_purchases_second_result(
    monkeypatch,
    fake_persistence,
):
    fake_persistence["last_search_variant_ids"] = [
        "variant-1",
        "variant-2",
    ]

    called = {}

    def fake_purchase(
        customer_id,
        variant_id,
        quantity,
        idempotency_key,
        branch_id=None,
        reservation_id=None,
    ):
        called.update(
            {
                "customer_id": customer_id,
                "variant_id": variant_id,
                "quantity": quantity,
                "idempotency_key": idempotency_key,
                "branch_id": branch_id,
                "reservation_id": reservation_id,
            }
        )

        return {
            "success": True,
            "order_id": "order-123",
            "purchase_attempt_id": "attempt-123",
            "reason_code": None,
            "reason": None,
        }

    monkeypatch.setattr(
        orchestrator_module.purchase_agent,
        "purchase",
        fake_purchase,
    )

    response = orchestrator_agent.process_turn(
        customer_id="customer-1",
        conversation_id="conversation-1",
        message="Buy the second one now",
    )

    assert called["variant_id"] == "variant-2"
    assert called["quantity"] == 1
    assert (
        called["idempotency_key"]
        == "chat-purchase:conversation-1:message-1"
    )
    assert len(response.blocks) == 1
    assert isinstance(response.blocks[0], OrderConfirmationBlock)
    assert response.blocks[0].order["order_id"] == "order-123"
    assert fake_persistence["last_order_id"] == "order-123"


def test_failed_purchase_has_no_confirmation_block(
    monkeypatch,
    fake_persistence,
):
    fake_persistence["last_variant_id"] = "variant-9"

    def fake_purchase(**kwargs):
        return {
            "success": False,
            "order_id": None,
            "purchase_attempt_id": "attempt-failed",
            "reason_code": "insufficient_stock",
            "reason": "Insufficient available stock.",
        }

    monkeypatch.setattr(
        orchestrator_module.purchase_agent,
        "purchase",
        fake_purchase,
    )

    response = orchestrator_agent.process_turn(
        customer_id="customer-1",
        conversation_id="conversation-1",
        message="Buy it now",
    )

    assert response.blocks == []
    assert "insufficient" in response.content.lower()
    assert (
        fake_persistence["last_purchase_failure_code"]
        == "insufficient_stock"
    )
    assert "last_order_id" not in fake_persistence


def test_purchase_without_item_reference_does_not_execute(
    monkeypatch,
    fake_persistence,
):
    called = {"value": False}

    def fake_purchase(*args, **kwargs):
        called["value"] = True
        raise AssertionError(
            "Purchase Agent must not be called without an exact item."
        )

    monkeypatch.setattr(
        orchestrator_module.purchase_agent,
        "purchase",
        fake_purchase,
    )

    response = orchestrator_agent.process_turn(
        customer_id="customer-1",
        conversation_id="conversation-1",
        message="Buy now",
    )

    assert called["value"] is False
    assert response.blocks == []
