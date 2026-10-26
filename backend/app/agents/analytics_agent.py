from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.config import settings
from app.services import analytics_service
from app.services.analytics_service import AnalyticsServiceError

logger = logging.getLogger(__name__)

MAX_QUESTION_LENGTH = 1000
MAX_CONTEXT_ROWS = 20
MAX_SUMMARY_ITEMS = 5


def _to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default

    if isinstance(value, bool):
        return int(value)

    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(str(value)))
        except (TypeError, ValueError):
            return default


def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _first_nonempty(
    row: dict[str, Any],
    *keys: str,
) -> str:
    for key in keys:
        value = _clean_text(row.get(key))

        if value:
            return value

    return ""


def _format_variant_label(
    row: dict[str, Any],
) -> str:
    product_name = _first_nonempty(
        row,
        "product_name",
        "name",
        "product",
    )

    color = _first_nonempty(
        row,
        "color_name",
        "requested_color",
        "color",
    )

    size = _first_nonempty(
        row,
        "size_name",
        "requested_size",
        "size",
    )

    sku = _first_nonempty(
        row,
        "sku",
        "variant_sku",
    )

    details = [
        value
        for value in (
            color,
            size,
        )
        if value
    ]

    if product_name:
        if details:
            return (
                f"{product_name} "
                f"({', '.join(details)})"
            )

        return product_name

    if sku:
        return sku

    variant_id = _first_nonempty(
        row,
        "variant_id",
    )

    product_id = _first_nonempty(
        row,
        "product_id",
    )

    if variant_id:
        return f"Variant {variant_id}"

    if product_id:
        return f"Product {product_id}"

    if details:
        return ", ".join(details)

    return "Unnamed item"


def _format_branch_label(
    row: dict[str, Any],
) -> str:
    branch_name = _first_nonempty(
        row,
        "branch_name",
        "name",
    )

    city = _first_nonempty(
        row,
        "branch_city",
        "city",
    )

    branch_id = _first_nonempty(
        row,
        "branch_id",
        "id",
    )

    if branch_name and city:
        return f"{branch_name} ({city})"

    if branch_name:
        return branch_name

    if city:
        return city

    if branch_id:
        return f"Branch {branch_id}"

    return "Unnamed branch"


