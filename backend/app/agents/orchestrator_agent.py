from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from app.agents.customer_interaction_agent import (
    customer_interaction_agent,
)
from app.agents.inventory_agent import (
    inventory_agent,
)
from app.agents.product_agent import (
    product_agent,
)

from app.agents.purchase_agent import (
    purchase_agent,
)

from app.schemas.chat import (
    CartSummaryBlock,
    ChatTurnResponse,
    ParsedCustomerMessage,
    ProductCard,
    ProductCarouselBlock,
    SmartCartRuleBlock,
    StockBranchItem,
    StockStatusBlock,
    WishlistBlock,
    OrderConfirmationBlock,
)
from app.services import chat_service
from app.services.cart_service import (
    add_cart_item,
)
from app.services.smart_cart_service import (
    create_customer_smart_cart_rule,
)
from app.services.wishlist_service import (
    add_wishlist_item,
)


# ============================================================================
# Internal plan model
# ============================================================================


@dataclass(frozen=True)
class PlannedTask:
    agent_key: str
    task_type: str
    tool_name: str


# ============================================================================
# Context-reference resolution
# ============================================================================


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
    Resolve a specific variant using this priority:

    1. Explicit variant UUID
    2. Ordinal reference against last search results
       ("first one", "second one")
    3. Context reference against last selected variant
       ("it", "this one", "isko")

    No product/variant is invented.
    """

    if parsed.entities.variant_id:
        return parsed.entities.variant_id

    ordinal = parsed.entities.ordinal_reference

    if ordinal is not None:
        variant_ids = (
            state.get("last_search_variant_ids")
            or []
        )

        index = ordinal - 1

        if 0 <= index < len(variant_ids):
            return str(variant_ids[index])

        return None

    if _CONTEXT_REFERENCE_RE.search(
        parsed.raw_message
    ):
        last_variant_id = state.get(
            "last_variant_id"
        )

        if last_variant_id:
            return str(last_variant_id)

    return None


# ============================================================================
# Planning
# ============================================================================


def plan_intent(
    intent: str,
) -> PlannedTask | None:
    if intent == "product_search":
        return PlannedTask(
            agent_key="product_agent",
            task_type="product_search",
            tool_name=(
                "product_agent.search"
            ),
        )

    if intent == "stock_check":
        return PlannedTask(
            agent_key="inventory_agent",
            task_type="stock_check",
            tool_name=(
                "inventory_agent."
                "get_stock_snapshot_with_branches"
            ),
        )

    if intent == "add_to_cart":
        return PlannedTask(
            agent_key="orchestrator_agent",
            task_type="add_to_cart",
            tool_name=(
                "cart_service.add_cart_item"
            ),
        )

    if intent == "add_to_wishlist":
        return PlannedTask(
            agent_key="orchestrator_agent",
            task_type="add_to_wishlist",
            tool_name=(
                "wishlist_service."
                "add_wishlist_item"
            ),
        )

    if intent == "smart_cart_create":
        return PlannedTask(
            agent_key="orchestrator_agent",
            task_type=(
                "create_smart_cart_rule"
            ),
            tool_name=(
                "smart_cart_service."
                "create_customer_smart_cart_rule"
            ),
        )

    if intent == "purchase":
        return PlannedTask(
            agent_key="purchase_agent",
            task_type="purchase",
            tool_name=(
                "purchase_agent.purchase"
            ),
        )

    return None


# ============================================================================
# Result validation / typed block conversion
# ============================================================================


def _primary_image_url(
    result: dict,
) -> str | None:
    images = result.get("images") or []

    primary = next(
        (
            image
            for image in images
            if image.get("is_primary")
        ),
        None,
    )

    if primary is None and images:
        primary = images[0]

    if not primary:
        return None

    return primary.get("image_url")


def _max_available(
    result: dict,
) -> int:
    inventory = result.get("inventory") or []

    return max(
        (
            int(
                row.get("available_quantity")
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
    Validate specialist output before exposing it to chat.

    Malformed search rows are skipped rather than converted into
    hallucinated product values.
    """

    products: list[ProductCard] = []

    for result in results:
        product = result.get("product") or {}
        variant = result.get("variant") or {}
        pricing = result.get("pricing") or {}
        color = variant.get("color") or {}
        size = variant.get("size") or {}

        product_id = result.get("product_id")
        variant_id = result.get("variant_id")
        name = product.get("name")
        sku = variant.get("sku")

        # Required identity fields must come from specialist output.
        if not all(
            [
                product_id,
                variant_id,
                name,
                sku,
            ]
        ):
            continue

        effective_price = pricing.get(
            "effective_price"
        )

        if effective_price is None:
            effective_price = variant.get(
                "price"
            )

        products.append(
            ProductCard(
                product_id=str(product_id),
                variant_id=str(variant_id),
                name=str(name),
                sku=str(sku),
                brand=product.get("brand"),
                material=product.get(
                    "material"
                ),
                color=color.get("name"),
                size=size.get("name"),
                effective_price=(
                    float(effective_price)
                    if effective_price
                    is not None
                    else None
                ),
                image_url=_primary_image_url(
                    result
                ),
                max_available_at_one_branch=(
                    _max_available(result)
                ),
            )
        )

    return ProductCarouselBlock(
        title="Products",
        products=products,
    )


