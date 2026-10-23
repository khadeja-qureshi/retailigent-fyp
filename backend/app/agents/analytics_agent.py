from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings
from app.services import analytics_service
from app.services.analytics_service import AnalyticsServiceError

logger = logging.getLogger(__name__)

MAX_QUESTION_LENGTH = 1000
MAX_CONTEXT_ROWS = 20


class AnalyticsAgent:
    """Answer staff questions using retrieved Retailigent analytics."""

    agent_key = "analytics"

    def answer(self, question: str) -> dict[str, Any]:
        question = question.strip()

        if not question:
            raise ValueError("Please enter a question.")

        if len(question) > MAX_QUESTION_LENGTH:
            raise ValueError(
                f"Questions must be {MAX_QUESTION_LENGTH} characters or fewer."
            )

        try:
            demand = analytics_service.get_demand_analytics(
                limit=MAX_CONTEXT_ROWS,
            )
            inventory = analytics_service.get_inventory_analytics(
                limit=MAX_CONTEXT_ROWS,
            )
        except AnalyticsServiceError:
            logger.exception("Could not retrieve staff analytics.")
            return {
                "answer": (
                    "I couldn't retrieve the analytics data right now. "
                    "Please try again shortly."
                ),
                "data_status": "unavailable",
                "sources": [],
            }

        context = {
            "unmet_demand": demand,
            "inventory": inventory,
        }

        sources = [
            {
                "name": "unmet_demand",
                "record_count": sum(
                    len(rows)
                    for rows in demand.values()
                ),
            },
            {
                "name": "branch_inventory_summary",
                "record_count": len(inventory.get("branches", [])),
            },
        ]

        has_records = any(
            isinstance(rows, list) and rows
            for group in context.values()
            if isinstance(group, dict)
            for rows in group.values()
        )

        if not has_records:
            return {
                "answer": (
                    "The analytics views returned no records for this query "
                    "context. This does not establish that demand or inventory "
                    "is zero; check whether the underlying data has been recorded."
                ),
                "data_status": "empty",
                "sources": sources,
            }

        answer = self._summarize(question, context)

        return {
            "answer": answer,
            "data_status": "available",
            "sources": sources,
        }

    def _summarize(
        self,
        question: str,
        context: dict[str, Any],
    ) -> str:
        prompt = (
            "You are Retailigent's staff analytics assistant. "
            "Answer the staff question using ONLY the supplied JSON data. "
            "Do not invent counts, product names, sizes, branch names, trends, "
            "or causes. If the supplied data does not answer the question, "
            "say what information is missing. Distinguish empty results from "
            "zero demand. Keep the answer concise.\n\n"
            f"Staff question:\n{question}\n\n"
            "Retrieved analytics JSON:\n"
            f"{json.dumps(context, default=str, ensure_ascii=True)}"
        )

        try:
            response = httpx.post(
                settings.ollama_url.rstrip("/") + "/api/generate",
                json={
                    "model": settings.ollama_llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "think": False,
                    "keep_alive": settings.ollama_keep_alive,
                    "options": {
                        "temperature": 0,
                        "num_predict": 300,
                    },
                },
                timeout=httpx.Timeout(
                    settings.ollama_llm_timeout_seconds,
                ),
            )
            response.raise_for_status()
            result = str(response.json().get("response", "")).strip()

            if result:
                return result

        except (
            httpx.HTTPError,
            ValueError,
            TypeError,
            KeyError,
        ):
            logger.warning(
                "Analytics Ollama summary failed.",
                exc_info=True,
            )

        return (
            "I retrieved analytics records, but couldn't generate a summary. "
            "Please review the demand and inventory analytics tables."
        )


analytics_agent = AnalyticsAgent()
