from __future__ import annotations

import logging
from typing import Any

from app.agents.feedback_classifier_agent import (
    feedback_classifier_agent,
)
from app.core.supabase_client import supabase_admin

logger = logging.getLogger(__name__)


class FeedbackServiceError(Exception):
    """Raised when feedback cannot be safely persisted or retrieved."""


def submit_feedback(
    *,
    customer_id: str,
    feedback_type: str,
    rating: int | None,
    message: str,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    clean_message = message.strip()
    if not clean_message:
        raise ValueError("Feedback message cannot be empty.")

    if conversation_id:
        ownership = (
            supabase_admin.table("conversations")
            .select("id")
            .eq("id", conversation_id)
            .eq("customer_id", customer_id)
            .limit(1)
            .execute()
        )
        if not ownership.data:
            raise ValueError(
                "The conversation was not found for this customer."
            )

    classification, used_ai = feedback_classifier_agent.classify(
        clean_message,
        rating=rating,
        feedback_type=feedback_type,
    )

    payload = {
        "customer_id": customer_id,
        "conversation_id": conversation_id,
        "feedback_type": feedback_type,
        "rating": rating,
        "message": clean_message,
        "ai_category": classification.category,
        "ai_sentiment": classification.sentiment,
        "classification_source": "ai" if used_ai else "fallback",
        "needs_review": classification.needs_review,
    }

    try:
        response = (
            supabase_admin.table("feedback")
            .insert(payload)
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise FeedbackServiceError(
                "Feedback was not returned after submission."
            )
        return rows[0]
    except FeedbackServiceError:
        raise
    except Exception as exc:
        logger.exception("Could not persist customer feedback.")
        raise FeedbackServiceError(
            "Feedback could not be saved."
        ) from exc


def list_customer_feedback(
    customer_id: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 100))
    try:
        response = (
            supabase_admin.table("feedback")
            .select("*")
            .eq("customer_id", customer_id)
            .order("created_at", desc=True)
            .limit(safe_limit)
            .execute()
        )
        return response.data or []
    except Exception as exc:
        logger.exception("Could not retrieve customer feedback.")
        raise FeedbackServiceError(
            "Feedback could not be loaded."
        ) from exc


def list_feedback_review_queue(
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 200))
    try:
        response = (
            supabase_admin.table("feedback")
            .select("*")
            .eq("needs_review", True)
            .order("created_at", desc=True)
            .limit(safe_limit)
            .execute()
        )
        return response.data or []
    except Exception as exc:
        logger.exception("Could not retrieve feedback review queue.")
        raise FeedbackServiceError(
            "The feedback review queue could not be loaded."
        ) from exc


def correct_feedback_classification(
    *,
    feedback_id: str,
    staff_category: str,
    staff_sentiment: str,
) -> dict[str, Any]:
    try:
        response = (
            supabase_admin.table("feedback")
            .update({
                "staff_category": staff_category,
                "staff_sentiment": staff_sentiment,
                "staff_corrected": True,
                "needs_review": False,
            })
            .eq("id", feedback_id)
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise LookupError("Feedback record not found.")
        return rows[0]
    except (LookupError, ValueError):
        raise
    except Exception as exc:
        logger.exception("Could not correct feedback classification.")
        raise FeedbackServiceError(
            "The feedback classification could not be updated."
        ) from exc
