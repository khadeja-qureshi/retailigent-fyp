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
from app.schemas.chat import (
    CartSummaryBlock,
    BranchMapBlock,
    ChatTurnResponse,
    SupportEscalationBlock,
    OrderConfirmationBlock,
    ParsedCustomerMessage,
    ProductCard,
    RecommendationBlock,
    ProductCarouselBlock,
    SmartCartRuleBlock,
    StockBranchItem,
    StockStatusBlock,
    WishlistBlock,
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
from app.services.support_service import (
    SupportTicketError,
    create_support_ticket,
)
from app.services.demand_signal_service import (
    record_demand_signal,
)


logger = logging.getLogger(
    __name__
)


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


def build_stock_status_block(
    variant_id: str,
    inventory: list[dict],
    *,
    branch_name: (
        str | None
    ) = None,
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
            and
            str(
                actual_branch_name
                or ""
            )
            .strip()
            .lower()
            !=
            branch_name
            .strip()
            .lower()
        ):
            continue

        status = (
            row.get(
                "status"
            )
        )

        if status not in {
            "out_of_stock",
            "low_stock",
            "available",
        }:
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
                plan = plan_intent(parsed.intent)
                assert plan is not None

                arguments = {
                    "branch_name": parsed.entities.branch_name,
                }

                results = self._run_traced_tool(
                    run_id=run_id,
                    plan=plan,
                    arguments=arguments,
                    call=lambda: location_agent.search(**arguments),
                )

                block = BranchMapBlock(
                    title="Store locations and hours",
                    branches=results,
                )

                (
                    chat_service
                    .merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "last_intent": parsed.intent,
                            "language": parsed.language,
                        },
                    )
                )

                if results:
                    content = (
                        "Here are the matching store locations, "
                        "addresses, and opening hours."
                    )
                else:
                    content = (
                        "I couldn't find an active store matching "
                        "that location. Try specifying a branch or area."
                    )

                blocks = [block]

            elif (
                parsed.intent
                == "recommendation_search"
            ):
                plan = plan_intent(parsed.intent)
                assert plan is not None

                arguments = {
                    "customer_id": customer_id,
                    "query": parsed.raw_message,
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
                        parsed.raw_message,
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
                variant_ids = (
                    resolve_variant_references(
                        parsed,
                        state,
                    )
                )

                if not variant_ids:
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
                                .compose_stock_reference_clarification(
                                    parsed.language
                                )
                            ),
                        )
                    )

                plan = (
                    plan_intent(
                        parsed.intent
                    )
                )

                assert (
                    plan is not None
                )

                jobs: list[
                    tuple[
                        PlannedTask,
                        dict,
                        Callable[
                            [],
                            Any,
                        ],
                    ]
                ] = []

                for variant_id in variant_ids:
                    arguments = {
                        "variant_id":
                            variant_id,
                    }

                    jobs.append(
                        (
                            plan,
                            arguments,
                            (
                                lambda current_variant_id=variant_id:
                                    inventory_agent
                                    .get_stock_snapshot_with_branches(
                                        current_variant_id
                                    )
                            ),
                        )
                    )

                inventory_results = (
                    self
                    ._run_parallel_traced_tools(
                        run_id=(
                            run_id
                        ),
                        jobs=jobs,
                    )
                )

                requested_branch = (
                    parsed
                    .entities
                    .branch_name
                )

                for variant_id, inventory in zip(
                    variant_ids,
                    inventory_results,
                    strict=True,
                ):
                    if not inventory:
                        continue

                    relevant_rows = []
                    for row in inventory:
                        branch = row.get("branch") or {}
                        if not branch:
                            continue

                        if (
                            requested_branch
                            and str(branch.get("name") or "").strip().lower()
                            != requested_branch.strip().lower()
                        ):
                            continue

                        relevant_rows.append(row)

                    if (
                        relevant_rows
                        and all(
                            int(row.get("available_quantity") or 0) <= 0
                            for row in relevant_rows
                        )
                    ):
                        record_demand_signal(
                            signal_type="insufficient_stock",
                            customer_id=customer_id,
                            variant_id=variant_id,
                            branch_id=(
                                str(relevant_rows[0].get("branch_id"))
                                if requested_branch
                                and relevant_rows[0].get("branch_id") is not None
                                else None
                            ),
                            metadata={
                                "requested_branch": requested_branch,
                                "checked_branch_count": len(relevant_rows),
                                "source": "stock_check",
                            },
                        )

                stock_blocks = [
                    build_stock_status_block(
                        variant_id,
                        inventory,
                        branch_name=(
                            parsed
                            .entities
                            .branch_name
                        ),
                    )
                    for (
                        variant_id,
                        inventory,
                    ) in zip(
                        variant_ids,
                        inventory_results,
                        strict=True,
                    )
                ]

                (
                    chat_service
                    .merge_conversation_state(
                        customer_id,
                        conversation_id,
                        {
                            "last_intent":
                                parsed.intent,
                            "last_variant_id":
                                variant_ids[-1],
                            "language":
                                parsed.language,
                        },
                    )
                )

                if (
                    len(stock_blocks)
                    == 1
                ):
                    content = (
                        customer_interaction_agent
                        .compose_stock_response(
                            parsed.language,
                            stock_blocks[0],
                            requested_branch=(
                                parsed
                                .entities
                                .branch_name
                            ),
                        )
                    )
                else:
                    content = (
                        customer_interaction_agent
                        .compose_multi_stock_response(
                            parsed.language,
                            len(
                                stock_blocks
                            ),
                        )
                    )

                blocks = list(
                    stock_blocks
                )

            elif (
                parsed.intent
                == "add_to_cart"
            ):
                variant_id = (
                    resolve_variant_reference(
                        parsed,
                        state,
                    )
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
                }

                cart = (
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
                            add_cart_item(
                                customer_id=(
                                    customer_id
                                ),
                                variant_id=(
                                    variant_id
                                ),
                                quantity=(
                                    quantity
                                ),
                            )
                        ),
                    )
                )

                block = (
                    CartSummaryBlock(
                        data=cart
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
                            "language":
                                parsed.language,
                        },
                    )
                )

                content = (
                    customer_interaction_agent
                    .compose_cart_added_response(
                        parsed.language,
                        quantity,
                    )
                )

                blocks = [
                    block
                ]

            elif (
                parsed.intent
                == "add_to_wishlist"
            ):
                variant_id = (
                    resolve_variant_reference(
                        parsed,
                        state,
                    )
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
                }

                wishlist = (
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
                            add_wishlist_item(
                                customer_id=(
                                    customer_id
                                ),
                                variant_id=(
                                    variant_id
                                ),
                            )
                        ),
                    )
                )

                block = (
                    WishlistBlock(
                        data=wishlist
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
                            "language":
                                parsed.language,
                        },
                    )
                )

                content = (
                    customer_interaction_agent
                    .compose_wishlist_added_response(
                        parsed.language
                    )
                )

                blocks = [
                    block
                ]

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
                == "purchase"
            ):
                variant_id = (
                    resolve_variant_reference(
                        parsed,
                        state,
                    )
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

            elif parsed.intent == "support_request":
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
                        str(item.get("role", "")).casefold()
                        in {"user", "customer"}
                        and str(item.get("content", "")).strip()
                        == message.strip()
                    )
                ]

                escalation = support_agent.prepare_escalation(
                    message=message,
                    language=parsed.language,
                    customer_context=customer_context,
                    recent_messages=recent_messages,
                )

                subject = escalation["subject"]

                try:
                    ticket = create_support_ticket(
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                        subject=subject,
                        description=escalation["description"],
                        sentiment=escalation["sentiment"],
                        priority=escalation["priority"],
                        handoff_summary=escalation["handoff_summary"],
                        agent_context=escalation["agent_context"],
                    )

                    ticket_id = str(ticket["ticket_id"])
                    ticket_status = ticket.get("status", "open")
                    ticket_subject = ticket.get("subject", subject)

                    if parsed.language == "roman_urdu":
                        content = (
                            "Aapki support request team ko bhej di gayi hai. "
                            f"Ticket ID: {ticket_id}"
                        )
                    else:
                        content = (
                            escalation["response"]
                            + f" Ticket ID: {ticket_id}."
                        )

                    blocks = [
                        SupportEscalationBlock(
                            ticket_id=ticket_id,
                            status=ticket_status,
                            subject=ticket_subject,
                            message=content,
                        )
                    ]

                    state_updates = {
                        "last_intent": parsed.intent,
                        "last_support_ticket_id": ticket_id,
                        "language": parsed.language,
                    }

                except SupportTicketError:
                    if parsed.language == "roman_urdu":
                        content = (
                            "Maazrat, aapki support request "
                            "abhi create nahi ho saki. "
                            "Please dobara try karein."
                        )
                    else:
                        content = (
                            "Sorry, I couldn't create your "
                            "support request right now. "
                            "Please try again."
                        )

                    blocks = []
                    state_updates = {
                        "last_intent": parsed.intent,
                        "language": parsed.language,
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