def build_stock_status_block(
    variant_id: str,
    inventory: list[dict],
    *,
    branch_name: str | None = None,
) -> StockStatusBlock:
    branches: list[StockBranchItem] = []

    for row in inventory:
        branch = row.get("branch") or {}

        if not branch:
            continue

        actual_branch_name = branch.get("name")

        if (
            branch_name
            and str(
                actual_branch_name or ""
            ).strip().lower()
            != branch_name.strip().lower()
        ):
            continue

        status = row.get("status")

        # Only DB-authoritative statuses are allowed through.
        if status not in {
            "out_of_stock",
            "low_stock",
            "available",
        }:
            continue

        branches.append(
            StockBranchItem(
                branch_id=str(
                    row["branch_id"]
                ),
                branch_name=str(
                    actual_branch_name
                ),
                city=branch.get("city"),
                area=branch.get("area"),
                address=branch.get(
                    "address"
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
        variant_id=variant_id,
        branches=branches,
    )


# ============================================================================
# Response composition
# ============================================================================


def _search_message(
    language: str,
    count: int,
) -> str:
    if count == 0:
        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                "Mujhe koi matching "
                "product nahi mila."
            )

        return (
            "I couldn't find any "
            "matching products."
        )

    if language == "roman_urdu":
        return (
            f"Mujhe {count} matching "
            "product milay hain."
        )

    if language == "mixed":
        return (
            f"Mujhe {count} matching "
            "products milay hain."
        )

    return (
        f"I found {count} matching "
        f"product{'s' if count != 1 else ''}."
    )


def _stock_message(
    language: str,
    block: StockStatusBlock,
    *,
    requested_branch: str | None = None,
) -> str:
    total = sum(
        row.available_quantity
        for row in block.branches
    )

    if requested_branch:
        if total > 0:
            if language in {
                "roman_urdu",
                "mixed",
            }:
                return (
                    f"Ji, {requested_branch} "
                    f"mein {total} available "
                    "hai."
                )

            return (
                f"Yes, {total} unit"
                f"{'s are' if total != 1 else ' is'} "
                f"available at {requested_branch}."
            )

        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                f"{requested_branch} mein "
                "abhi stock available "
                "nahi hai."
            )

        return (
            "It is currently out of stock "
            f"at {requested_branch}."
        )

    if total > 0:
        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                f"Ji, total {total} unit"
                f"{'s' if total != 1 else ''} "
                "available hain."
            )

        return (
            f"There {'are' if total != 1 else 'is'} "
            f"{total} unit"
            f"{'s' if total != 1 else ''} "
            "available."
        )

    if language in {
        "roman_urdu",
        "mixed",
    }:
        return (
            "Abhi yeh item out of "
            "stock hai."
        )

    return (
        "This item is currently "
        "out of stock."
    )


def _cart_added_message(
    language: str,
    quantity: int,
) -> str:
    if language in {
        "roman_urdu",
        "mixed",
    }:
        return (
            f"Ji, {quantity} item "
            "cart mein add kar diya."
        )

    return (
        f"Added {quantity} item"
        f"{'s' if quantity != 1 else ''} "
        "to your cart."
    )


