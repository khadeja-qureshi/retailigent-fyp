import pytest
from app.agents.customer_interaction_agent import (
    customer_interaction_agent,
    detect_language,
)


def test_detects_english():
    assert (
        detect_language(
            "Show me blue kurtas"
        )
        == "english"
    )


def test_detects_roman_urdu():
    assert (
        detect_language(
            "Mujhe kurta chahiye"
        )
        == "roman_urdu"
    )


def test_detects_mixed_language():
    assert (
        detect_language(
            "Mujhe blue kurta "
            "size M dikhao"
        )
        == "mixed"
    )


def test_product_search_extracts_entities():
    parsed = (
        customer_interaction_agent
        .parse(
            "Show me blue kurtas "
            "size M under Rs 3000"
        )
    )

    assert (
        parsed.intent
        == "product_search"
    )

    assert (
        parsed.entities.category
        == "kurta"
    )

    assert (
        parsed.entities.color
        == "Blue"
    )

    assert (
        parsed.entities.size
        == "M"
    )

    assert (
        parsed.entities.max_price
        == 3000
    )

    assert (
        parsed.requires_clarification
        is False
    )


def test_stock_check_uses_ordinal_reference():
    parsed = (
        customer_interaction_agent
        .parse(
            "Is the first one "
            "available?"
        )
    )

    assert (
        parsed.intent
        == "stock_check"
    )

    assert (
        parsed.entities
        .ordinal_reference
        == 1
    )

    assert (
        parsed.requires_clarification
        is False
    )


def test_add_second_result_to_cart():
    parsed = (
        customer_interaction_agent
        .parse(
            "Add the second one "
            "to cart"
        )
    )

    assert (
        parsed.intent
        == "add_to_cart"
    )

    assert (
        parsed.entities
        .ordinal_reference
        == 2
    )

    assert (
        parsed.requires_clarification
        is False
    )


def test_smart_cart_auto_buy_target():
    parsed = (
        customer_interaction_agent
        .parse(
            "Buy the first one "
            "automatically if the "
            "price drops below Rs 2500"
        )
    )

    assert (
        parsed.intent
        == "smart_cart_create"
    )

    assert (
        parsed.entities
        .ordinal_reference
        == 1
    )

    assert (
        parsed.entities
        .target_price
        == 2500
    )

    assert (
        parsed.entities
        .authorization_mode
        == "auto_buy"
    )

    assert (
        parsed.requires_clarification
        is False
    )

@pytest.mark.parametrize(
    ("message", "expected_price"),
    [
        ("buy it price falls below 1500 rupees", 1500),
        ("buy it below 1500", 1500),
        ("buy it if the price falls below 1500 rupees", 1500),
        ("buy it when the price falls below 1500 rupees", 1500),
    ],
)
def test_conditional_purchase_with_price_threshold(
    message,
    expected_price,
):
    parsed = customer_interaction_agent.parse(message)

    assert parsed.intent == "smart_cart_create"
    assert parsed.entities.target_price == expected_price
    assert parsed.entities.authorization_mode == "auto_buy"
    assert parsed.requires_clarification is False


def test_immediate_purchase_still_works():
    parsed = customer_interaction_agent.parse("buy it now")

    assert parsed.intent == "purchase"
    assert parsed.requires_clarification is False


def test_smart_cart_notify_only():
    parsed = (
        customer_interaction_agent
        .parse(
            "Put the first one in "
            "Smart Cart and notify me "
            "if it gets 20% discount"
        )
    )

    assert (
    parsed.intent
    == "smart_cart_create"
)

    # The message explicitly says
    # notify rather than auto-buy.
    assert (
        parsed.entities
        .authorization_mode
        == "notify_only"
    )

    assert (
        parsed.entities
        .min_discount_percentage
        == 20
    )


def test_purchase_context_reference():
    parsed = (
        customer_interaction_agent
        .parse(
            "Buy it now"
        )
    )

    assert (
        parsed.intent
        == "purchase"
    )

    assert (
        parsed.requires_clarification
        is False
    )