class AnalyticsAgent:
    """
    Staff analytics agent.

    Uses deterministic summaries for common Phase 15 analytics questions.
    Ollama is used only as an optional enhancement for broader questions.

    This guarantees that analytics still provide useful answers even if
    Ollama is unavailable or fails to generate a response.
    """

    agent_key = "analytics"

    def answer(
        self,
        question: str,
    ) -> dict[str, Any]:
        question = question.strip()

        if not question:
            raise ValueError(
                "Please enter a question."
            )

        if len(question) > MAX_QUESTION_LENGTH:
            raise ValueError(
                f"Questions must be "
                f"{MAX_QUESTION_LENGTH} "
                "characters or fewer."
            )

        try:
            demand = (
                analytics_service
                .get_demand_analytics(
                    limit=MAX_CONTEXT_ROWS,
                )
            )

            inventory = (
                analytics_service
                .get_inventory_analytics(
                    limit=MAX_CONTEXT_ROWS,
                )
            )

        except AnalyticsServiceError:
            logger.exception(
                "Could not retrieve staff analytics."
            )

            return {
                "answer": (
                    "I couldn't retrieve the analytics "
                    "data right now. Please try again "
                    "shortly."
                ),
                "data_status": "unavailable",
                "sources": [],
            }

        context = {
            "unmet_demand": demand,
            "inventory": inventory,
        }

        inventory_rows = self._as_rows(
            inventory.get(
                "branches",
                [],
            )
            if isinstance(
                inventory,
                dict,
            )
            else []
        )

        sources = [
            {
                "name": "unmet_demand",
                "record_count":
                    self._count_group_rows(
                        demand
                    ),
            },
            {
                "name":
                    "branch_inventory_summary",
                "record_count":
                    len(inventory_rows),
            },
        ]

        if not self._context_has_records(
            context
        ):
            return {
                "answer": (
                    "The analytics views returned no "
                    "records for this query context. "
                    "This does not establish that demand "
                    "or inventory is zero; check whether "
                    "the underlying data has been "
                    "recorded."
                ),
                "data_status": "empty",
                "sources": sources,
            }

        deterministic = (
            self._deterministic_summary(
                question=question,
                context=context,
            )
        )

        if deterministic:
            answer = deterministic

        else:
            answer = (
                self._summarize_with_ollama(
                    question=question,
                    context=context,
                )
            )

            if not answer:
                answer = (
                    self._generic_data_summary(
                        context
                    )
                )

        return {
            "answer": answer,
            "data_status": "available",
            "sources": sources,
        }

    @staticmethod
    def _as_rows(
        value: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(
            value,
            list,
        ):
            return []

        return [
            row
            for row in value
            if isinstance(
                row,
                dict,
            )
        ]

    def _count_group_rows(
        self,
        group: Any,
    ) -> int:
        if not isinstance(
            group,
            dict,
        ):
            return 0

        return sum(
            len(
                self._as_rows(rows)
            )
            for rows
            in group.values()
        )

    def _context_has_records(
        self,
        context: dict[str, Any],
    ) -> bool:
        for group in context.values():
            if not isinstance(
                group,
                dict,
            ):
                continue

            for rows in group.values():
                if self._as_rows(rows):
                    return True

        return False

    @staticmethod
    def _normalize_question(
        question: str,
    ) -> str:
        normalized = (
            question
            .lower()
            .strip()
        )

        normalized = re.sub(
            r"[^a-z0-9\s_-]+",
            " ",
            normalized,
        )

        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        )

        return normalized

    def _deterministic_summary(
        self,
        *,
        question: str,
        context: dict[str, Any],
    ) -> str | None:
        q = self._normalize_question(
            question
        )

        demand = (
            context.get(
                "unmet_demand"
            )
            if isinstance(
                context.get(
                    "unmet_demand"
                ),
                dict,
            )
            else {}
        )

        inventory = (
            context.get(
                "inventory"
            )
            if isinstance(
                context.get(
                    "inventory"
                ),
                dict,
            )
            else {}
        )

        if self._asks_inventory_summary(
            q
        ):
            return self._summarize_inventory(
                inventory
            )

        if (
            self
            ._asks_high_demand_low_availability(
                q
            )
        ):
            return (
                self
                ._summarize_high_demand_low_availability(
                    demand=demand,
                    inventory=inventory,
                )
            )

        if self._asks_unmet_demand(
            q
        ):
            return (
                self._summarize_unmet_demand(
                    demand
                )
            )

        if (
            self
            ._asks_unavailable_searches(
                q
            )
        ):
            return (
                self
                ._summarize_unavailable_searches(
                    demand
                )
            )

        if self._asks_missing_information(
            q
        ):
            return (
                self
                ._summarize_missing_information(
                    demand=demand,
                    inventory=inventory,
                )
            )

        if self._asks_tickets(
            q
        ):
            return (
                "The current Analytics Agent "
                "context does not include support "
                "ticket rows, so I cannot reliably "
                "rank urgent tickets from this "
                "endpoint. Use the staff Tickets "
                "dashboard for ticket priority and "
                "sentiment data."
            )

        if self._asks_feedback(
            q
        ):
            return (
                "The current Analytics Agent "
                "context does not include feedback "
                "rows, so I cannot reliably identify "
                "feedback needing review from this "
                "endpoint. Use the staff Feedback "
                "dashboard for needs-review and "
                "sentiment data."
            )

        return None

    @staticmethod
    def _asks_inventory_summary(
        q: str,
    ) -> bool:
        return (
            "inventory" in q
            and any(
                phrase in q
                for phrase in (
                    "summarize",
                    "summary",
                    "across branches",
                    "by branch",
                    "availability",
                    "stock",
                )
            )
        )

    @staticmethod
    def _asks_high_demand_low_availability(
        q: str,
    ) -> bool:
        return (
            "demand" in q
            and any(
                phrase in q
                for phrase in (
                    "low availability",
                    "low stock",
                    "high demand",
                    "most demand",
                )
            )
            and any(
                word in q
                for word in (
                    "variant",
                    "variants",
                    "product",
                    "products",
                    "item",
                    "items",
                )
            )
        )

    @staticmethod
    def _asks_unmet_demand(
        q: str,
    ) -> bool:
        return (
            any(
                phrase in q
                for phrase in (
                    "unmet demand",
                    "most searched",
                    "most requested",
                    "highest demand",
                    "demand signals",
                )
            )
            or (
                "demand" in q
                and any(
                    word in q
                    for word in (
                        "most",
                        "top",
                        "highest",
                        "unavailable",
                    )
                )
            )
        )

    @staticmethod
    def _asks_unavailable_searches(
        q: str,
    ) -> bool:
        return any(
            phrase in q
            for phrase in (
                "unavailable product searches",
                "unavailable searches",
                "failed searches",
                "no matching products",
                "searches unavailable",
            )
        )

    @staticmethod
    def _asks_missing_information(
        q: str,
    ) -> bool:
        return (
            (
                "missing" in q
                or "not available" in q
                or "not included" in q
            )
            and (
                "information" in q
                or "data" in q
                or "analytics" in q
            )
        )

    @staticmethod
    def _asks_tickets(
        q: str,
    ) -> bool:
        return any(
            word in q
            for word in (
                "ticket",
                "tickets",
                "support",
                "complaint",
                "complaints",
            )
        )

    @staticmethod
    def _asks_feedback(
        q: str,
    ) -> bool:
        return (
            "feedback" in q
            or "reviews" in q
        )

    def _get_demand_rows(
        self,
        demand: dict[str, Any],
        *preferred_keys: str,
    ) -> list[dict[str, Any]]:
        for key in preferred_keys:
            rows = self._as_rows(
                demand.get(key)
            )

            if rows:
                return rows

        return []

    def _summarize_unmet_demand(
        self,
        demand: dict[str, Any],
    ) -> str:
        rows = self._get_demand_rows(
            demand,
            "product_demand_availability",
            "products",
            "product_demand",
            "demand_vs_availability",
            "high_interest_low_availability",
        )

        if not rows:
            rows = self._get_demand_rows(
                demand,
                "unavailable_searches",
                "searches",
            )

        if not rows:
            return (
                "No unmet-demand rows were returned "
                "by the analytics views. That means "
                "there is nothing in the retrieved "
                "result set to rank."
            )

        def score(
            row: dict[str, Any],
        ) -> int:
            return max(
                _to_int(
                    row.get(
                        "unfulfilled_signal_count"
                    )
                ),
                _to_int(
                    row.get(
                        "demand_signal_count"
                    )
                ),
                _to_int(
                    row.get(
                        "signal_count"
                    )
                ),
                _to_int(
                    row.get(
                        "count"
                    )
                ),
            )

        ranked = sorted(
            rows,
            key=score,
            reverse=True,
        )

        lines: list[str] = []

        for row in ranked[
            :MAX_SUMMARY_ITEMS
        ]:
            count = score(
                row
            )

            if _first_nonempty(
                row,
                "product_name",
                "name",
                "product",
                "variant_id",
                "product_id",
            ):
                label = (
                    _format_variant_label(
                        row
                    )
                )

            else:
                color = _first_nonempty(
                    row,
                    "requested_color",
                    "color_name",
                )

                size = _first_nonempty(
                    row,
                    "requested_size",
                    "size_name",
                )

                signal_type = (
                    _first_nonempty(
                        row,
                        "signal_type",
                    )
                )

                parts = [
                    value
                    for value in (
                        color,
                        size,
                        (
                            signal_type
                            .replace(
                                "_",
                                " ",
                            )
                            if signal_type
                            else ""
                        ),
                    )
                    if value
                ]

                label = (
                    ", ".join(
                        parts
                    )
                    or "Unavailable search"
                )

            lines.append(
                f"- {label}: "
                f"{count} unfulfilled "
                f"demand signal"
                f"{'' if count == 1 else 's'}."
            )

        return (
            "The highest unmet demand in "
            "the retrieved analytics is:\n"
            + "\n".join(
                lines
            )
        )

    def _summarize_high_demand_low_availability(
        self,
        *,
        demand: dict[str, Any],
        inventory: dict[str, Any],
    ) -> str:
        rows = self._get_demand_rows(
            demand,
            "high_interest_low_availability",
            "product_demand_availability",
            "demand_vs_availability",
            "products",
        )

        if not rows:
            return (
                "The retrieved analytics do not "
                "contain rows that combine demand "
                "with item-level availability, so "
                "I cannot reliably rank high-demand, "
                "low-availability variants."
            )

        def demand_score(
            row: dict[str, Any],
        ) -> int:
            return max(
                _to_int(
                    row.get(
                        "unfulfilled_signal_count"
                    )
                ),
                _to_int(
                    row.get(
                        "demand_signal_count"
                    )
                ),
                _to_int(
                    row.get(
                        "signal_count"
                    )
                ),
            )

        def availability_score(
            row: dict[str, Any],
        ) -> int:
            for key in (
                "available_quantity",
                "available_stock",
                "availability",
                "total_available",
            ):
                if (
                    row.get(key)
                    is not None
                ):
                    return _to_int(
                        row.get(key)
                    )

            return 0

        ranked = sorted(
            rows,
            key=lambda row: (
                -demand_score(
                    row
                ),
                availability_score(
                    row
                ),
            ),
        )

        lines: list[str] = []

        for row in ranked[
            :MAX_SUMMARY_ITEMS
        ]:
            demand_count = (
                demand_score(
                    row
                )
            )

            available: (
                int | None
            ) = None

            for key in (
                "available_quantity",
                "available_stock",
                "availability",
                "total_available",
            ):
                if (
                    row.get(key)
                    is not None
                ):
                    available = _to_int(
                        row.get(key)
                    )

                    break

            label = (
                _format_variant_label(
                    row
                )
            )

            if available is None:
                lines.append(
                    f"- {label}: "
                    f"{demand_count} "
                    "unfulfilled demand signal"
                    f"{'' if demand_count == 1 else 's'}; "
                    "the retrieved row does not "
                    "include a direct stock quantity."
                )

            else:
                lines.append(
                    f"- {label}: "
                    f"{demand_count} "
                    "unfulfilled demand signal"
                    f"{'' if demand_count == 1 else 's'}, "
                    f"{available} available unit"
                    f"{'' if available == 1 else 's'}."
                )

        inventory_rows = (
            self._as_rows(
                inventory.get(
                    "branches",
                    [],
                )
            )
        )

        suffix = ""

        if inventory_rows:
            suffix = (
                "\n\nBranch-level inventory "
                "summary is available separately, "
                "but it should not be treated as "
                "variant-level stock unless the "
                "analytics row explicitly links "
                "the same variant and branch."
            )

        return (
            "The strongest high-demand / "
            "low-availability signals are:\n"
            + "\n".join(
                lines
            )
            + suffix
        )

    def _summarize_inventory(
        self,
        inventory: dict[str, Any],
    ) -> str:
        rows = self._as_rows(
            inventory.get(
                "branches",
                [],
            )
        )

        if not rows:
            return (
                "No branch inventory summary "
                "rows were returned, so I cannot "
                "summarize stock across branches "
                "from the current analytics data."
            )

        total_variants = 0
        available_variants = 0
        low_stock_variants = 0
        out_of_stock_variants = 0

        lines: list[str] = []

        for row in rows[
            :MAX_CONTEXT_ROWS
        ]:
            total = _to_int(
                row.get(
                    "total_variants"
                )
            )

            available = _to_int(
                row.get(
                    "available_variants"
                )
            )

            low = _to_int(
                row.get(
                    "low_stock_variants"
                )
            )

            out = _to_int(
                row.get(
                    "out_of_stock_variants"
                )
            )

            total_variants += total
            available_variants += (
                available
            )
            low_stock_variants += low
            out_of_stock_variants += out

            lines.append(
                f"- {_format_branch_label(row)}: "
                f"{available} available, "
                f"{low} low-stock, "
                f"{out} out-of-stock, "
                f"{total} total variant rows."
            )

        return (
            f"Inventory summary across "
            f"{len(rows)} branch"
            f"{'' if len(rows) == 1 else 'es'}:\n"
            + "\n".join(
                lines
            )
            + (
                "\n\nAcross the retrieved "
                "branch summaries: "
                f"{available_variants} available, "
                f"{low_stock_variants} low-stock, "
                f"{out_of_stock_variants} "
                "out-of-stock, "
                f"{total_variants} total "
                "variant rows."
            )
        )

    def _summarize_unavailable_searches(
        self,
        demand: dict[str, Any],
    ) -> str:
        rows = self._get_demand_rows(
            demand,
            "unavailable_searches",
            "searches",
        )

        if not rows:
            return (
                "No unavailable-search rows were "
                "returned by the analytics view. "
                "That does not prove customers "
                "never searched for unavailable "
                "items; it only means the current "
                "retrieved result set is empty."
            )

        def score(
            row: dict[str, Any],
        ) -> int:
            return max(
                _to_int(
                    row.get(
                        "signal_count"
                    )
                ),
                _to_int(
                    row.get(
                        "count"
                    )
                ),
                _to_int(
                    row.get(
                        "unfulfilled_signal_count"
                    )
                ),
            )

        ranked = sorted(
            rows,
            key=score,
            reverse=True,
        )

        lines: list[str] = []

        for row in ranked[
            :MAX_SUMMARY_ITEMS
        ]:
            color = _first_nonempty(
                row,
                "requested_color",
                "color_name",
            )

            size = _first_nonempty(
                row,
                "requested_size",
                "size_name",
            )

            signal_type = (
                _first_nonempty(
                    row,
                    "signal_type",
                )
            )

            descriptors = [
                value
                for value in (
                    color,
                    size,
                    (
                        signal_type
                        .replace(
                            "_",
                            " ",
                        )
                        if signal_type
                        else ""
                    ),
                )
                if value
            ]

            label = (
                ", ".join(
                    descriptors
                )
                or "Unavailable search"
            )

            count = score(
                row
            )

            lines.append(
                f"- {label}: "
                f"{count} signal"
                f"{'' if count == 1 else 's'}."
            )

        return (
            "The most frequent unavailable-search "
            "patterns in the retrieved analytics "
            "are:\n"
            + "\n".join(
                lines
            )
        )

    def _summarize_missing_information(
        self,
        *,
        demand: dict[str, Any],
        inventory: dict[str, Any],
    ) -> str:
        missing: list[str] = []

        product_rows = (
            self._get_demand_rows(
                demand,
                "product_demand_availability",
                "high_interest_low_availability",
                "products",
            )
        )

        search_rows = (
            self._get_demand_rows(
                demand,
                "unavailable_searches",
                "searches",
            )
        )

        branch_rows = self._as_rows(
            inventory.get(
                "branches",
                [],
            )
        )

        if not product_rows:
            missing.append(
                "product/variant-level "
                "demand rows"
            )

        if not search_rows:
            missing.append(
                "unavailable-search "
                "breakdown rows"
            )

        if not branch_rows:
            missing.append(
                "branch inventory "
                "summary rows"
            )

        if (
            product_rows
            and not any(
                any(
                    row.get(key)
                    is not None
                    for key in (
                        "available_quantity",
                        "available_stock",
                        "total_available",
                    )
                )
                for row
                in product_rows
            )
        ):
            missing.append(
                "direct item-level available "
                "quantities in the demand rows"
            )

        missing.extend(
            [
                "support-ticket records",
                "feedback review records",
            ]
        )

        if not missing:
            return (
                "The retrieved analytics context "
                "contains demand, unavailable-search, "
                "and branch inventory data. No "
                "obvious required field is missing "
                "from those retrieved groups."
            )

        return (
            "The current Analytics Agent context "
            "is missing or does not directly include: "
            + "; ".join(
                missing
            )
            + ". I will not infer those values "
            "from unrelated rows."
        )

    def _generic_data_summary(
        self,
        context: dict[str, Any],
    ) -> str:
        demand = (
            context.get(
                "unmet_demand"
            )
            if isinstance(
                context.get(
                    "unmet_demand"
                ),
                dict,
            )
            else {}
        )

        inventory = (
            context.get(
                "inventory"
            )
            if isinstance(
                context.get(
                    "inventory"
                ),
                dict,
            )
            else {}
        )

        demand_groups = {
            key: len(
                self._as_rows(
                    value
                )
            )
            for key, value
            in demand.items()
            if self._as_rows(
                value
            )
        }

        branch_count = len(
            self._as_rows(
                inventory.get(
                    "branches",
                    [],
                )
            )
        )

        parts: list[str] = []

        if demand_groups:
            group_text = ", ".join(
                (
                    f"{name.replace('_', ' ')}: "
                    f"{count}"
                )
                for name, count
                in sorted(
                    demand_groups.items()
                )
            )

            parts.append(
                "Demand analytics retrieved "
                f"({group_text})."
            )

        if branch_count:
            parts.append(
                "Branch inventory summary "
                f"contains {branch_count} branch"
                f"{'' if branch_count == 1 else 'es'}."
            )

        if not parts:
            return (
                "Analytics records were retrieved, "
                "but the current data shape does "
                "not provide enough structured "
                "information to answer that "
                "question reliably."
            )

        return (
            "I could not generate a "
            "natural-language model summary, "
            "but the retrieved data is available. "
            + " ".join(
                parts
            )
        )

    def _summarize_with_ollama(
        self,
        *,
        question: str,
        context: dict[str, Any],
    ) -> str | None:
        prompt = (
            "You are Retailigent's staff analytics "
            "assistant. Answer the staff question "
            "using ONLY the supplied JSON data. "
            "Do not invent counts, product names, "
            "sizes, branch names, trends, or causes. "
            "If the supplied data does not answer "
            "the question, state exactly what "
            "information is missing. Distinguish "
            "an empty result from a true value of "
            "zero. Keep the answer concise and "
            "actionable for retail staff.\n\n"
            f"Staff question:\n{question}\n\n"
            "Retrieved analytics JSON:\n"
            f"{json.dumps(
                context,
                default=str,
                ensure_ascii=True,
            )}"
        )

        try:
            response = httpx.post(
                (
                    settings
                    .ollama_url
                    .rstrip("/")
                    + "/api/generate"
                ),
                json={
                    "model":
                        settings
                        .ollama_llm_model,
                    "prompt":
                        prompt,
                    "stream":
                        False,
                    "think":
                        False,
                    "keep_alive":
                        settings
                        .ollama_keep_alive,
                    "options": {
                        "temperature": 0,
                        "num_predict": 300,
                    },
                },
                timeout=httpx.Timeout(
                    settings
                    .ollama_llm_timeout_seconds,
                ),
            )

            response.raise_for_status()

            payload = response.json()

            result = _clean_text(
                payload.get(
                    "response"
                )
                if isinstance(
                    payload,
                    dict,
                )
                else ""
            )

            if result:
                return result

        except (
            httpx.HTTPError,
            ValueError,
            TypeError,
            KeyError,
        ):
            logger.warning(
                (
                    "Analytics Ollama summary "
                    "failed; using deterministic "
                    "fallback."
                ),
                exc_info=True,
            )

        return None


analytics_agent = AnalyticsAgent()