def _wishlist_added_message(
    language: str,
) -> str:
    if language in {
        "roman_urdu",
        "mixed",
    }:
        return (
            "Ji, item wishlist mein "
            "add kar diya."
        )

    return (
        "Added the item to your "
        "wishlist."
    )


def _item_reference_clarification(
    language: str,
) -> str:
    if language in {
        "roman_urdu",
        "mixed",
    }:
        return (
            "Kaunsa item? Aap first one, "
            "second one, ya koi product "
            "select kar sakte hain."
        )

    return (
        "Which item do you mean? "
        "You can say first one, second one, "
        "or select a product."
    )


def _smart_cart_created_message(
    language: str,
    authorization_mode: str,
) -> str:
    if authorization_mode == "auto_buy":
        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                "Smart Cart rule bana diya. "
                "Condition match hone par "
                "authorized automatic purchase "
                "attempt hoga."
            )

        return (
            "Your Smart Cart rule is active. "
            "When the condition matches, the "
            "authorized automatic purchase "
            "workflow can run."
        )

    if language in {
        "roman_urdu",
        "mixed",
    }:
        return (
            "Smart Cart rule bana diya. "
            "Condition match hone par "
            "aapko notify kiya jayega."
        )

    return (
        "Your Smart Cart rule is active. "
        "You'll be notified when the "
        "condition matches."
    )


# ============================================================================
# Orchestrator
# ============================================================================
def _purchase_result_message(
    language: str,
    result: dict,
) -> str:
    if result.get("success") is True:
        order_id = result.get(
            "order_id"
        )

        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                "Purchase successfully complete "
                "ho gaya. "
                f"Order ID: {order_id}"
            )

        return (
            "Purchase completed successfully. "
            f"Order ID: {order_id}"
        )

    reason = (
        result.get("reason")
        or
        "The purchase could not be completed."
    )

    if language in {
        "roman_urdu",
        "mixed",
    }:
        return (
            "Purchase complete nahi ho saka. "
            f"{reason}"
        )

    return (
        "The purchase could not be completed. "
        f"{reason}"
    )

