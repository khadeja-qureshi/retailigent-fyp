from __future__ import annotations

import logging
import re

from concurrent.futures import (
    ThreadPoolExecutor,
)
from dataclasses import dataclass
from typing import Any, Callable

from app.agents.customer_interaction_agent import (
    customer_interaction_agent,
)
from app.agents.inventory_agent import (
    inventory_agent,
)
from app.agents.memory_agent import (
    memory_agent,
)
from app.agents.product_agent import (
    product_agent,
)
from app.agents.recommendation_agent import (
    recommendation_agent,
)
from app.agents.location_agent import (
    location_agent,
)
from app.agents.support_agent import (
    support_agent,
)
from app.agents.purchase_agent import (
    purchase_agent,
)
from app.agents.alert_agent import (
    alert_agent,
)
from app.schemas.chat import (
    AlertBlock,
    CartSummaryBlock,
    BranchMapBlock,
    ChatTurnResponse,
    SupportEscalationBlock,
    OrderConfirmationBlock,
    ParsedCustomerMessage,
    ProductCard,
    ReservationBlock,
    RecommendationBlock,
    ProductCarouselBlock,
    SmartCartRuleBlock,
    StockBranchItem,
    StockStatusBlock,
    WishlistBlock,
)
from app.services import chat_service, feedback_service
from app.services.feedback_service import (
    FeedbackServiceError,
)
from app.services.reservation_service import (
    create_customer_reservation,
)

from app.services.cart_service import (
    add_cart_item,
)
from app.services.smart_cart_service import (
    create_customer_smart_cart_rule,
)
from app.services.wishlist_service import (
    add_wishlist_item,
)
from app.services.support_service import (
    SupportTicketError,
    add_customer_support_message,
    create_support_ticket,
    get_latest_open_support_ticket,
)
from app.services.demand_signal_service import (
    record_demand_signal,
)
from app.services.preference_capture_service import (
    capture_explicit_preferences,
)


logger = logging.getLogger(
    __name__
)


