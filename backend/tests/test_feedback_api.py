from uuid import UUID

from fastapi.testclient import TestClient

import app.api.v1.feedback as feedback_module
from app.core.auth import (
    get_current_user_id,
    get_current_user_role,
    require_customer,
)
from app.main import app
from app.services.feedback_service import FeedbackServiceError


def _customer_id():
    return "customer-1"


def _customer_role():
    return "customer"


def _staff_role():
    return "staff"


def _install_customer_auth():
    app.dependency_overrides[get_current_user_id] = _customer_id
    app.dependency_overrides[require_customer] = _customer_role
    app.dependency_overrides[get_current_user_role] = _customer_role


def _install_staff_auth():
    app.dependency_overrides[get_current_user_role] = _staff_role


def _clear_auth():
    app.dependency_overrides.clear()


def test_customer_can_submit_feedback(monkeypatch):
    _install_customer_auth()
    called = {}

    def fake_submit_feedback(**kwargs):
        called.update(kwargs)
        return {
            "id": "feedback-1",
            "ai_category": "service",
            "ai_sentiment": "negative",
            "needs_review": True,
        }

    monkeypatch.setattr(
        feedback_module.feedback_service,
        "submit_feedback",
        fake_submit_feedback,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/feedback",
                json={
                    "feedback_type": "general",
                    "rating": 1,
                    "message": "Nobody helped me.",
                },
            )

        assert response.status_code == 201
        assert response.json()["needs_review"] is True
        assert called["customer_id"] == "customer-1"
        assert called["message"] == "Nobody helped me."
    finally:
        _clear_auth()


def test_customer_cannot_access_review_queue(monkeypatch):
    _install_customer_auth()
    called = {"queue": False}

    def fake_queue(**kwargs):
        called["queue"] = True
        return []

    monkeypatch.setattr(
        feedback_module.feedback_service,
        "list_feedback_review_queue",
        fake_queue,
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/feedback/review-queue")

        assert response.status_code == 403
        assert called["queue"] is False
    finally:
        _clear_auth()


def test_staff_can_access_review_queue(monkeypatch):
    _install_customer_auth()
    _install_staff_auth()
    monkeypatch.setattr(
        feedback_module.feedback_service,
        "list_feedback_review_queue",
        lambda **kwargs: [
            {"id": "feedback-1", "needs_review": True}
        ],
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/feedback/review-queue")

        assert response.status_code == 200
        assert response.json()["count"] == 1
    finally:
        _clear_auth()


def test_customer_cannot_correct_feedback(monkeypatch):
    _install_customer_auth()
    called = {"correct": False}

    def fake_correct(**kwargs):
        called["correct"] = True
        return {}

    monkeypatch.setattr(
        feedback_module.feedback_service,
        "correct_feedback_classification",
        fake_correct,
    )

    try:
        with TestClient(app) as client:
            response = client.patch(
                "/api/v1/feedback/"
                "00000000-0000-0000-0000-000000000001/classification",
                json={
                    "staff_category": "service",
                    "staff_sentiment": "negative",
                },
            )

        assert response.status_code == 403
        assert called["correct"] is False
    finally:
        _clear_auth()


def test_staff_can_correct_feedback(monkeypatch):
    _install_customer_auth()
    _install_staff_auth()
    monkeypatch.setattr(
        feedback_module.feedback_service,
        "correct_feedback_classification",
        lambda **kwargs: {
            "id": kwargs["feedback_id"],
            "staff_category": kwargs["staff_category"],
            "staff_sentiment": kwargs["staff_sentiment"],
            "staff_corrected": True,
            "needs_review": False,
        },
    )

    try:
        with TestClient(app) as client:
            response = client.patch(
                "/api/v1/feedback/"
                "00000000-0000-0000-0000-000000000001/classification",
                json={
                    "staff_category": "service",
                    "staff_sentiment": "negative",
                },
            )

        assert response.status_code == 200
        assert response.json()["staff_corrected"] is True
        assert response.json()["needs_review"] is False
    finally:
        _clear_auth()


def test_invalid_feedback_payload_is_rejected():
    _install_customer_auth()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/feedback",
                json={
                    "feedback_type": "unknown",
                    "rating": 7,
                    "message": "",
                },
            )

        assert response.status_code == 422
    finally:
        _clear_auth()
