from unittest.mock import MagicMock

import pytest

from app.agents import feedback_classifier_agent as classifier_module
from app.services import feedback_service


@pytest.fixture
def db(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(feedback_service, "supabase_admin", client)
    return client


@pytest.fixture
def classification(monkeypatch):
    result = classifier_module.FeedbackClassification(
        category="service",
        sentiment="negative",
        needs_review=True,
        rationale="Customer reports a poor support experience.",
    )
    monkeypatch.setattr(
        feedback_service.feedback_classifier_agent,
        "classify",
        lambda *args, **kwargs: (result, True),
    )
    return result


def test_submit_feedback_persists_ai_classification(
    db, classification
):
    row = {
        "id": "feedback-1",
        "customer_id": "customer-1",
        "ai_category": "service",
        "ai_sentiment": "negative",
        "classification_source": "ai",
        "needs_review": True,
    }
    db.table.return_value.insert.return_value.execute.return_value.data = [
        row
    ]

    result = feedback_service.submit_feedback(
        customer_id="customer-1",
        feedback_type="general",
        rating=1,
        message="  Nobody helped me.  ",
    )

    assert result == row
    db.table.assert_called_once_with("feedback")
    payload = db.table.return_value.insert.call_args.args[0]
    assert payload["message"] == "Nobody helped me."
    assert payload["classification_source"] == "ai"
    assert payload["needs_review"] is True
    assert payload["ai_category"] == classification.category


def test_submit_feedback_marks_fallback_source(db, monkeypatch):
    result = classifier_module.FeedbackClassification(
        category="delivery",
        sentiment="negative",
        needs_review=True,
        rationale="Rule-based fallback.",
    )
    monkeypatch.setattr(
        feedback_service.feedback_classifier_agent,
        "classify",
        lambda *args, **kwargs: (result, False),
    )
    db.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "feedback-2"}
    ]

    feedback_service.submit_feedback(
        customer_id="customer-1",
        feedback_type="delivery",
        rating=2,
        message="My parcel is late.",
    )

    payload = db.table.return_value.insert.call_args.args[0]
    assert payload["classification_source"] == "fallback"
    assert payload["needs_review"] is True


def test_submit_feedback_rejects_blank_message(db):
    with pytest.raises(ValueError, match="cannot be empty"):
        feedback_service.submit_feedback(
            customer_id="customer-1",
            feedback_type="general",
            rating=None,
            message="   ",
        )

    db.table.assert_not_called()


def test_submit_feedback_checks_conversation_ownership(
    db, classification
):
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

    with pytest.raises(ValueError, match="conversation was not found"):
        feedback_service.submit_feedback(
            customer_id="customer-1",
            feedback_type="general",
            rating=3,
            message="Some feedback",
            conversation_id="conversation-other",
        )

    assert db.table.call_count == 1
    db.table.assert_called_with("conversations")


def test_submit_feedback_fails_if_insert_returns_no_row(
    db, classification
):
    db.table.return_value.insert.return_value.execute.return_value.data = []

    with pytest.raises(
        feedback_service.FeedbackServiceError,
        match="not returned",
    ):
        feedback_service.submit_feedback(
            customer_id="customer-1",
            feedback_type="general",
            rating=4,
            message="Thanks.",
        )


def test_review_queue_filters_to_items_needing_review(db):
    db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"id": "feedback-3", "needs_review": True}
    ]

    rows = feedback_service.list_feedback_review_queue()

    assert len(rows) == 1
    assert rows[0]["needs_review"] is True
    db.table.assert_called_once_with("feedback")
    db.table.return_value.select.return_value.eq.assert_called_once_with(
        "needs_review", True
    )


def test_staff_correction_marks_record_reviewed(db):
    expected = {
        "id": "feedback-4",
        "staff_category": "service",
        "staff_sentiment": "negative",
        "staff_corrected": True,
        "needs_review": False,
    }
    db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        expected
    ]

    result = feedback_service.correct_feedback_classification(
        feedback_id="feedback-4",
        staff_category="service",
        staff_sentiment="negative",
    )

    assert result == expected
    payload = db.table.return_value.update.call_args.args[0]
    assert payload["staff_corrected"] is True
    assert payload["needs_review"] is False


def test_staff_correction_raises_if_feedback_not_found(db):
    db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []

    with pytest.raises(LookupError, match="not found"):
        feedback_service.correct_feedback_classification(
            feedback_id="missing",
            staff_category="general",
            staff_sentiment="neutral",
        )