def _extract_stock_requested_quantity(
    message: str,
    parsed: ParsedCustomerMessage,
) -> int | None:
    """
    Extract the requested quantity specifically for stock-check questions.

    Examples supported:
        Do you have 500 of the second kurta in stock?
        Do you have 25 units of this?
        Is quantity 40 available?
        500 of the first shirt

    Structured parser quantity is preferred when available.

    The fallback patterns deliberately avoid ordinal references such as
    "second", so "500 of the second kurta" resolves quantity=500 rather
    than quantity=2.
    """

    if parsed.entities.quantity is not None:
        try:
            quantity = int(
                parsed.entities.quantity
            )

        except (
            TypeError,
            ValueError,
        ):
            quantity = 0

        if quantity > 0:
            return quantity

    text = re.sub(
        r"\s+",
        " ",
        message
        .strip()
        .casefold(),
    )

    patterns = (
        # "do you have 500 of ..."
        r"\b(?:have|has)\s+(\d+)\b",

        # "500 units / 500 pieces / 500 items"
        r"\b(\d+)\s+"
        r"(?:units?|pieces?|items?|pcs?)\b",

        # "quantity 500" / "qty: 500"
        r"\b(?:quantity|qty)\s*"
        r"(?:is|=|:)?\s*(\d+)\b",

        # "500 of the second kurta"
        r"\b(\d+)\s+of\b",
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        try:
            quantity = int(
                match.group(1)
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        if quantity > 0:
            return quantity

    return None


def _looks_like_feedback(message: str) -> bool:
    text = re.sub(r"\s+", " ", message.strip().casefold())

    if not text:
        return False

    explicit_feedback_terms = (
        "feedback",
        "review",
        "experience",
        "rating",
    )

    feedback_subject_terms = (
        "checkout",
        "website",
        "app",
        "shopping assistant",
        "assistant",
        "chatbot",
        "service",
        "support",
        "store",
        "branch",
        "delivery",
        "product",
        "quality",
    )

    evaluative_terms = (
        "terrible",
        "confusing",
        "helpful",
        "easy to use",
        "great",
        "excellent",
        "good",
        "bad",
        "poor",
        "awful",
        "amazing",
        "satisfied",
        "disappointed",
        "bekar",
        "bura",
        "kharaab",
        "kharab",
        "acha",
        "achha",
        "theek",
        "thora confusing",
        "bohat acha",
        "bohat kharab",
    )

    if any(term in text for term in explicit_feedback_terms):
        return True

    has_subject = any(
        term in text
        for term in feedback_subject_terms
    )

    has_evaluation = any(
        term in text
        for term in evaluative_terms
    )

    return has_subject and has_evaluation


def _infer_feedback_type(message: str) -> str:
    text = message.strip().casefold()

    if any(term in text for term in (
        "checkout",
        "website",
        "web page",
        "app",
        "login",
    )):
        return "website"

    if any(term in text for term in (
        "shopping assistant",
        "assistant",
        "chatbot",
        "bot",
        "agent",
    )):
        return "agent"

    if any(term in text for term in (
        "delivery",
        "shipping",
        "courier",
        "parcel",
    )):
        return "delivery"

    if any(term in text for term in (
        "store",
        "branch",
        "shop",
    )):
        return "store"

    if any(term in text for term in (
        "product",
        "quality",
        "fabric",
        "size",
        "colour",
        "color",
    )):
        return "product"

    if any(term in text for term in (
        "support",
        "service",
        "staff",
        "representative",
    )):
        return "service"

    return "general"


@dataclass(
    frozen=True
)
class PlannedTask:
    agent_key: str
    task_type: str
    tool_name: str


_CONTEXT_REFERENCE_RE = re.compile(
    r"\b("
    r"it|"
    r"this|"
    r"that|"
    r"this one|"
    r"that one|"
    r"isko|"
    r"isse|"
    r"yeh|"
    r"ye"
    r")\b",
    flags=re.IGNORECASE,
)


def resolve_variant_reference(
    parsed: ParsedCustomerMessage,
    state: dict,
) -> str | None:
    """
    Resolve one exact variant.

    Priority:
    1. explicit variant UUID
    2. ordinal from previous search
    3. contextual pronoun using the last variant
    """

    if parsed.entities.variant_id:
        return (
            parsed
            .entities
            .variant_id
        )

    ordinal = (
        parsed
        .entities
        .ordinal_reference
    )

    if ordinal is not None:
        variant_ids = (
            state.get(
                "last_search_variant_ids"
            )
            or []
        )

        index = ordinal - 1

        if (
            0
            <= index
            < len(variant_ids)
        ):
            return str(
                variant_ids[index]
            )

        return None

    if _CONTEXT_REFERENCE_RE.search(
        parsed.raw_message
    ):
        last_variant_id = (
            state.get(
                "last_variant_id"
            )
        )

        if last_variant_id:
            return str(
                last_variant_id
            )
    # A reservation can refer to "1 item" without
    # using a pronoun. Reuse context only when the
    # immediately preceding intent was a stock check
    # and that search identified exactly one variant.
    if (
        parsed.intent == "reservation_create"
        and state.get("last_intent") == "stock_check"
    ):
        last_search_variant_ids = (
            state.get("last_search_variant_ids") or []
        )

        if len(last_search_variant_ids) == 1:
            return str(last_search_variant_ids[0])

        if (
            not last_search_variant_ids
            and state.get("last_variant_id")
        ):
            return str(state["last_variant_id"])

    return None


def resolve_variant_references(
    parsed: ParsedCustomerMessage,
    state: dict,
) -> list[str]:
    """
    Resolve one or more independent variant
    references.

    Multiple ordinals such as "first and second"
    are used by the Orchestrator for parallel
    specialist execution.
    """

    if parsed.entities.variant_id:
        return [
            parsed.entities.variant_id
        ]

    ordinals = (
        parsed
        .entities
        .ordinal_references
        or (
            [
                parsed
                .entities
                .ordinal_reference
            ]
            if (
                parsed
                .entities
                .ordinal_reference
                is not None
            )
            else []
        )
    )

    if ordinals:
        variant_ids = (
            state.get(
                "last_search_variant_ids"
            )
            or []
        )

        resolved: list[str] = []

        for ordinal in ordinals:
            index = ordinal - 1

            if not (
                0
                <= index
                < len(variant_ids)
            ):
                return []

            variant_id = str(
                variant_ids[index]
            )

            if (
                variant_id
                not in resolved
            ):
                resolved.append(
                    variant_id
                )

        return resolved

    single = (
        resolve_variant_reference(
            parsed,
            state,
        )
    )

    if not single:
        return []

    return [
        single
    ]


def plan_intent(
    intent: str,
) -> PlannedTask | None:
    if intent == "product_search":
        return PlannedTask(
            agent_key=(
                "product_agent"
            ),
            task_type=(
                "product_search"
            ),
            tool_name=(
                "product_agent.search"
            ),
        )

    if intent == "store_location_search":
        return PlannedTask(
            agent_key="location_agent",
            task_type="branch_location_search",
            tool_name="location_agent.search",
        )

    if intent == "recommendation_search":
        return PlannedTask(
            agent_key="recommendation_agent",
            task_type="personalized_recommendations",
            tool_name="recommendation_agent.recommend",
        )

    if intent == "stock_check":
        return PlannedTask(
            agent_key=(
                "inventory_agent"
            ),
            task_type=(
                "stock_check"
            ),
            tool_name=(
                "inventory_agent."
                "get_stock_snapshot_with_branches"
            ),
        )

    if intent == "reservation_create":
        return PlannedTask(
            agent_key="orchestrator_agent",
            task_type="create_reservation",
            tool_name=(
                "reservation_service."
                "create_customer_reservation"
            ),
        )

    if intent == "add_to_cart":
        return PlannedTask(
            agent_key=(
                "orchestrator_agent"
            ),
            task_type=(
                "add_to_cart"
            ),
            tool_name=(
                "cart_service."
                "add_cart_item"
            ),
        )

    if intent == "add_to_wishlist":
        return PlannedTask(
            agent_key=(
                "orchestrator_agent"
            ),
            task_type=(
                "add_to_wishlist"
            ),
            tool_name=(
                "wishlist_service."
                "add_wishlist_item"
            ),
        )

    if intent == "smart_cart_create":
        return PlannedTask(
            agent_key=(
                "orchestrator_agent"
            ),
            task_type=(
                "create_smart_cart_rule"
            ),
            tool_name=(
                "smart_cart_service."
                "create_customer_smart_cart_rule"
            ),
        )

    if intent == "alert_create":
        return PlannedTask(
            agent_key="alert_agent",
            task_type="create_alert",
            tool_name="alert_agent.create",
        )

    if intent == "purchase":
        return PlannedTask(
            agent_key=(
                "purchase_agent"
            ),
            task_type=(
                "purchase"
            ),
            tool_name=(
                "purchase_agent.purchase"
            ),
        )

    return None


def _primary_image_url(
    result: dict,
) -> str | None:
    images = (
        result.get(
            "images"
        )
        or []
    )

    primary = next(
        (
            image
            for image in images
            if image.get(
                "is_primary"
            )
        ),
        None,
    )

    if (
        primary is None
        and images
    ):
        primary = images[0]

    if not primary:
        return None

    return (
        primary.get(
            "image_url"
        )
    )


def _max_available(
    result: dict,
) -> int:
    inventory = (
        result.get(
            "inventory"
        )
        or []
    )

    return max(
        (
            int(
                row.get(
                    "available_quantity"
                )
                or 0
            )
            for row in inventory
        ),
        default=0,
    )


def build_product_carousel(
    results: list[dict],
) -> ProductCarouselBlock:
    """
    Validate Product Agent rows before exposing
    them as chat blocks.
    """

    products: list[
        ProductCard
    ] = []

    for result in results:
        product = (
            result.get(
                "product"
            )
            or {}
        )

        variant = (
            result.get(
                "variant"
            )
            or {}
        )

        pricing = (
            result.get(
                "pricing"
            )
            or {}
        )

        color = (
            variant.get(
                "color"
            )
            or {}
        )

        size = (
            variant.get(
                "size"
            )
            or {}
        )

        product_id = (
            result.get(
                "product_id"
            )
        )

        variant_id = (
            result.get(
                "variant_id"
            )
        )

        name = (
            product.get(
                "name"
            )
        )

        sku = (
            variant.get(
                "sku"
            )
        )

        if not all(
            [
                product_id,
                variant_id,
                name,
                sku,
            ]
        ):
            continue

        effective_price = (
            pricing.get(
                "effective_price"
            )
        )

        if effective_price is None:
            effective_price = (
                variant.get(
                    "price"
                )
            )

        products.append(
            ProductCard(
                product_id=str(
                    product_id
                ),
                variant_id=str(
                    variant_id
                ),
                name=str(
                    name
                ),
                sku=str(
                    sku
                ),
                brand=(
                    product.get(
                        "brand"
                    )
                ),
                material=(
                    product.get(
                        "material"
                    )
                ),
                color=(
                    color.get(
                        "name"
                    )
                ),
                size=(
                    size.get(
                        "name"
                    )
                ),
                effective_price=(
                    float(
                        effective_price
                    )
                    if (
                        effective_price
                        is not None
                    )
                    else None
                ),
                image_url=(
                    _primary_image_url(
                        result
                    )
                ),
                max_available_at_one_branch=(
                    _max_available(
                        result
                    )
                ),
            )
        )

    return ProductCarouselBlock(
        title="Products",
        products=products,
    )


def _normalize_catalog_text(value: Any) -> str:
    text = str(value or "").strip().casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _result_product_name(result: dict[str, Any]) -> str:
    return str(
        (result.get("product") or {}).get("name")
        or ""
    ).strip()


def _filter_named_product_results(
    results: list[dict[str, Any]],
    product_name: str | None,
) -> list[dict[str, Any]]:
    """Keep an explicitly named product as a hard constraint."""
    if not product_name:
        return list(results)

    requested = _normalize_catalog_text(product_name)
    requested_tokens = set(requested.split())

    filtered: list[dict[str, Any]] = []

    for result in results:
        actual = _normalize_catalog_text(
            _result_product_name(result)
        )

        if not actual:
            continue

        if actual == requested:
            filtered.append(result)
            continue

        actual_tokens = set(actual.split())

        if not requested_tokens:
            continue

        coverage = (
            len(requested_tokens & actual_tokens)
            / len(requested_tokens)
        )

        if coverage >= 0.8:
            filtered.append(result)

    return filtered


def _unique_variant_ids_from_results(
    results: list[dict[str, Any]],
) -> list[str]:
    output: list[str] = []

    for result in results:
        value = result.get("variant_id")

        if not value:
            continue

        variant_id = str(value)

        if variant_id not in output:
            output.append(variant_id)

    return output


def _inventory_available_quantity(row: dict[str, Any]) -> int:
    try:
        return max(
            0,
            int(row.get("available_quantity") or 0),
        )
    except (TypeError, ValueError):
        return 0


def _location_matches_branch(
    branch: dict[str, Any],
    requested_location: str | None,
) -> bool:
    if not requested_location:
        return True

    requested = _normalize_catalog_text(requested_location)

    if not requested:
        return True

    name = _normalize_catalog_text(branch.get("name"))
    city = _normalize_catalog_text(branch.get("city"))
    area = _normalize_catalog_text(branch.get("area"))
    address = _normalize_catalog_text(branch.get("address"))

    if requested in {name, city, area}:
        return True

    if name and (requested in name or name in requested):
        return True

    if area and (requested in area or area in requested):
        return True

    if address and requested in address:
        return True

    return False


def _split_inventory_for_location(
    rows: list[dict[str, Any]],
    requested_location: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not requested_location:
        return list(rows), []

    matching: list[dict[str, Any]] = []
    other: list[dict[str, Any]] = []

    for row in rows:
        branch = row.get("branch") or {}

        if _location_matches_branch(branch, requested_location):
            matching.append(row)
        else:
            other.append(row)

    return matching, other


def _total_available(rows: list[dict[str, Any]]) -> int:
    return sum(
        _inventory_available_quantity(row)
        for row in rows
    )


def _positive_inventory_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if _inventory_available_quantity(row) > 0
    ]


def _available_size_names(
    results: list[dict[str, Any]],
) -> list[str]:
    values: set[str] = set()

    for result in results:
        inventory = result.get("inventory") or []

        if not any(
            _inventory_available_quantity(row) > 0
            for row in inventory
        ):
            continue

        size = (
            (result.get("variant") or {}).get("size")
            or {}
        )
        name = str(size.get("name") or "").strip()

        if name:
            values.add(name)

    return sorted(values)


def _available_color_names(
    results: list[dict[str, Any]],
) -> list[str]:
    values: set[str] = set()

    for result in results:
        inventory = result.get("inventory") or []

        if not any(
            _inventory_available_quantity(row) > 0
            for row in inventory
        ):
            continue

        color = (
            (result.get("variant") or {}).get("color")
            or {}
        )
        name = str(color.get("name") or "").strip()

        if name:
            values.add(name)

    return sorted(values)


def _format_branch_alternatives(
    rows: list[dict[str, Any]],
) -> str:
    parts: list[str] = []

    for row in sorted(
        _positive_inventory_rows(rows),
        key=lambda item: -_inventory_available_quantity(item),
    )[:5]:
        branch = row.get("branch") or {}
        name = str(branch.get("name") or "Branch").strip()
        city = str(branch.get("city") or "").strip()
        quantity = _inventory_available_quantity(row)
        label = f"{name}, {city}" if city else name
        parts.append(
            f"{label}: {quantity} unit{'s' if quantity != 1 else ''}"
        )

    return "; ".join(parts)


def _build_catalog_query(
    parsed: ParsedCustomerMessage,
) -> str:
    """Build a clean search query while preserving free-text semantics.

    Structured bilingual requests should not send filler/action words such
    as "mujhe", "chahiye", "available hai" into hybrid retrieval. When the
    parser has useful hard attributes, use those attributes as the retrieval
    query and keep the same attributes as authoritative filters.

    Free-text semantic requests with no structured attributes still use the
    original customer message unchanged.
    """

    if parsed.entities.product_name:
        return parsed.entities.product_name.strip()

    parts: list[str] = []

    for value in (
        parsed.entities.color,
        parsed.entities.material,
        parsed.entities.category,
    ):
        if value:
            text = str(value).strip()
            if text and text.casefold() not in {
                item.casefold()
                for item in parts
            }:
                parts.append(text)

    if parts:
        return " ".join(parts)

    return parsed.raw_message.strip()


def _combined_cart_wishlist_request(message: str) -> bool:
    text = _normalize_catalog_text(message)
    return "cart" in text and "wishlist" in text


def _resolve_named_action_variant(
    *,
    parsed: ParsedCustomerMessage,
    state: dict,
    customer_id: str,
) -> tuple[str | None, list[dict[str, Any]]]:
    """Resolve Cart/Wishlist actions without overriding explicit context."""
    existing_reference = resolve_variant_reference(
        parsed,
        state,
    )

    if existing_reference:
        return existing_reference, []

    # An explicit but out-of-range ordinal must stay unresolved.
    # Never turn "the third one" into a semantic product search.
    if parsed.entities.ordinal_reference is not None:
        return None, []

    product_name = parsed.entities.product_name

    if product_name:
        results = product_agent.search(
            query=product_name,
            match_count=50,
            color=parsed.entities.color,
            size=parsed.entities.size,
            material=parsed.entities.material,
            category=parsed.entities.category,
            min_price=None,
            max_price=None,
            track_demand=False,
            customer_id=customer_id,
        )

        results = _filter_named_product_results(
            results,
            product_name,
        )

        variant_ids = _unique_variant_ids_from_results(results)

        if len(variant_ids) == 1:
            return variant_ids[0], results

        if variant_ids:
            last_variant = state.get("last_variant_id")

            if last_variant and str(last_variant) in variant_ids:
                return str(last_variant), results

        return None, results

    return None, []


def _is_nearest_location_request(message: str) -> bool:
    text = _normalize_catalog_text(message)
    return any(
        phrase in text
        for phrase in (
            "nearest branch",
            "nearest store",
            "closest branch",
            "closest store",
            "near me",
            "mere qareeb",
            "mere kareeb",
            "mere nazdeek",
            "mere nazdiq",
            "qareeb store",
            "qareeb branch",
            "kareeb store",
            "kareeb branch",
        )
    )


def _infer_alert_type(message: str) -> str:
    text = _normalize_catalog_text(message)

    if any(
        phrase in text
        for phrase in (
            "back in stock",
            "restock",
            "stock again",
            "available again",
        )
    ):
        return "restock"

    if any(
        phrase in text
        for phrase in (
            "goes on sale",
            "go on sale",
            "on sale",
            "sale alert",
        )
    ):
        return "sale"

    return "price_drop"


def _pending_action_payload(
    parsed: ParsedCustomerMessage,
    *,
    variant_id: str | None = None,
) -> dict[str, Any]:
    return {
        "intent": parsed.intent,
        "variant_id": (
            variant_id
            or parsed.entities.variant_id
        ),
        "product_name": parsed.entities.product_name,
        "category": parsed.entities.category,
        "color": parsed.entities.color,
        "size": parsed.entities.size,
        "material": parsed.entities.material,
        "branch_name": parsed.entities.branch_name,
        "quantity": parsed.entities.quantity,
        "target_price": parsed.entities.target_price,
        "min_discount_percentage": (
            parsed.entities.min_discount_percentage
        ),
        "authorization_mode": (
            parsed.entities.authorization_mode
        ),
        "alert_type": (
            _infer_alert_type(parsed.raw_message)
            if parsed.intent == "alert_create"
            else None
        ),
    }


def _resume_pending_action(
    parsed: ParsedCustomerMessage,
    state: dict[str, Any],
) -> ParsedCustomerMessage:
    pending = state.get("pending_action")

    if not isinstance(pending, dict):
        return parsed

    pending_intent = str(
        pending.get("intent")
        or ""
    )

    if pending_intent not in {
        "smart_cart_create",
        "alert_create",
        "reservation_create",
        "purchase",
    }:
        return parsed

    # A clearly new shopping/location/support request cancels the old
    # clarification rather than being hijacked by stale pending state.
    if parsed.intent not in {
        "unknown",
        "alert_create",
        "smart_cart_create",
    }:
        return parsed

    parsed.intent = pending_intent

    entities = parsed.entities

    for field in (
        "variant_id",
        "product_name",
        "category",
        "color",
        "size",
        "material",
        "branch_name",
        "quantity",
        "min_discount_percentage",
        "authorization_mode",
    ):
        if getattr(entities, field) is None:
            value = pending.get(field)
            if value is not None:
                setattr(entities, field, value)

    if entities.target_price is None:
        pending_target = pending.get("target_price")

        if pending_target is not None:
            entities.target_price = pending_target
        elif entities.max_price is not None:
            # A follow-up such as "below Rs. 2500" is parsed as a generic
            # max-price phrase.  While a Smart Cart/price-alert action is
            # pending, that value is the trigger price.
            entities.target_price = entities.max_price
            entities.max_price = None

    if pending_intent == "smart_cart_create":
        if (
            entities.target_price is None
            and entities.min_discount_percentage is None
        ):
            parsed.requires_clarification = True
            parsed.clarification_question = (
                customer_interaction_agent
                .compose_smart_cart_trigger_clarification(
                    parsed.language
                )
            )
        elif entities.authorization_mode is None:
            parsed.requires_clarification = True
            parsed.clarification_question = (
                customer_interaction_agent
                .compose_smart_cart_authorization_clarification(
                    parsed.language
                )
            )
        else:
            parsed.requires_clarification = False
            parsed.clarification_question = None

    elif pending_intent == "alert_create":
        alert_type = str(
            pending.get("alert_type")
            or _infer_alert_type(parsed.raw_message)
        )

        if (
            alert_type == "price_drop"
            and entities.target_price is None
        ):
            parsed.requires_clarification = True
            parsed.clarification_question = (
                "What target price should I watch for?"
                if parsed.language == "english"
                else "Kis target price par alert chahiye?"
            )
        else:
            parsed.requires_clarification = False
            parsed.clarification_question = None

    elif pending_intent in {
        "reservation_create",
        "purchase",
    }:
        # Let the concrete reservation/purchase branch validate whichever
        # field is still missing.  A short follow-up such as "Gulberg" or
        # "the second one" is often parsed as unknown by itself, but it is
        # meaningful in the context of the pending action.
        parsed.requires_clarification = False
        parsed.clarification_question = None

    return parsed


def _preference_acknowledgement(
    parsed: ParsedCustomerMessage,
    stored: list[dict[str, Any]],
) -> str:
    labels = [
        f"{item.get('label')}: {item.get('value')}"
        for item in stored
        if item.get("value") is not None
    ]

    detail = ", ".join(labels)

    if parsed.language in {"roman_urdu", "mixed"}:
        if detail:
            return (
                "Theek hai — maine aapki stated preferences save kar li hain: "
                f"{detail}. Personalization enabled ho to recommendations mein "
                "inhein use kiya jayega."
            )
        return "Theek hai — maine aapki preference note kar li hai."

    if detail:
        return (
            "Got it — I saved the preferences you explicitly stated: "
            f"{detail}. They will be used for recommendations when "
            "personalization is enabled."
        )

    return "Got it — I noted your preference."


def build_stock_status_block(
    variant_id: str,
    inventory: list[dict],
    *,
    branch_name: (
        str | None
    ) = None,
    product_name: str | None = None,
    sku: str | None = None,
    color: str | None = None,
    size: str | None = None,
) -> StockStatusBlock:
    branches: list[
        StockBranchItem
    ] = []

    for row in inventory:
        branch = (
            row.get(
                "branch"
            )
            or {}
        )

        if not branch:
            continue

        actual_branch_name = (
            branch.get(
                "name"
            )
        )

        if (
            branch_name
            and not _location_matches_branch(
                branch,
                branch_name,
            )
        ):
            continue

        status = row.get("status")

        if status not in {
            "out_of_stock",
            "low_stock",
            "available",
        }:
            continue

        available_quantity = int(
            row.get("available_quantity") or 0
        )

        # General availability queries should show only branches
        # with positive stock. Explicit branch checks must still
        # show out-of-stock results for that requested branch.
        if not branch_name and available_quantity <= 0:
            continue

        branches.append(
            StockBranchItem(
                branch_id=str(
                    row[
                        "branch_id"
                    ]
                ),
                branch_name=str(
                    actual_branch_name
                ),
                city=(
                    branch.get(
                        "city"
                    )
                ),
                area=(
                    branch.get(
                        "area"
                    )
                ),
                address=(
                    branch.get(
                        "address"
                    )
                ),
                available_quantity=int(
                    row.get(
                        "available_quantity"
                    )
                    or 0
                ),
                status=status,
            )
        )

    return StockStatusBlock(
        variant_id=(
            variant_id
        ),
        product_name=product_name,
        sku=sku,
        color=color,
        size=size,
        branches=(
            branches
        ),
    )


class OrchestratorAgent:
    agent_key = (
        "orchestrator_agent"
    )

    def _run_traced_tool(
        self,
        *,
        run_id: str,
        plan: PlannedTask,
        arguments: dict,
        call: Callable[
            [],
            Any,
        ],
    ) -> Any:
        task = (
            chat_service
            .create_agent_task(
                run_id,
                agent_key=(
                    plan.agent_key
                ),
                task_type=(
                    plan.task_type
                ),
                input_payload=(
                    arguments
                ),
            )
        )

        tool_call = (
            chat_service
            .create_agent_tool_call(
                agent_run_id=(
                    run_id
                ),
                agent_task_id=(
                    task["id"]
                ),
                agent_key=(
                    plan.agent_key
                ),
                tool_name=(
                    plan.tool_name
                ),
                arguments=(
                    arguments
                ),
            )
        )

        try:
            result = call()

            (
                chat_service
                .complete_agent_tool_call(
                    tool_call[
                        "id"
                    ],
                    result=result,
                )
            )

            (
                chat_service
                .complete_agent_task(
                    task["id"],
                    output_payload={
                        "result":
                            result,
                    },
                )
            )

            return result

        except Exception as exc:
            (
                chat_service
                .fail_agent_tool_call(
                    tool_call[
                        "id"
                    ],
                    error_message=(
                        str(exc)
                    ),
                )
            )

            (
                chat_service
                .fail_agent_task(
                    task["id"],
                    error_message=(
                        str(exc)
                    ),
                )
            )

            raise

    def _run_parallel_traced_tools(
        self,
        *,
        run_id: str,
        jobs: list[
            tuple[
                PlannedTask,
                dict,
                Callable[
                    [],
                    Any,
                ],
            ]
        ],
    ) -> list[Any]:
        """
        Run independent specialist/tool calls
        concurrently while keeping individual
        task/tool traces.
        """

        if not jobs:
            return []

        if len(jobs) == 1:
            (
                plan,
                arguments,
                call,
            ) = jobs[0]

            return [
                self._run_traced_tool(
                    run_id=run_id,
                    plan=plan,
                    arguments=(
                        arguments
                    ),
                    call=call,
                )
            ]

        worker_count = min(
            len(jobs),
            8,
        )

        with ThreadPoolExecutor(
            max_workers=(
                worker_count
            ),
            thread_name_prefix=(
                "retailigent-orchestrator"
            ),
        ) as executor:
            futures = [
                executor.submit(
                    self._run_traced_tool,
                    run_id=run_id,
                    plan=plan,
                    arguments=(
                        arguments
                    ),
                    call=call,
                )
                for (
                    plan,
                    arguments,
                    call,
                ) in jobs
            ]

            return [
                future.result()
                for future
                in futures
            ]

    def _finish_clarification(
        self,
        *,
        customer_id: str,
        conversation_id: str,
        run_id: str,
        parsed: ParsedCustomerMessage,
        content: str,
        update_state: bool = True,
    ) -> ChatTurnResponse:
        assistant_message = (
            chat_service
            .append_message(
                customer_id,
                conversation_id,
                role="assistant",
                content=content,
                agent_key=(
                    self.agent_key
                ),
                metadata={
                    "blocks": [],
                    "intent":
                        parsed.intent,
                },
            )
        )

        if update_state:
            (
                chat_service
                .merge_conversation_state(
                    customer_id,
                    conversation_id,
                    {
                        "last_intent":
                            parsed.intent,
                        "language":
                            parsed.language,
                    },
                )
            )

        (
            chat_service
            .complete_agent_run(
                run_id,
                final_response=(
                    content
                ),
                metadata={
                    "intent":
                        parsed.intent,
                    "clarification":
                        True,
                },
            )
        )

        return ChatTurnResponse(
            conversation_id=(
                conversation_id
            ),
            message_id=str(
                assistant_message[
                    "id"
                ]
            ),
            content=content,
            language=(
                parsed.language
            ),
            blocks=[],
        )

    def process_turn(
        self,
        *,
        customer_id: str,
        message: str,
        conversation_id: (
            str | None
        ) = None,
        customer_latitude: float | None = None,
        customer_longitude: float | None = None,
    ) -> ChatTurnResponse:
        is_new_conversation = (
            conversation_id is None
        )

        conversation = (
            chat_service
            .get_or_create_conversation(
                customer_id,
                conversation_id=(
                    conversation_id
                ),
                language="english",
                title=(
                    message
                    .strip()[:80]
                    if is_new_conversation
                    else None
                ),
            )
        )

        conversation_id = str(
            conversation["id"]
        )

        state = (
            chat_service
            .get_conversation_state(
                customer_id,
                conversation_id,
            )
        )

        customer_context = (
            state.get(
                "customer_context_snapshot"
            )
            or {}
        )

        context_already_loaded = bool(
            state.get(
                "customer_context_loaded"
            )
        )

        if (
            is_new_conversation
            or
            not context_already_loaded
        ):
            try:
                customer_context = (
                    memory_agent
                    .load_context(
                        customer_id
                    )
                )

                state = (
                    chat_service
                    .merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "customer_context_snapshot":
                                customer_context,
                            "customer_context_loaded":
                                True,
                        },
                    )
                )

            except Exception:
                logger.exception(
                    "Could not load customer "
                    "memory context for "
                    "conversation %s",
                    conversation_id,
                )

                customer_context = {}

        parsed = (
            customer_interaction_agent
            .parse(
                message,
                customer_context=(
                    customer_context
                ),
            )
        )

        # Feedback must win over accidental shopping/item intents.
        # Example: "The checkout experience was terrible and confusing"
        # previously matched purchase/cart wording and triggered an item
        # clarification before the Phase 14 feedback service was reached.
        if _looks_like_feedback(message):
            parsed.intent = "feedback_submit"
            parsed.requires_clarification = False
            parsed.clarification_question = None

        parsed = _resume_pending_action(
            parsed,
            state,
        )

        if (
            conversation.get(
                "language"
            )
            != parsed.language
        ):
            (
                chat_service
                .update_conversation_language(
                    customer_id,
                    conversation_id,
                    parsed.language,
                )
            )

        user_message = (
            chat_service
            .append_message(
                customer_id,
                conversation_id,
                role="user",
                content=(
                    message.strip()
                ),
                metadata={
                    "language":
                        parsed.language,
                },
            )
        )

        user_message_id = str(
            user_message["id"]
        )

        (
            chat_service
            .merge_conversation_state(
                customer_id,
                conversation_id,
                {
                    "memory_finalized":
                        False,
                },
            )
        )

        run = (
            chat_service
            .create_agent_run(
                customer_id,
                conversation_id,
                input_text=(
                    message
                ),
                root_agent_key=(
                    self.agent_key
                ),
                metadata={
                    "language":
                        parsed.language,
                },
            )
        )

        run_id = str(
            run["id"]
        )

        try:
            parse_task = (
                chat_service
                .create_agent_task(
                    run_id,
                    agent_key=(
                        "customer_interaction_agent"
                    ),
                    task_type=(
                        "understand_customer_message"
                    ),
                    input_payload={
                        "message":
                            message,
                    },
                )
            )

            (
                chat_service
                .complete_agent_task(
                    parse_task[
                        "id"
                    ],
                    output_payload=(
                        parsed.model_dump(
                            mode="json"
                        )
                    ),
                )
            )

            state = (
                chat_service
                .get_conversation_state(
                    customer_id,
                    conversation_id,
                )
            )

            if (
                parsed
                .requires_clarification
            ):
                content = (
                    parsed
                    .clarification_question
                    or
                    customer_interaction_agent
                    .compose_generic_clarification(
                        parsed.language
                    )
                )

                if parsed.intent in {
                    "smart_cart_create",
                    "alert_create",
                }:
                    resolved_variant = resolve_variant_reference(
                        parsed,
                        state,
                    )

                    if not resolved_variant:
                        resolved_variant, _ = _resolve_named_action_variant(
                            parsed=parsed,
                            state=state,
                            customer_id=customer_id,
                        )

                    if resolved_variant:
                        parsed.entities.variant_id = resolved_variant

                    pending_payload = _pending_action_payload(
                        parsed,
                        variant_id=resolved_variant,
                    )

                    chat_service.merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "pending_action": pending_payload,
                            "last_variant_id": (
                                resolved_variant
                                or state.get("last_variant_id")
                            ),
                        },
                    )

                return (
                    self
                    ._finish_clarification(
                        customer_id=(
                            customer_id
                        ),
                        conversation_id=(
                            conversation_id
                        ),
                        run_id=(
                            run_id
                        ),
                        parsed=parsed,
                        content=content,
                    )
                )

            if (
                parsed.intent
                == "store_location_search"
            ):
                nearest_request = _is_nearest_location_request(
                    message
                )

                if (
                    nearest_request
                    and (
                        customer_latitude is None
                        or customer_longitude is None
                    )
                ):
                    content = (
                        "I need your browser location permission to find the "
                        "nearest branch. Please allow location access and try "
                        "again, or tell me your city/area."
                        if parsed.language == "english"
                        else (
                            "Nearest branch batane ke liye browser location "
                            "permission chahiye. Location allow karke dobara "
                            "try karein, ya apna city/area bata dein."
                        )
                    )
                    blocks = []

                    chat_service.merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "last_intent": parsed.intent,
                            "language": parsed.language,
                        },
                    )

                else:
                    plan = plan_intent(parsed.intent)
                    assert plan is not None

                    arguments = {
                        "branch_name": parsed.entities.branch_name,
                        "customer_latitude": customer_latitude,
                        "customer_longitude": customer_longitude,
                    }

                    results = self._run_traced_tool(
                        run_id=run_id,
                        plan=plan,
                        arguments=arguments,
                        call=lambda: location_agent.search(**arguments),
                    )

                    if nearest_request and results:
                        results = results[:1]

                    block = BranchMapBlock(
                        title=(
                            "Nearest store"
                            if nearest_request
                            else "Store locations and hours"
                        ),
                        branches=results,
                    )

                    chat_service.merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "last_intent": parsed.intent,
                            "language": parsed.language,
                        },
                    )

                    if results:
                        content = (
                            "Here is the nearest active store based on your "
                            "current browser location."
                            if nearest_request
                            else (
                                "Here are the matching store locations, "
                                "addresses, and opening hours."
                            )
                        )
                    else:
                        content = (
                            "I couldn't find an active store matching that "
                            "location. Try specifying a branch or area."
                        )

                    blocks = [block]

            elif (
                parsed.intent
                == "preference_update"
            ):
                stored_preferences = capture_explicit_preferences(
                    customer_id,
                    conversation_id,
                    parsed.entities,
                )

                # Refresh the cached context so subsequent turns in the same
                # conversation do not keep using an old memory snapshot.
                try:
                    refreshed_context = memory_agent.load_context(
                        customer_id
                    )
                except Exception:
                    refreshed_context = customer_context

                chat_service.merge_conversation_state(
                    customer_id,
                    conversation_id,
                    {
                        "last_intent": parsed.intent,
                        "language": parsed.language,
                        "customer_context_snapshot": refreshed_context,
                        "customer_context_loaded": True,
                    },
                )

                content = _preference_acknowledgement(
                    parsed,
                    stored_preferences,
                )
                blocks = []

            elif (
                parsed.intent
                == "recommendation_search"
            ):
                plan = plan_intent(parsed.intent)
                assert plan is not None

                arguments = {
                    "customer_id": customer_id,
                    "query": _build_catalog_query(parsed),
                    "category": parsed.entities.category,
                    "color": parsed.entities.color,
                    "size": parsed.entities.size,
                    "material": parsed.entities.material,
                    "min_price": parsed.entities.min_price,
                    "max_price": parsed.entities.max_price,
                    "match_count": 10,
                }

                results = self._run_traced_tool(
                    run_id=run_id,
                    plan=plan,
                    arguments=arguments,
                    call=lambda: recommendation_agent.recommend(
                        **arguments
                    ),
                )

                product_block = build_product_carousel(results)
                block = RecommendationBlock(
                    title="Recommended for you",
                    products=product_block.products,
                )

                variant_ids = [
                    product.variant_id
                    for product in block.products
                ]

                updates = {
                    "last_intent": parsed.intent,
                    "language": parsed.language,
                    "last_search_variant_ids": variant_ids,
                }

                if variant_ids:
                    updates["last_variant_id"] = variant_ids[0]

                chat_service.merge_conversation_state(
                    customer_id,
                    conversation_id,
                    updates,
                )

                content = (
                    "Here are some product recommendations "
                    "that match your request."
                )
                blocks = [block]

            elif (
                parsed.intent
                == "product_search"
            ):
                plan = (
                    plan_intent(
                        parsed.intent
                    )
                )

                assert (
                    plan is not None
                )

                arguments = {
                    "query":
                        _build_catalog_query(
                            parsed
                        ),
                    "match_count":
                        10,
                    "color":
                        parsed.entities.color,
                    "size":
                        parsed.entities.size,
                    "material":
                        parsed.entities.material,
                    "category":
                        parsed.entities.category,
                    "min_price":
                        parsed.entities.min_price,
                    "max_price":
                        parsed.entities.max_price,
                    "track_demand":
                        True,
                    "customer_id":
                        customer_id,
                }

                results = (
                    self
                    ._run_traced_tool(
                        run_id=(
                            run_id
                        ),
                        plan=plan,
                        arguments=(
                            arguments
                        ),
                        call=lambda: (
                            product_agent
                            .search(
                                **arguments
                            )
                        ),
                    )
                )

                block = (
                    build_product_carousel(
                        results
                    )
                )

                variant_ids = [
                    product.variant_id
                    for product
                    in block.products
                ]

                updates = {
                    "last_intent":
                        parsed.intent,
                    "language":
                        parsed.language,
                    "last_search_variant_ids":
                        variant_ids,
                }

                if variant_ids:
                    updates[
                        "last_variant_id"
                    ] = variant_ids[0]

                (
                    chat_service
                    .merge_conversation_state(
                        customer_id,
                        conversation_id,
                        updates,
                    )
                )

                content = (
                    customer_interaction_agent
                    .compose_search_response(
                        parsed.language,
                        len(
                            block.products
                        ),
                        remembered_size=(
                            parsed
                            .context_used
                            .get(
                                "usual_size"
                            )
                        ),
                    )
                )

                blocks = [
                    block
                ]

            elif (
                parsed.intent
                == "stock_check"
            ):
                requested_product_name = (
                    parsed.entities.product_name
                )
                requested_branch = (
                    parsed.entities.branch_name
                )
                requested_quantity = (
                    _extract_stock_requested_quantity(
                        message,
                        parsed,
                    )
                )

                # Context/ordinal references remain supported.
                variant_ids = (
                    resolve_variant_references(
                        parsed,
                        state,
                    )
                )

                exact_results: list[dict[str, Any]] = []
                named_stock_handled = False

                # A newly named product is a hard constraint and must be
                # resolved before falling back to old conversation context.
                if requested_product_name:
                    search_plan = plan_intent(
                        "product_search"
                    )
                    assert search_plan is not None

                    search_arguments = {
                        "query": requested_product_name,
                        "match_count": 50,
                        "color": parsed.entities.color,
                        "size": parsed.entities.size,
                        "material": parsed.entities.material,
                        "category": parsed.entities.category,
                        "min_price": None,
                        "max_price": None,
                        "track_demand": False,
                        "customer_id": customer_id,
                    }

                    exact_results = self._run_traced_tool(
                        run_id=run_id,
                        plan=search_plan,
                        arguments=search_arguments,
                        call=lambda: product_agent.search(
                            **search_arguments
                        ),
                    )

                    exact_results = _filter_named_product_results(
                        exact_results,
                        requested_product_name,
                    )
                    variant_ids = _unique_variant_ids_from_results(
                        exact_results
                    )

                    # If the exact size/color combination does not exist,
                    # search the SAME product without those variant filters
                    # so we can truthfully explain the alternatives.
                    if not variant_ids:
                        relaxed_arguments = {
                            "query": requested_product_name,
                            "match_count": 50,
                            "color": None,
                            "size": None,
                            "material": parsed.entities.material,
                            "category": parsed.entities.category,
                            "min_price": None,
                            "max_price": None,
                            "track_demand": False,
                            "customer_id": customer_id,
                        }

                        relaxed_results = self._run_traced_tool(
                            run_id=run_id,
                            plan=search_plan,
                            arguments=relaxed_arguments,
                            call=lambda: product_agent.search(
                                **relaxed_arguments
                            ),
                        )
                        relaxed_results = _filter_named_product_results(
                            relaxed_results,
                            requested_product_name,
                        )

                        if not relaxed_results:
                            record_demand_signal(
                                signal_type="no_catalog_match",
                                customer_id=customer_id,
                                requested_size=parsed.entities.size,
                                requested_color=parsed.entities.color,
                                metadata={
                                    "query": _build_catalog_query(parsed),
                                    "requested_product_name": requested_product_name,
                                    "requested_branch": requested_branch,
                                    "source": "stock_check",
                                },
                            )

                            content = (
                                f'I couldn\'t find "{requested_product_name}" '
                                "in our catalog."
                            )
                            blocks = []

                            chat_service.merge_conversation_state(
                                customer_id,
                                conversation_id,
                                {
                                    "last_intent": parsed.intent,
                                    "last_variant_id": None,
                                    "last_search_variant_ids": [],
                                    "language": parsed.language,
                                },
                            )
                        else:
                            product_name = (
                                _result_product_name(relaxed_results[0])
                                or requested_product_name
                            )
                            sizes = _available_size_names(relaxed_results)
                            colors = _available_color_names(relaxed_results)

                            requested_parts: list[str] = []
                            if parsed.entities.size:
                                requested_parts.append(
                                    f"size {parsed.entities.size}"
                                )
                            if parsed.entities.color:
                                requested_parts.append(
                                    f"color {parsed.entities.color}"
                                )

                            requested_label = (
                                " in " + " / ".join(requested_parts)
                                if requested_parts
                                else ""
                            )

                            content = (
                                f"{product_name}{requested_label} is not "
                                "currently available."
                            )

                            if parsed.entities.size and sizes:
                                content += (
                                    " Available sizes: "
                                    + ", ".join(sizes)
                                    + "."
                                )

                            if parsed.entities.color and colors:
                                content += (
                                    " Available colors: "
                                    + ", ".join(colors)
                                    + "."
                                )

                            candidate = relaxed_results[0]
                            record_demand_signal(
                                signal_type="requested_variant_unavailable",
                                customer_id=customer_id,
                                product_id=candidate.get("product_id"),
                                variant_id=candidate.get("variant_id"),
                                requested_size=parsed.entities.size,
                                requested_color=parsed.entities.color,
                                metadata={
                                    "query": parsed.raw_message,
                                    "requested_product_name": requested_product_name,
                                    "requested_branch": requested_branch,
                                    "source": "stock_check",
                                },
                            )

                            alternative_block = build_product_carousel(
                                relaxed_results[:10]
                            )
                            blocks = (
                                [alternative_block]
                                if alternative_block.products
                                else []
                            )

                            alternative_ids = _unique_variant_ids_from_results(
                                relaxed_results
                            )
                            chat_service.merge_conversation_state(
                                customer_id,
                                conversation_id,
                                {
                                    "last_intent": parsed.intent,
                                    "last_variant_id": (
                                        alternative_ids[0]
                                        if alternative_ids
                                        else None
                                    ),
                                    "last_search_variant_ids": alternative_ids,
                                    "language": parsed.language,
                                },
                            )

                        # This named-product request is fully handled.
                        named_stock_handled = True
                        variant_ids = []

                # Category-only stock questions can still search normally.
                elif (
                    not variant_ids
                    and parsed.entities.category
                ):
                    search_plan = plan_intent(
                        "product_search"
                    )
                    assert search_plan is not None

                    search_arguments = {
                        "query": _build_catalog_query(parsed),
                        "match_count": 10,
                        "color": parsed.entities.color,
                        "size": parsed.entities.size,
                        "material": parsed.entities.material,
                        "category": parsed.entities.category,
                        "min_price": parsed.entities.min_price,
                        "max_price": parsed.entities.max_price,
                        "track_demand": True,
                        "customer_id": customer_id,
                    }
                    search_results = self._run_traced_tool(
                        run_id=run_id,
                        plan=search_plan,
                        arguments=search_arguments,
                        call=lambda: product_agent.search(
                            **search_arguments
                        ),
                    )
                    variant_ids = _unique_variant_ids_from_results(
                        search_results
                    )

                    # A structured stock question already identifies what
                    # the customer wants. If no exact variant matches, this
                    # is an unavailable request, not an ambiguous reference.
                    # Never answer "Which item do you mean?" for:
                    #   "Do you have a blue Khaddar shirt in size M?"
                    if not variant_ids:
                        relaxed_results: list[dict[str, Any]] = []

                        if parsed.entities.size:
                            relaxed_arguments = {
                                **search_arguments,
                                "size": None,
                                "track_demand": False,
                            }

                            relaxed_results = self._run_traced_tool(
                                run_id=run_id,
                                plan=search_plan,
                                arguments=relaxed_arguments,
                                call=lambda: product_agent.search(
                                    **relaxed_arguments
                                ),
                            )

                        descriptor_parts = [
                            str(value)
                            for value in (
                                parsed.entities.color,
                                parsed.entities.material,
                                parsed.entities.category,
                            )
                            if value
                        ]

                        descriptor = (
                            " ".join(descriptor_parts)
                            or "matching product"
                        )

                        if parsed.entities.size:
                            descriptor += f" in size {parsed.entities.size}"

                        content = (
                            f"I couldn't find a {descriptor} that matches "
                            "your request."
                        )

                        sizes = _available_size_names(relaxed_results)

                        if parsed.entities.size and sizes:
                            content += (
                                " Available sizes for otherwise matching "
                                "items: "
                                + ", ".join(sizes)
                                + "."
                            )

                        record_demand_signal(
                            signal_type="requested_variant_unavailable",
                            customer_id=customer_id,
                            requested_size=parsed.entities.size,
                            requested_color=parsed.entities.color,
                            metadata={
                                "query": parsed.raw_message,
                                "requested_branch": requested_branch,
                                "requested_material": parsed.entities.material,
                                "requested_category": parsed.entities.category,
                                "max_price": parsed.entities.max_price,
                                "source": "stock_check",
                            },
                        )

                        alternative_block = build_product_carousel(
                            relaxed_results[:10]
                        )
                        blocks = (
                            [alternative_block]
                            if alternative_block.products
                            else []
                        )

                        chat_service.merge_conversation_state(
                            customer_id,
                            conversation_id,
                            {
                                "last_intent": parsed.intent,
                                "last_variant_id": None,
                                "last_search_variant_ids": (
                                    _unique_variant_ids_from_results(
                                        relaxed_results
                                    )
                                ),
                                "language": parsed.language,
                            },
                        )

                        named_stock_handled = True

                # If a named/structured request was already handled above,
                # content is set.
                if named_stock_handled:
                    pass

                elif not variant_ids:
                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                        run_id=run_id,
                        parsed=parsed,
                        content=(
                            customer_interaction_agent
                            .compose_stock_reference_clarification(
                                parsed.language
                            )
                        ),
                    )

                else:
                    plan = plan_intent(parsed.intent)
                    assert plan is not None

                    jobs: list[
                        tuple[
                            PlannedTask,
                            dict,
                            Callable[[], Any],
                        ]
                    ] = []

                    for variant_id in variant_ids:
                        arguments = {
                            "variant_id": variant_id,
                        }
                        jobs.append(
                            (
                                plan,
                                arguments,
                                lambda current_variant_id=variant_id:
                                    inventory_agent
                                    .get_stock_snapshot_with_branches(
                                        current_variant_id
                                    ),
                            )
                        )

                    inventory_results = self._run_parallel_traced_tools(
                        run_id=run_id,
                        jobs=jobs,
                    )

                    requested_rows_all: list[dict[str, Any]] = []
                    alternative_rows_all: list[dict[str, Any]] = []
                    display_rows_by_variant: list[list[dict[str, Any]]] = []

                    for inventory in inventory_results:
                        inventory = inventory or []

                        if requested_branch:
                            requested_rows, other_rows = (
                                _split_inventory_for_location(
                                    inventory,
                                    requested_branch,
                                )
                            )
                            requested_rows_all.extend(requested_rows)
                            alternative_rows_all.extend(
                                _positive_inventory_rows(other_rows)
                            )

                            if _total_available(requested_rows) > 0:
                                display_rows_by_variant.append(
                                    requested_rows
                                )
                            else:
                                display_rows_by_variant.append(
                                    requested_rows
                                    + _positive_inventory_rows(other_rows)
                                )
                        else:
                            requested_rows_all.extend(inventory)
                            display_rows_by_variant.append(inventory)

                    available_quantity = _total_available(
                        requested_rows_all
                    )

                    if requested_quantity is not None and (
                        requested_quantity > available_quantity
                    ):
                        signal_type = "insufficient_stock"
                    elif available_quantity <= 0:
                        signal_type = (
                            "requested_variant_unavailable"
                            if requested_product_name
                            else "insufficient_stock"
                        )
                    else:
                        signal_type = None

                    if signal_type:
                        first_variant_id = variant_ids[0]
                        first_branch_id = None

                        if requested_rows_all:
                            value = requested_rows_all[0].get("branch_id")
                            first_branch_id = str(value) if value else None

                        metadata = {
                            "requested_branch": requested_branch,
                            "checked_branch_count": len(requested_rows_all),
                            "available_quantity": available_quantity,
                            "requested_size": parsed.entities.size,
                            "requested_color": parsed.entities.color,
                            "available_elsewhere": bool(alternative_rows_all),
                            "source": "stock_check",
                        }

                        if requested_quantity is not None:
                            metadata["requested_quantity"] = requested_quantity
                            metadata["shortfall_quantity"] = max(
                                0,
                                requested_quantity - available_quantity,
                            )

                        record_demand_signal(
                            signal_type=signal_type,
                            customer_id=customer_id,
                            variant_id=first_variant_id,
                            branch_id=first_branch_id,
                            requested_size=parsed.entities.size,
                            requested_color=parsed.entities.color,
                            metadata=metadata,
                        )

                    exact_by_variant = {
                        str(result.get("variant_id")): result
                        for result in exact_results
                        if result.get("variant_id")
                    }

                    stock_blocks: list[StockStatusBlock] = []

                    for variant_id, rows in zip(
                        variant_ids,
                        display_rows_by_variant,
                        strict=True,
                    ):
                        result = exact_by_variant.get(str(variant_id)) or {}
                        product = result.get("product") or {}
                        variant = result.get("variant") or {}
                        color_data = variant.get("color") or {}
                        size_data = variant.get("size") or {}

                        stock_blocks.append(
                            build_stock_status_block(
                                variant_id,
                                rows,
                                branch_name=None,
                                product_name=(
                                    str(product.get("name"))
                                    if product.get("name")
                                    else None
                                ),
                                sku=(
                                    str(variant.get("sku"))
                                    if variant.get("sku")
                                    else None
                                ),
                                color=(
                                    str(color_data.get("name"))
                                    if color_data.get("name")
                                    else None
                                ),
                                size=(
                                    str(size_data.get("name"))
                                    if size_data.get("name")
                                    else None
                                ),
                            )
                        )

                    product_label = (
                        _result_product_name(exact_results[0])
                        if exact_results
                        else (
                            requested_product_name
                            or "The requested item"
                        )
                    )

                    if requested_branch:
                        if available_quantity > 0:
                            if (
                                requested_quantity is not None
                                and requested_quantity > available_quantity
                            ):
                                content = (
                                    f"{product_label} is available at "
                                    f"{requested_branch}, but only "
                                    f"{available_quantity} unit"
                                    f"{'s are' if available_quantity != 1 else ' is'} "
                                    f"currently available. You requested "
                                    f"{requested_quantity}."
                                )
                            else:
                                content = (
                                    f"Yes. {product_label} is available at "
                                    f"{requested_branch}. Available quantity: "
                                    f"{available_quantity}."
                                )
                        else:
                            content = (
                                f"{product_label} is not currently available "
                                f"at {requested_branch}."
                            )
                            alternatives = _format_branch_alternatives(
                                alternative_rows_all
                            )
                            if alternatives:
                                content += (
                                    " It is available at other branches: "
                                    f"{alternatives}."
                                )
                            else:
                                content += (
                                    " It is also not currently available at "
                                    "any other active branch."
                                )
                    else:
                        if available_quantity <= 0:
                            content = (
                                f"{product_label} is currently out of stock "
                                "at all active branches."
                            )
                        elif (
                            requested_quantity is not None
                            and requested_quantity > available_quantity
                        ):
                            content = (
                                f"Only {available_quantity} unit"
                                f"{'s are' if available_quantity != 1 else ' is'} "
                                "currently available across the matching "
                                f"branches. You requested {requested_quantity}."
                            )
                        elif len(stock_blocks) == 1:
                            content = (
                                customer_interaction_agent
                                .compose_stock_response(
                                    parsed.language,
                                    stock_blocks[0],
                                    requested_branch=None,
                                )
                            )
                        else:
                            content = (
                                f"I checked {len(stock_blocks)} matching variants "
                                "in parallel. The stock cards below show "
                                "verified branch-level availability."
                            )

                    chat_service.merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "last_intent": parsed.intent,
                            "last_variant_id": variant_ids[-1],
                            "last_search_variant_ids": variant_ids,
                            "language": parsed.language,
                        },
                    )
                    blocks = list(stock_blocks)

            elif parsed.intent == "reservation_create":
                variant_id = resolve_variant_reference(
                    parsed,
                    state,
                )

                if not variant_id:
                    variant_id, candidates = _resolve_named_action_variant(
                        parsed=parsed,
                        state=state,
                        customer_id=customer_id,
                    )

                    if (
                        not variant_id
                        and parsed.entities.product_name
                        and candidates
                    ):
                        chat_service.merge_conversation_state(
                            customer_id,
                            conversation_id,
                            {
                                "pending_action": _pending_action_payload(parsed),
                            },
                        )
                        return self._finish_clarification(
                            customer_id=customer_id,
                            conversation_id=conversation_id,
                            run_id=run_id,
                            parsed=parsed,
                            content=(
                                f"I found multiple variants of "
                                f"{parsed.entities.product_name}. "
                                "Please specify the size/color or select one "
                                "of the product cards first."
                            ),
                            update_state=False,
                        )

                if not variant_id:
                    chat_service.merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "pending_action": _pending_action_payload(parsed),
                        },
                    )
                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                        run_id=run_id,
                        parsed=parsed,
                        content=(
                            customer_interaction_agent
                            .compose_item_reference_clarification(
                                parsed.language
                            )
                        ),
                        update_state=False,
                    )

                branch_name = parsed.entities.branch_name

                if not branch_name:
                    chat_service.merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "pending_action": _pending_action_payload(
                                parsed,
                                variant_id=variant_id,
                            ),
                            "last_variant_id": variant_id,
                        },
                    )
                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                        run_id=run_id,
                        parsed=parsed,
                        content=(
                            "Which branch would you like to reserve it at? "
                            "Please specify the branch name."
                            if parsed.language == "english"
                            else
                            "Kis branch se reserve karna hai? "
                            "Please branch ka naam batayein."
                        ),
                        update_state=False,
                    )

                quantity = parsed.entities.quantity or 1

                if quantity < 1:
                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                        run_id=run_id,
                        parsed=parsed,
                        content="Please request a quantity of at least 1.",
                    )

                inventory_rows = (
                    inventory_agent.get_stock_snapshot_with_branches(
                        variant_id
                    )
                    or []
                )

                matching_rows = [
                    row
                    for row in inventory_rows
                    if _location_matches_branch(
                        row.get("branch") or {},
                        branch_name,
                    )
                ]

                matching_row = (
                    matching_rows[0]
                    if len(matching_rows) == 1
                    else None
                )

                if matching_row is None:
                    available_branches = sorted(
                        {
                            str(
                                (row.get("branch") or {}).get("name")
                                or ""
                            ).strip()
                            for row in inventory_rows
                            if (
                                (row.get("branch") or {}).get("name")
                            )
                        }
                    )

                    branch_options = (
                        ", ".join(available_branches)
                        if available_branches
                        else "no active branches currently listed"
                    )

                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                        run_id=run_id,
                        parsed=parsed,
                        content=(
                            f"I couldn't find that branch for this item. "
                            f"Available branches: {branch_options}."
                        ),
                    )

                available_quantity = int(
                    matching_row.get("available_quantity") or 0
                )

                if available_quantity < quantity:
                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                        run_id=run_id,
                        parsed=parsed,
                        content=(
                            f"Only {available_quantity} unit(s) are currently "
                            f"available at {branch_name}. Please choose a "
                            "smaller quantity or another branch."
                        ),
                    )

                branch_id = str(matching_row["branch_id"])

                plan = plan_intent(parsed.intent)
                assert plan is not None

                arguments = {
                    "variant_id": variant_id,
                    "branch_id": branch_id,
                    "quantity": quantity,
                    "hold_minutes": 15,
                }

                try:
                    reservation = self._run_traced_tool(
                        run_id=run_id,
                        plan=plan,
                        arguments=arguments,
                        call=lambda: create_customer_reservation(
                            customer_id=customer_id,
                            variant_id=variant_id,
                            branch_id=branch_id,
                            quantity=quantity,
                            hold_minutes=15,
                        ),
                    )
                except Exception:
                    logger.exception(
                        "Chat reservation failed for conversation %s",
                        conversation_id,
                    )

                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                        run_id=run_id,
                        parsed=parsed,
                        content=(
                            "I couldn't complete that reservation. "
                            "Stock may have changed, so please check "
                            "availability and try again."
                        ),
                    )

                reservation_id = str(reservation["id"])

                chat_service.merge_conversation_state(
                    customer_id,
                    conversation_id,
                    {
                        "last_intent": parsed.intent,
                        "last_variant_id": variant_id,
                        "last_reservation_id": reservation_id,
                        "last_reservation_variant_id": variant_id,
                        "pending_action": None,
                        "language": parsed.language,
                    },
                )

                blocks = [
                    ReservationBlock(reservation=reservation)
                ]

                content = (
                    f"Your reservation is confirmed for {quantity} "
                    f"unit(s) at {branch_name}. The hold expires at "
                    f"{reservation.get('expires_at')}. This is a temporary "
                    "reservation, not a completed purchase."
                )

            elif (
                parsed.intent
                == "add_to_cart"
            ):
                variant_id, candidates = (
                    _resolve_named_action_variant(
                        parsed=parsed,
                        state=state,
                        customer_id=customer_id,
                    )
                )

                if not variant_id:
                    if parsed.entities.product_name and not candidates:
                        content = (
                            f'I couldn\'t find "{parsed.entities.product_name}" '
                            "in our catalog."
                        )
                        blocks = []
                        return self._finish_clarification(
                            customer_id=customer_id,
                            conversation_id=conversation_id,
                            run_id=run_id,
                            parsed=parsed,
                            content=content,
                        )

                    if candidates:
                        candidate_block = build_product_carousel(
                            candidates[:10]
                        )
                        sizes = _available_size_names(candidates)
                        colors = _available_color_names(candidates)
                        details: list[str] = []
                        if sizes:
                            details.append("sizes " + ", ".join(sizes))
                        if colors:
                            details.append("colors " + ", ".join(colors))
                        detail_text = (
                            f" ({'; '.join(details)})"
                            if details
                            else ""
                        )
                        content = (
                            f"I found multiple variants of "
                            f"{parsed.entities.product_name or 'that product'}"
                            f"{detail_text}. Please specify the size/color "
                            "or select one of the product cards first."
                        )
                        return self._finish_clarification(
                            customer_id=customer_id,
                            conversation_id=conversation_id,
                            run_id=run_id,
                            parsed=parsed,
                            content=content,
                        )

                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                        run_id=run_id,
                        parsed=parsed,
                        content=(
                            customer_interaction_agent
                            .compose_item_reference_clarification(
                                parsed.language
                            )
                        ),
                    )

                quantity = parsed.entities.quantity or 1
                cart_plan = plan_intent("add_to_cart")
                assert cart_plan is not None

                cart_arguments = {
                    "variant_id": variant_id,
                    "quantity": quantity,
                }
                cart = self._run_traced_tool(
                    run_id=run_id,
                    plan=cart_plan,
                    arguments=cart_arguments,
                    call=lambda: add_cart_item(
                        customer_id=customer_id,
                        variant_id=variant_id,
                        quantity=quantity,
                    ),
                )
                cart_block = CartSummaryBlock(data=cart)

                if _combined_cart_wishlist_request(parsed.raw_message):
                    wishlist_plan = plan_intent("add_to_wishlist")
                    assert wishlist_plan is not None
                    wishlist_arguments = {
                        "variant_id": variant_id,
                    }
                    wishlist = self._run_traced_tool(
                        run_id=run_id,
                        plan=wishlist_plan,
                        arguments=wishlist_arguments,
                        call=lambda: add_wishlist_item(
                            customer_id=customer_id,
                            variant_id=variant_id,
                        ),
                    )
                    blocks = [
                        cart_block,
                        WishlistBlock(data=wishlist),
                    ]
                    content = (
                        f"Added {quantity} item"
                        f"{'s' if quantity != 1 else ''} to your cart "
                        "and added the item to your wishlist."
                    )
                else:
                    blocks = [cart_block]
                    content = (
                        customer_interaction_agent
                        .compose_cart_added_response(
                            parsed.language,
                            quantity,
                        )
                    )

                chat_service.merge_conversation_state(
                    customer_id,
                    conversation_id,
                    {
                        "last_intent": parsed.intent,
                        "last_variant_id": variant_id,
                        "language": parsed.language,
                    },
                )

            elif (
                parsed.intent
                == "add_to_wishlist"
            ):
                variant_id, candidates = (
                    _resolve_named_action_variant(
                        parsed=parsed,
                        state=state,
                        customer_id=customer_id,
                    )
                )

                if not variant_id:
                    if parsed.entities.product_name and not candidates:
                        return self._finish_clarification(
                            customer_id=customer_id,
                            conversation_id=conversation_id,
                            run_id=run_id,
                            parsed=parsed,
                            content=(
                                f'I couldn\'t find "{parsed.entities.product_name}" '
                                "in our catalog."
                            ),
                        )

                    if candidates:
                        candidate_block = build_product_carousel(
                            candidates[:10]
                        )
                        sizes = _available_size_names(candidates)
                        colors = _available_color_names(candidates)
                        details: list[str] = []
                        if sizes:
                            details.append("sizes " + ", ".join(sizes))
                        if colors:
                            details.append("colors " + ", ".join(colors))
                        detail_text = (
                            f" ({'; '.join(details)})"
                            if details
                            else ""
                        )
                        return self._finish_clarification(
                            customer_id=customer_id,
                            conversation_id=conversation_id,
                            run_id=run_id,
                            parsed=parsed,
                            content=(
                                f"I found multiple variants of "
                                f"{parsed.entities.product_name or 'that product'}"
                                f"{detail_text}. Please specify the size/color "
                                "or select one of the product cards first."
                            ),
                        )

                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                        run_id=run_id,
                        parsed=parsed,
                        content=(
                            customer_interaction_agent
                            .compose_item_reference_clarification(
                                parsed.language
                            )
                        ),
                    )

                wishlist_plan = plan_intent("add_to_wishlist")
                assert wishlist_plan is not None
                wishlist_arguments = {
                    "variant_id": variant_id,
                }
                wishlist = self._run_traced_tool(
                    run_id=run_id,
                    plan=wishlist_plan,
                    arguments=wishlist_arguments,
                    call=lambda: add_wishlist_item(
                        customer_id=customer_id,
                        variant_id=variant_id,
                    ),
                )
                wishlist_block = WishlistBlock(data=wishlist)

                if _combined_cart_wishlist_request(parsed.raw_message):
                    quantity = parsed.entities.quantity or 1
                    cart_plan = plan_intent("add_to_cart")
                    assert cart_plan is not None
                    cart_arguments = {
                        "variant_id": variant_id,
                        "quantity": quantity,
                    }
                    cart = self._run_traced_tool(
                        run_id=run_id,
                        plan=cart_plan,
                        arguments=cart_arguments,
                        call=lambda: add_cart_item(
                            customer_id=customer_id,
                            variant_id=variant_id,
                            quantity=quantity,
                        ),
                    )
                    blocks = [
                        CartSummaryBlock(data=cart),
                        wishlist_block,
                    ]
                    content = (
                        f"Added {quantity} item"
                        f"{'s' if quantity != 1 else ''} to your cart "
                        "and added the item to your wishlist."
                    )
                else:
                    blocks = [wishlist_block]
                    content = (
                        customer_interaction_agent
                        .compose_wishlist_added_response(
                            parsed.language
                        )
                    )

                chat_service.merge_conversation_state(
                    customer_id,
                    conversation_id,
                    {
                        "last_intent": parsed.intent,
                        "last_variant_id": variant_id,
                        "language": parsed.language,
                    },
                )

            elif (
                parsed.intent
                == "smart_cart_create"
            ):
                variant_id = (
                    resolve_variant_reference(
                        parsed,
                        state,
                    )
                )

                if not variant_id:
                    variant_id, candidates = _resolve_named_action_variant(
                        parsed=parsed,
                        state=state,
                        customer_id=customer_id,
                    )

                    if (
                        not variant_id
                        and parsed.entities.product_name
                        and candidates
                    ):
                        return self._finish_clarification(
                            customer_id=customer_id,
                            conversation_id=conversation_id,
                            run_id=run_id,
                            parsed=parsed,
                            content=(
                                f"I found multiple variants of "
                                f"{parsed.entities.product_name}. "
                                "Please specify the size/color or select one "
                                "of the product cards first."
                            ),
                        )

                if not variant_id:
                    return (
                        self
                        ._finish_clarification(
                            customer_id=(
                                customer_id
                            ),
                            conversation_id=(
                                conversation_id
                            ),
                            run_id=(
                                run_id
                            ),
                            parsed=parsed,
                            content=(
                                customer_interaction_agent
                                .compose_item_reference_clarification(
                                    parsed.language
                                )
                            ),
                        )
                    )

                if (
                    parsed
                    .entities
                    .target_price
                    is None
                    and
                    parsed
                    .entities
                    .min_discount_percentage
                    is None
                ):
                    chat_service.merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "pending_action": _pending_action_payload(
                                parsed,
                                variant_id=variant_id,
                            ),
                            "last_variant_id": variant_id,
                        },
                    )
                    return (
                        self
                        ._finish_clarification(
                            customer_id=(
                                customer_id
                            ),
                            conversation_id=(
                                conversation_id
                            ),
                            run_id=(
                                run_id
                            ),
                            parsed=parsed,
                            content=(
                                customer_interaction_agent
                                .compose_smart_cart_trigger_clarification(
                                    parsed.language
                                )
                            ),
                        )
                    )

                authorization_mode = (
                    parsed
                    .entities
                    .authorization_mode
                )

                if (
                    authorization_mode
                    is None
                ):
                    chat_service.merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "pending_action": _pending_action_payload(
                                parsed,
                                variant_id=variant_id,
                            ),
                            "last_variant_id": variant_id,
                        },
                    )
                    return (
                        self
                        ._finish_clarification(
                            customer_id=(
                                customer_id
                            ),
                            conversation_id=(
                                conversation_id
                            ),
                            run_id=(
                                run_id
                            ),
                            parsed=parsed,
                            content=(
                                customer_interaction_agent
                                .compose_smart_cart_authorization_clarification(
                                    parsed.language
                                )
                            ),
                        )
                    )

                quantity = (
                    parsed
                    .entities
                    .quantity
                    or 1
                )

                plan = (
                    plan_intent(
                        parsed.intent
                    )
                )

                assert (
                    plan is not None
                )

                arguments = {
                    "variant_id":
                        variant_id,
                    "quantity":
                        quantity,
                    "target_price":
                        parsed
                        .entities
                        .target_price,
                    "min_discount_percentage":
                        parsed
                        .entities
                        .min_discount_percentage,
                    "authorization_mode":
                        authorization_mode,
                    "branch_id":
                        None,
                }

                rule = (
                    self
                    ._run_traced_tool(
                        run_id=(
                            run_id
                        ),
                        plan=plan,
                        arguments=(
                            arguments
                        ),
                        call=lambda: (
                            create_customer_smart_cart_rule(
                                customer_id=(
                                    customer_id
                                ),
                                variant_id=(
                                    variant_id
                                ),
                                quantity=(
                                    quantity
                                ),
                                target_price=(
                                    parsed
                                    .entities
                                    .target_price
                                ),
                                min_discount_percentage=(
                                    parsed
                                    .entities
                                    .min_discount_percentage
                                ),
                                authorization_mode=(
                                    authorization_mode
                                ),
                                branch_id=(
                                    None
                                ),
                            )
                        ),
                    )
                )

                block = (
                    SmartCartRuleBlock(
                        rule=rule
                    )
                )

                (
                    chat_service
                    .merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "last_intent":
                                parsed.intent,
                            "last_variant_id":
                                variant_id,
                            "last_smart_cart_rule_id":
                                rule["id"],
                            "pending_action":
                                None,
                            "language":
                                parsed.language,
                        },
                    )
                )

                content = (
                    customer_interaction_agent
                    .compose_smart_cart_created_response(
                        parsed.language,
                        authorization_mode,
                    )
                )

                blocks = [
                    block
                ]

            elif (
                parsed.intent
                == "alert_create"
            ):
                variant_id = resolve_variant_reference(
                    parsed,
                    state,
                )

                if not variant_id:
                    variant_id, candidates = _resolve_named_action_variant(
                        parsed=parsed,
                        state=state,
                        customer_id=customer_id,
                    )

                    if (
                        not variant_id
                        and parsed.entities.product_name
                        and candidates
                    ):
                        return self._finish_clarification(
                            customer_id=customer_id,
                            conversation_id=conversation_id,
                            run_id=run_id,
                            parsed=parsed,
                            content=(
                                f"I found multiple variants of "
                                f"{parsed.entities.product_name}. "
                                "Please specify the size/color or select one "
                                "of the product cards first."
                            ),
                        )

                if not variant_id:
                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                        run_id=run_id,
                        parsed=parsed,
                        content=(
                            customer_interaction_agent
                            .compose_item_reference_clarification(
                                parsed.language
                            )
                        ),
                    )

                pending = state.get("pending_action")
                pending_alert_type = (
                    str(pending.get("alert_type"))
                    if isinstance(pending, dict)
                    and pending.get("intent") == "alert_create"
                    and pending.get("alert_type")
                    else None
                )

                alert_type = (
                    pending_alert_type
                    or _infer_alert_type(message)
                )

                target_price = parsed.entities.target_price

                if (
                    alert_type == "price_drop"
                    and target_price is None
                ):
                    chat_service.merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "pending_action": {
                                **_pending_action_payload(
                                    parsed,
                                    variant_id=variant_id,
                                ),
                                "alert_type": alert_type,
                            },
                            "last_variant_id": variant_id,
                        },
                    )

                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                        run_id=run_id,
                        parsed=parsed,
                        content=(
                            "What target price should I watch for?"
                            if parsed.language == "english"
                            else "Kis target price par alert chahiye?"
                        ),
                        update_state=False,
                    )

                plan = plan_intent(parsed.intent)
                assert plan is not None

                arguments = {
                    "variant_id": variant_id,
                    "alert_type": alert_type,
                    "target_price": target_price,
                }

                alert = self._run_traced_tool(
                    run_id=run_id,
                    plan=plan,
                    arguments=arguments,
                    call=lambda: alert_agent.create(
                        customer_id=customer_id,
                        variant_id=variant_id,
                        alert_type=alert_type,
                        target_price=target_price,
                    ),
                )

                block = AlertBlock(
                    alert=alert
                )

                chat_service.merge_conversation_state(
                    customer_id,
                    conversation_id,
                    {
                        "last_intent": parsed.intent,
                        "last_variant_id": variant_id,
                        "last_alert_id": alert.get("id"),
                        "pending_action": None,
                        "language": parsed.language,
                    },
                )

                if alert_type == "restock":
                    content = (
                        "Restock alert created. I'll notify you when this "
                        "variant is back in stock."
                    )
                elif alert_type == "sale":
                    content = (
                        "Sale alert created. I'll notify you when this "
                        "variant goes on sale."
                    )
                else:
                    content = (
                        f"Price alert created. I'll notify you when this "
                        f"variant reaches Rs. {float(target_price):,.0f}."
                    )

                blocks = [block]

            elif (
                parsed.intent
                == "purchase"
            ):
                variant_id = (
                    resolve_variant_reference(
                        parsed,
                        state,
                    )
                )

                if not variant_id:
                    variant_id, candidates = _resolve_named_action_variant(
                        parsed=parsed,
                        state=state,
                        customer_id=customer_id,
                    )

                if not variant_id:
                    chat_service.merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "pending_action": _pending_action_payload(parsed),
                        },
                    )
                    return (
                        self
                        ._finish_clarification(
                            customer_id=(
                                customer_id
                            ),
                            conversation_id=(
                                conversation_id
                            ),
                            run_id=(
                                run_id
                            ),
                            parsed=parsed,
                            content=(
                                customer_interaction_agent
                                .compose_item_reference_clarification(
                                    parsed.language
                                )
                            ),
                            update_state=False,
                        )
                    )

                quantity = (
                    parsed
                    .entities
                    .quantity
                    or 1
                )

                reservation_id = None

                if (
                    state.get(
                        "last_reservation_id"
                    )
                    and
                    state.get(
                        "last_reservation_variant_id"
                    )
                    == variant_id
                ):
                    reservation_id = str(
                        state[
                            "last_reservation_id"
                        ]
                    )

                idempotency_key = (
                    "chat-purchase:"
                    f"{conversation_id}:"
                    f"{user_message_id}"
                )

                plan = (
                    plan_intent(
                        parsed.intent
                    )
                )

                assert (
                    plan is not None
                )

                arguments = {
                    "customer_id":
                        customer_id,
                    "variant_id":
                        variant_id,
                    "quantity":
                        quantity,
                    "idempotency_key":
                        idempotency_key,
                    "branch_id":
                        None,
                    "reservation_id":
                        reservation_id,
                }

                result = (
                    self
                    ._run_traced_tool(
                        run_id=(
                            run_id
                        ),
                        plan=plan,
                        arguments=(
                            arguments
                        ),
                        call=lambda: (
                            purchase_agent
                            .purchase(
                                customer_id=(
                                    customer_id
                                ),
                                variant_id=(
                                    variant_id
                                ),
                                quantity=(
                                    quantity
                                ),
                                idempotency_key=(
                                    idempotency_key
                                ),
                                branch_id=(
                                    None
                                ),
                                reservation_id=(
                                    reservation_id
                                ),
                            )
                        ),
                    )
                )

                success = (
                    result.get(
                        "success"
                    )
                    is True
                )

                if success:
                    order_id = (
                        result.get(
                            "order_id"
                        )
                    )

                    if not order_id:
                        raise ValueError(
                            "Purchase service returned "
                            "success=True without an "
                            "order_id."
                        )

                    order_payload = {
                        **result,
                        "variant_id":
                            variant_id,
                        "quantity":
                            quantity,
                    }

                    block = (
                        OrderConfirmationBlock(
                            order=(
                                order_payload
                            )
                        )
                    )

                    blocks = [
                        block
                    ]

                    state_updates = {
                        "last_intent":
                            parsed.intent,
                        "last_variant_id":
                            variant_id,
                        "last_order_id":
                            str(
                                order_id
                            ),
                        "pending_action":
                            None,
                        "language":
                            parsed.language,
                    }

                    if result.get(
                        "purchase_attempt_id"
                    ):
                        state_updates[
                            "last_purchase_attempt_id"
                        ] = str(
                            result[
                                "purchase_attempt_id"
                            ]
                        )

                else:
                    blocks = []

                    state_updates = {
                        "last_intent":
                            parsed.intent,
                        "last_variant_id":
                            variant_id,
                        "last_purchase_failure_code":
                            result.get(
                                "reason_code"
                            ),
                        "pending_action":
                            None,
                        "language":
                            parsed.language,
                    }

                (
                    chat_service
                    .merge_conversation_state(
                        customer_id,
                        conversation_id,
                        state_updates,
                    )
                )

                content = (
                    customer_interaction_agent
                    .compose_purchase_response(
                        parsed.language,
                        result,
                    )
                )

            elif parsed.intent == "feedback_submit":
                feedback_type = _infer_feedback_type(
                    message
                )

                try:
                    feedback_row = (
                        feedback_service
                        .submit_feedback(
                            customer_id=customer_id,
                            feedback_type=feedback_type,
                            rating=None,
                            message=message,
                            conversation_id=(
                                conversation_id
                            ),
                        )
                    )

                    sentiment = str(
                        feedback_row.get(
                            "ai_sentiment"
                        )
                        or "neutral"
                    )

                    needs_review = bool(
                        feedback_row.get(
                            "needs_review"
                        )
                    )

                    if parsed.language == "roman_urdu":
                        if needs_review:
                            content = (
                                "Shukriya. Aapka feedback record "
                                "kar liya gaya hai aur review ke "
                                "liye flag kar diya gaya hai."
                            )
                        else:
                            content = (
                                "Shukriya. Aapka feedback record "
                                "kar liya gaya hai."
                            )
                    else:
                        if needs_review:
                            content = (
                                "Thanks for the feedback. I've "
                                "recorded it and flagged it for "
                                "review."
                            )
                        else:
                            content = (
                                "Thanks for the feedback. I've "
                                "recorded it."
                            )

                    blocks = []

                    chat_service.merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "last_intent": parsed.intent,
                            "last_feedback_id": str(
                                feedback_row.get("id")
                            ),
                            "last_feedback_sentiment": sentiment,
                            "language": parsed.language,
                        },
                    )

                except (
                    FeedbackServiceError,
                    ValueError,
                ):
                    logger.exception(
                        "Could not save chat feedback for "
                        "conversation %s",
                        conversation_id,
                    )

                    if parsed.language == "roman_urdu":
                        content = (
                            "Maazrat, aapka feedback abhi save "
                            "nahi ho saka. Please dobara try "
                            "karein."
                        )
                    else:
                        content = (
                            "Sorry, I couldn't save your "
                            "feedback right now. Please try "
                            "again."
                        )

                    blocks = []

                    chat_service.merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "last_intent": parsed.intent,
                            "language": parsed.language,
                        },
                    )

            elif parsed.intent == "support_request":
                # ----------------------------------------------------------
                # Existing-ticket status/follow-up
                # ----------------------------------------------------------
                # A question such as "Has anyone looked at my issue yet?"
                # must not create a brand-new support escalation. We fetch
                # the customer's latest unresolved ticket from the database
                # so this works both in the same conversation and in a new
                # conversation whose cached memory snapshot may be stale.
                if support_agent.is_ticket_status_followup(
                    message
                ):
                    try:
                        existing_ticket = (
                            get_latest_open_support_ticket(
                                customer_id
                            )
                        )

                        if existing_ticket is None:
                            content = (
                                support_agent
                                .compose_no_open_ticket_response(
                                    language=(
                                        parsed.language
                                    )
                                )
                            )
                            blocks = []
                            state_updates = {
                                "last_intent":
                                    parsed.intent,
                                "language":
                                    parsed.language,
                            }

                        else:
                            ticket_id = str(
                                existing_ticket[
                                    "id"
                                ]
                            )

                            # Persist the customer's follow-up in the
                            # existing ticket thread instead of opening a
                            # duplicate ticket.
                            existing_ticket = (
                                add_customer_support_message(
                                    customer_id=(
                                        customer_id
                                    ),
                                    ticket_id=(
                                        ticket_id
                                    ),
                                    message=message,
                                )
                            )

                            ticket_status = str(
                                existing_ticket.get(
                                    "status",
                                    "open",
                                )
                                or "open"
                            )

                            ticket_subject = str(
                                existing_ticket.get(
                                    "subject",
                                    "Support request",
                                )
                                or "Support request"
                            )

                            content = (
                                support_agent
                                .compose_ticket_status_response(
                                    ticket=(
                                        existing_ticket
                                    ),
                                    language=(
                                        parsed.language
                                    ),
                                )
                            )

                            blocks = [
                                SupportEscalationBlock(
                                    ticket_id=(
                                        ticket_id
                                    ),
                                    status=(
                                        ticket_status
                                    ),
                                    subject=(
                                        ticket_subject
                                    ),
                                    message=(
                                        content
                                    ),
                                )
                            ]

                            state_updates = {
                                "last_intent":
                                    parsed.intent,
                                "last_support_ticket_id":
                                    ticket_id,
                                "language":
                                    parsed.language,
                            }

                    except SupportTicketError:
                        logger.exception(
                            "Could not load/update existing "
                            "support ticket for customer %s",
                            customer_id,
                        )

                        if (
                            parsed.language
                            == "roman_urdu"
                        ):
                            content = (
                                "Maazrat, main aapke existing "
                                "support ticket ka status abhi "
                                "load nahi kar saka/saki. "
                                "Please dobara try karein."
                            )
                        else:
                            content = (
                                "Sorry, I couldn't load your "
                                "existing support ticket right "
                                "now. Please try again."
                            )

                        blocks = []
                        state_updates = {
                            "last_intent":
                                parsed.intent,
                            "language":
                                parsed.language,
                        }

                    chat_service.merge_conversation_state(
                        customer_id,
                        conversation_id,
                        state_updates,
                    )

                # ----------------------------------------------------------
                # Brand-new complaint / escalation
                # ----------------------------------------------------------
                else:
                    recent_messages = []

                    try:
                        recent_messages = (
                            chat_service.list_recent_messages(
                                customer_id,
                                conversation_id,
                                limit=12,
                            )
                        )
                    except Exception:
                        logger.exception(
                            "Could not load recent messages for "
                            "support handoff in conversation %s",
                            conversation_id,
                        )

                    # The current message is passed separately.
                    recent_messages = [
                        item
                        for item in recent_messages
                        if not (
                            str(
                                item.get(
                                    "role",
                                    "",
                                )
                            ).casefold()
                            in {
                                "user",
                                "customer",
                            }
                            and str(
                                item.get(
                                    "content",
                                    "",
                                )
                            ).strip()
                            == message.strip()
                        )
                    ]

                    escalation = (
                        support_agent.prepare_escalation(
                            message=message,
                            language=(
                                parsed.language
                            ),
                            customer_context=(
                                customer_context
                            ),
                            recent_messages=(
                                recent_messages
                            ),
                        )
                    )

                    subject = (
                        escalation[
                            "subject"
                        ]
                    )

                    try:
                        ticket = (
                            create_support_ticket(
                                customer_id=(
                                    customer_id
                                ),
                                conversation_id=(
                                    conversation_id
                                ),
                                subject=subject,
                                description=(
                                    escalation[
                                        "description"
                                    ]
                                ),
                                sentiment=(
                                    escalation[
                                        "sentiment"
                                    ]
                                ),
                                priority=(
                                    escalation[
                                        "priority"
                                    ]
                                ),
                                handoff_summary=(
                                    escalation[
                                        "handoff_summary"
                                    ]
                                ),
                                agent_context=(
                                    escalation[
                                        "agent_context"
                                    ]
                                ),
                            )
                        )

                        ticket_id = str(
                            ticket[
                                "ticket_id"
                            ]
                        )

                        ticket_status = (
                            ticket.get(
                                "status",
                                "open",
                            )
                        )

                        ticket_subject = (
                            ticket.get(
                                "subject",
                                subject,
                            )
                        )

                        if (
                            parsed.language
                            == "roman_urdu"
                        ):
                            content = (
                                "Aapki support request "
                                "team ko bhej di gayi hai. "
                                f"Ticket ID: {ticket_id}"
                            )
                        else:
                            content = (
                                escalation[
                                    "response"
                                ]
                                +
                                f" Ticket ID: {ticket_id}."
                            )

                        blocks = [
                            SupportEscalationBlock(
                                ticket_id=(
                                    ticket_id
                                ),
                                status=(
                                    ticket_status
                                ),
                                subject=(
                                    ticket_subject
                                ),
                                message=content,
                            )
                        ]

                        state_updates = {
                            "last_intent":
                                parsed.intent,
                            "last_support_ticket_id":
                                ticket_id,
                            "language":
                                parsed.language,
                        }

                    except SupportTicketError:
                        if (
                            parsed.language
                            == "roman_urdu"
                        ):
                            content = (
                                "Maazrat, aapki "
                                "support request abhi "
                                "create nahi ho saki. "
                                "Please dobara try karein."
                            )
                        else:
                            content = (
                                "Sorry, I couldn't "
                                "create your support "
                                "request right now. "
                                "Please try again."
                            )

                        blocks = []
                        state_updates = {
                            "last_intent":
                                parsed.intent,
                            "language":
                                parsed.language,
                        }

                    chat_service.merge_conversation_state(
                        customer_id,
                        conversation_id,
                        state_updates,
                    )
            else:
                content = (
                    customer_interaction_agent
                    .compose_unhandled_response(
                        parsed.language
                    )
                )

                blocks = []

                (
                    chat_service
                    .merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "last_intent":
                                parsed.intent,
                            "language":
                                parsed.language,
                        },
                    )
                )

            assistant_message = (
                chat_service
                .append_message(
                    customer_id,
                    conversation_id,
                    role="assistant",
                    content=(
                        content
                    ),
                    agent_key=(
                        self.agent_key
                    ),
                    metadata={
                        "intent":
                            parsed.intent,
                        "blocks": [
                            block
                            .model_dump(
                                mode="json"
                            )
                            for block
                            in blocks
                        ],
                    },
                )
            )

            (
                chat_service
                .complete_agent_run(
                    run_id,
                    final_response=(
                        content
                    ),
                    metadata={
                        "intent":
                            parsed.intent,
                        "language":
                            parsed.language,
                        "block_types": [
                            block.type
                            for block
                            in blocks
                        ],
                    },
                )
            )

            return ChatTurnResponse(
                conversation_id=(
                    conversation_id
                ),
                message_id=str(
                    assistant_message[
                        "id"
                    ]
                ),
                content=(
                    content
                ),
                language=(
                    parsed.language
                ),
                blocks=(
                    blocks
                ),
            )

        except Exception as exc:
            try:
                (
                    chat_service
                    .fail_agent_run(
                        run_id,
                        error_message=(
                            str(exc)
                        ),
                    )
                )
            finally:
                raise


orchestrator_agent = (
    OrchestratorAgent()
)