def test_cart_without_item_asks_for_clarification():
    parsed = (
        customer_interaction_agent
        .parse(
            "Add to cart"
        )
    )

    assert (
        parsed.intent
        == "add_to_cart"
    )

    assert (
        parsed.requires_clarification
        is True
    )

    assert (
        parsed.clarification_question
        is not None
    )


def test_variant_uuid_is_extracted():
    variant_id = (
        "f1000000-0000-0000-"
        "0000-000000000003"
    )

    parsed = (
        customer_interaction_agent
        .parse(
            f"Is variant {variant_id} "
            "available in Clifton?"
        )
    )

    assert (
        parsed.intent
        == "stock_check"
    )

    assert (
        parsed.entities.variant_id
        == variant_id
    )

    assert (
        parsed.entities.branch_name
        == "Clifton"
    )

def test_put_context_item_in_wishlist():
    parsed = (
        customer_interaction_agent
        .parse(
            "Put it in my wishlist"
        )
    )

    assert (
        parsed.intent
        == "add_to_wishlist"
    )

    assert (
        parsed.requires_clarification
        is False
    )

def test_discount_notify_becomes_smart_cart():
    parsed = (
        customer_interaction_agent
        .parse(
            "First wala 20% discount "
            "pe notify karna"
        )
    )

    assert (
        parsed.intent
        == "smart_cart_create"
    )

    assert (
        parsed.entities
        .ordinal_reference
        == 1
    )

    assert (
        parsed.entities
        .min_discount_percentage
        == 20
    )

    assert (
        parsed.entities
        .authorization_mode
        == "notify_only"
    )

    assert (
        parsed.requires_clarification
        is False
    )


def test_support_intent_detects_english_complaint():
    parsed = customer_interaction_agent.parse(
        "My order is delayed and I want to complain"
    )
    assert parsed.intent == "support_request"


def test_support_intent_detects_human_agent_request():
    parsed = customer_interaction_agent.parse(
        "Please connect me to a human agent"
    )
    assert parsed.intent == "support_request"


def test_support_intent_detects_roman_urdu():
    parsed = customer_interaction_agent.parse(
        "Mujhe shikayat karni hai, support chahiye"
    )
    assert parsed.intent == "support_request"


def test_support_intent_detects_mixed_language():
    parsed = customer_interaction_agent.parse(
        "My order late hai, please help"
    )
    assert parsed.intent == "support_request"


def test_product_search_still_works():
    parsed = customer_interaction_agent.parse(
        "Show me blue kurtas size M"
    )
    assert parsed.intent == "product_search"

@pytest.mark.parametrize(
    "message",
    [
        "Do you have blue kurtas in size M?",
        "Do you have this in stock?",
        "Is this item available?",
        "Blue kurta size M mil jayega?",
        "Black shirt stock mein hai kya?",
        "Do you sell white kurtas?",
    ],
)
def test_availability_questions_detect_stock_check(message):
    parsed = customer_interaction_agent.parse(message)

    assert parsed.intent == "stock_check"


def test_vague_availability_question_is_recognized():
    parsed = customer_interaction_agent.parse("Do you have this?")

    assert parsed.intent == "stock_check"


def test_product_search_still_works_after_availability_detection():
    parsed = customer_interaction_agent.parse(
        "Show me blue kurtas size M"
    )

    assert parsed.intent == "product_search"
    assert parsed.entities.color == "Blue"
    assert parsed.entities.size == "M"

@pytest.mark.parametrize(
    "message",
    [
        "What types of products do you have?",
        "What categories do you sell?",
        "What products do you offer?",
        "What kind of items can I buy?",
        "Aap kya kya sell karte hain?",
        "Aap ke paas kya kya milta hai?",
    ],
)
def test_catalog_discovery_questions_detect_catalog_discovery(
    message,
):
    parsed = customer_interaction_agent.parse(message)

    assert parsed.intent == "catalog_discovery"
    assert parsed.requires_clarification is False


def test_specific_product_search_remains_product_search():
    parsed = customer_interaction_agent.parse(
        "Show me blue kurtas size M"
    )

    assert parsed.intent == "product_search"


def test_stock_question_remains_stock_check():
    parsed = customer_interaction_agent.parse(
        "Do you have blue kurtas in size M?"
    )

    assert parsed.intent == "stock_check"