class OrchestratorAgent:
    agent_key = "orchestrator_agent"

    def _run_traced_tool(
        self,
        *,
        run_id: str,
        plan: PlannedTask,
        arguments: dict,
        call: Callable[[], Any],
    ) -> Any:
        task = (
            chat_service
            .create_agent_task(
                run_id,
                agent_key=plan.agent_key,
                task_type=plan.task_type,
                input_payload=arguments,
            )
        )

        tool_call = (
            chat_service
            .create_agent_tool_call(
                agent_run_id=run_id,
                agent_task_id=task["id"],
                agent_key=plan.agent_key,
                tool_name=plan.tool_name,
                arguments=arguments,
            )
        )

        try:
            result = call()

            chat_service.complete_agent_tool_call(
                tool_call["id"],
                result=result,
            )

            chat_service.complete_agent_task(
                task["id"],
                output_payload={
                    "result": result,
                },
            )

            return result

        except Exception as exc:
            chat_service.fail_agent_tool_call(
                tool_call["id"],
                error_message=str(exc),
            )

            chat_service.fail_agent_task(
                task["id"],
                error_message=str(exc),
            )

            raise

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
                agent_key=self.agent_key,
                metadata={
                    "blocks": [],
                    "intent": parsed.intent,
                },
            )
        )

        if update_state:
            chat_service.merge_conversation_state(
                customer_id,
                conversation_id,
                {
                    "last_intent": parsed.intent,
                    "language": parsed.language,
                },
            )

        chat_service.complete_agent_run(
            run_id,
            final_response=content,
            metadata={
                "intent": parsed.intent,
                "clarification": True,
            },
        )

        return ChatTurnResponse(
            conversation_id=conversation_id,
            message_id=str(
                assistant_message["id"]
            ),
            content=content,
            language=parsed.language,
            blocks=[],
        )

    def process_turn(
        self,
        *,
        customer_id: str,
        message: str,
        conversation_id: str | None = None,
    ) -> ChatTurnResponse:
        parsed = (
            customer_interaction_agent
            .parse(message)
        )

        conversation = (
            chat_service
            .get_or_create_conversation(
                customer_id,
                conversation_id=conversation_id,
                language=parsed.language,
                title=(
                    message.strip()[:80]
                    if not conversation_id
                    else None
                ),
            )
        )

        conversation_id = str(
            conversation["id"]
        )

        if (
            conversation.get(
                "language"
            )
            != parsed.language
        ):
            chat_service.update_conversation_language(
                customer_id,
                conversation_id,
                parsed.language,
            )

        # Always persist the user message.
        # This must NOT be inside the language-change if block.
        user_message = (
            chat_service
            .append_message(
                customer_id,
                conversation_id,
                role="user",
                content=message.strip(),
                metadata={
                    "language":
                        parsed.language,
                },
            )
        )

        user_message_id = str(
            user_message["id"]
        )

        run = (
            chat_service
            .create_agent_run(
                customer_id,
                conversation_id,
                input_text=message,
                root_agent_key=self.agent_key,
                metadata={
                    "language": parsed.language,
                },
            )
        )

        run_id = str(run["id"])

        try:
            # ---------------------------------------------------------
            # Trace Customer Interaction Agent
            # ---------------------------------------------------------
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
                        "message": message,
                    },
                )
            )

            chat_service.complete_agent_task(
                parse_task["id"],
                output_payload=(
                    parsed.model_dump(
                        mode="json"
                    )
                ),
            )

            state = (
                chat_service
                .get_conversation_state(
                    customer_id,
                    conversation_id,
                )
            )

            # ---------------------------------------------------------
            # Parser-level clarification
            # ---------------------------------------------------------
            if parsed.requires_clarification:
                content = (
                    parsed.clarification_question
                    or (
                        "Could you clarify "
                        "what you mean?"
                    )
                )

                return self._finish_clarification(
                    customer_id=customer_id,
                    conversation_id=(
                        conversation_id
                    ),
                    run_id=run_id,
                    parsed=parsed,
                    content=content,
                )

            # ---------------------------------------------------------
            # Product search
            # ---------------------------------------------------------
            if parsed.intent == "product_search":
                plan = plan_intent(parsed.intent)
                assert plan is not None

                arguments = {
                    "query": parsed.raw_message,
                    "match_count": 10,
                    "color": parsed.entities.color,
                    "size": parsed.entities.size,
                    "material": (
                        parsed.entities.material
                    ),
                    "category": (
                        parsed.entities.category
                    ),
                    "min_price": (
                        parsed.entities.min_price
                    ),
                    "max_price": (
                        parsed.entities.max_price
                    ),
                }

                results = self._run_traced_tool(
                    run_id=run_id,
                    plan=plan,
                    arguments=arguments,
                    call=lambda: (
                        product_agent.search(
                            **arguments
                        )
                    ),
                )

                block = build_product_carousel(
                    results
                )

                variant_ids = [
                    product.variant_id
                    for product in block.products
                ]

                updates = {
                    "last_intent": parsed.intent,
                    "language": parsed.language,
                    "last_search_variant_ids": (
                        variant_ids
                    ),
                }

                if variant_ids:
                    updates[
                        "last_variant_id"
                    ] = variant_ids[0]

                chat_service.merge_conversation_state(
                    customer_id,
                    conversation_id,
                    updates,
                )

                content = _search_message(
                    parsed.language,
                    len(block.products),
                )

                blocks = [block]

            # ---------------------------------------------------------
            # Stock check
            # ---------------------------------------------------------
            elif parsed.intent == "stock_check":
                variant_id = (
                    resolve_variant_reference(
                        parsed,
                        state,
                    )
                )

                if not variant_id:
                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=(
                            conversation_id
                        ),
                        run_id=run_id,
                        parsed=parsed,
                        content=(
                            "Which exact item do you "
                            "want me to check? You can "
                            "say first one, second one, "
                            "or select a product."
                        ),
                    )

                plan = plan_intent(parsed.intent)
                assert plan is not None

                arguments = {
                    "variant_id": variant_id,
                }

                inventory = self._run_traced_tool(
                    run_id=run_id,
                    plan=plan,
                    arguments=arguments,
                    call=lambda: (
                        inventory_agent
                        .get_stock_snapshot_with_branches(
                            variant_id
                        )
                    ),
                )

                block = build_stock_status_block(
                    variant_id,
                    inventory,
                    branch_name=(
                        parsed.entities.branch_name
                    ),
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

                content = _stock_message(
                    parsed.language,
                    block,
                    requested_branch=(
                        parsed.entities.branch_name
                    ),
                )

                blocks = [block]

            # ---------------------------------------------------------
            # Add to cart
            # ---------------------------------------------------------
            elif parsed.intent == "add_to_cart":
                variant_id = (
                    resolve_variant_reference(
                        parsed,
                        state,
                    )
                )

                if not variant_id:
                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=(
                            conversation_id
                        ),
                        run_id=run_id,
                        parsed=parsed,
                        content=(
                            _item_reference_clarification(
                                parsed.language
                            )
                        ),
                    )

                quantity = (
                    parsed.entities.quantity
                    or 1
                )

                plan = plan_intent(parsed.intent)
                assert plan is not None

                arguments = {
                    "variant_id": variant_id,
                    "quantity": quantity,
                }

                cart = self._run_traced_tool(
                    run_id=run_id,
                    plan=plan,
                    arguments=arguments,
                    call=lambda: add_cart_item(
                        customer_id=customer_id,
                        variant_id=variant_id,
                        quantity=quantity,
                    ),
                )

                block = CartSummaryBlock(
                    data=cart
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

                content = _cart_added_message(
                    parsed.language,
                    quantity,
                )

                blocks = [block]

            # ---------------------------------------------------------
            # Add to wishlist
            # ---------------------------------------------------------
            elif parsed.intent == "add_to_wishlist":
                variant_id = (
                    resolve_variant_reference(
                        parsed,
                        state,
                    )
                )

                if not variant_id:
                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=(
                            conversation_id
                        ),
                        run_id=run_id,
                        parsed=parsed,
                        content=(
                            _item_reference_clarification(
                                parsed.language
                            )
                        ),
                    )

                plan = plan_intent(parsed.intent)
                assert plan is not None

                arguments = {
                    "variant_id": variant_id,
                }

                wishlist = self._run_traced_tool(
                    run_id=run_id,
                    plan=plan,
                    arguments=arguments,
                    call=lambda: add_wishlist_item(
                        customer_id=customer_id,
                        variant_id=variant_id,
                    ),
                )

                block = WishlistBlock(
                    data=wishlist
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

                content = _wishlist_added_message(
                    parsed.language
                )

                blocks = [block]

            # ---------------------------------------------------------
            # Create Smart Cart rule
            # ---------------------------------------------------------
            elif parsed.intent == "smart_cart_create":
                variant_id = (
                    resolve_variant_reference(
                        parsed,
                        state,
                    )
                )

                if not variant_id:
                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=(
                            conversation_id
                        ),
                        run_id=run_id,
                        parsed=parsed,
                        content=(
                            _item_reference_clarification(
                                parsed.language
                            )
                        ),
                    )

                if (
                    parsed.entities.target_price
                    is None
                    and parsed.entities
                    .min_discount_percentage
                    is None
                ):
                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=(
                            conversation_id
                        ),
                        run_id=run_id,
                        parsed=parsed,
                        content=(
                            "What price or minimum "
                            "discount should trigger "
                            "the Smart Cart rule?"
                        ),
                    )

                authorization_mode = (
                    parsed.entities
                    .authorization_mode
                )

                if authorization_mode is None:
                    return self._finish_clarification(
                        customer_id=customer_id,
                        conversation_id=(
                            conversation_id
                        ),
                        run_id=run_id,
                        parsed=parsed,
                        content=(
                            "Should I only notify you "
                            "when the condition matches, "
                            "or are you authorizing "
                            "automatic purchase?"
                        ),
                    )

                quantity = (
                    parsed.entities.quantity
                    or 1
                )

                plan = plan_intent(parsed.intent)
                assert plan is not None

                arguments = {
                    "variant_id": variant_id,
                    "quantity": quantity,
                    "target_price": (
                        parsed.entities.target_price
                    ),
                    "min_discount_percentage": (
                        parsed.entities
                        .min_discount_percentage
                    ),
                    "authorization_mode": (
                        authorization_mode
                    ),
                    "branch_id": None,
                }

                rule = self._run_traced_tool(
                    run_id=run_id,
                    plan=plan,
                    arguments=arguments,
                    call=lambda: (
                        create_customer_smart_cart_rule(
                            customer_id=customer_id,
                            variant_id=variant_id,
                            quantity=quantity,
                            target_price=(
                                parsed.entities
                                .target_price
                            ),
                            min_discount_percentage=(
                                parsed.entities
                                .min_discount_percentage
                            ),
                            authorization_mode=(
                                authorization_mode
                            ),
                            branch_id=None,
                        )
                    ),
                )

                block = SmartCartRuleBlock(
                    rule=rule
                )

                chat_service.merge_conversation_state(
                    customer_id,
                    conversation_id,
                    {
                        "last_intent": parsed.intent,
                        "last_variant_id": variant_id,
                        "last_smart_cart_rule_id": (
                            rule["id"]
                        ),
                        "language": parsed.language,
                    },
                )

                content = (
                    _smart_cart_created_message(
                        parsed.language,
                        authorization_mode,
                    )
                )

                blocks = [block]

                        # ---------------------------------------------------------
            # Purchase
            # ---------------------------------------------------------
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

                # Never guess which product the
                # customer intended to purchase.
                if not variant_id:
                    content = (
                        _item_reference_clarification(
                            parsed.language
                        )
                    )

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

                    chat_service.complete_agent_run(
                        run_id,
                        final_response=content,
                        metadata={
                            "intent":
                                parsed.intent,
                            "clarification":
                                True,
                        },
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

                quantity = (
                    parsed.entities.quantity
                    or 1
                )

                # Only use a reservation if the
                # conversation state explicitly says
                # that reservation belongs to this
                # exact variant.
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

                plan = plan_intent(
                    parsed.intent
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
                    self._run_traced_tool(
                        run_id=run_id,
                        plan=plan,
                        arguments=arguments,
                        call=lambda: (
                            purchase_agent
                            .purchase(
                                customer_id=
                                    customer_id,
                                variant_id=
                                    variant_id,
                                quantity=
                                    quantity,
                                idempotency_key=
                                    idempotency_key,
                                branch_id=None,
                                reservation_id=
                                    reservation_id,
                            )
                        ),
                    )
                )

                # Validate specialist/service output
                # before exposing a confirmation block.
                success = (
                    result.get("success")
                    is True
                )

                if success:
                    order_id = result.get(
                        "order_id"
                    )

                    if not order_id:
                        raise ValueError(
                            "Purchase service returned "
                            "success=True without "
                            "an order_id."
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
                            order=order_payload
                        )
                    )

                    blocks = [block]

                    state_updates = {
                        "last_intent":
                            parsed.intent,
                        "last_variant_id":
                            variant_id,
                        "last_order_id":
                            str(order_id),
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
                    # A failed purchase is NOT an
                    # order confirmation.
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
                        "language":
                            parsed.language,
                    }

                chat_service.merge_conversation_state(
                    customer_id,
                    conversation_id,
                    state_updates,
                )

                content = (
                    _purchase_result_message(
                        parsed.language,
                        result,
                    )
                )    

            # ---------------------------------------------------------
            # Actions not connected yet
            # ---------------------------------------------------------
            else:
                content = (
                    "I understood the request, "
                    "but this action has not been "
                    "connected to the orchestrator "
                    "yet."
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

            # ---------------------------------------------------------
            # Persist assistant response
            # ---------------------------------------------------------
            assistant_message = (
                chat_service
                .append_message(
                    customer_id,
                    conversation_id,
                    role="assistant",
                    content=content,
                    agent_key=self.agent_key,
                    metadata={
                        "intent": parsed.intent,
                        "blocks": [
                            block.model_dump(
                                mode="json"
                            )
                            for block in blocks
                        ],
                    },
                )
            )

            chat_service.complete_agent_run(
                run_id,
                final_response=content,
                metadata={
                    "intent": parsed.intent,
                    "language": parsed.language,
                    "block_types": [
                        block.type
                        for block in blocks
                    ],
                },
            )

            return ChatTurnResponse(
                conversation_id=conversation_id,
                message_id=str(
                    assistant_message["id"]
                ),
                content=content,
                language=parsed.language,
                blocks=blocks,
            )

        except Exception as exc:
            try:
                chat_service.fail_agent_run(
                    run_id,
                    error_message=str(exc),
                )
            finally:
                raise


orchestrator_agent = OrchestratorAgent()
