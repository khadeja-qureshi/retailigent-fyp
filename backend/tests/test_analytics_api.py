from fastapi.testclient import TestClient
import pytest
import app.api.v1.analytics as analytics_module
from app.core.auth import (
    get_current_user_role,
    get_current_user_roles,
    require_customer,
)
from app.main import app
from app.services.analytics_service import AnalyticsServiceError


def _customer_role():
    return "customer"


def _staff_role():
    return "staff"


def _install_customer_auth():
    app.dependency_overrides[require_customer] = _customer_role
    app.dependency_overrides[get_current_user_role] = _customer_role
    app.dependency_overrides[get_current_user_roles] = lambda: ["customer"]


def _install_staff_auth():
    app.dependency_overrides[get_current_user_role] = _staff_role
    app.dependency_overrides[get_current_user_roles] = lambda: ["staff"]


def _clear_auth():
    app.dependency_overrides.clear()


def test_staff_can_access_demand_analytics(monkeypatch):
    _install_staff_auth()
    monkeypatch.setattr(
        analytics_module.analytics_service,
        "get_demand_analytics",
        lambda **kwargs: {
            "high_interest_low_availability": [{"product_id": "p1"}],
            "unavailable_searches": [{"signal_count": 3}],
            "product_demand_availability": [],
        },
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/analytics/demand?limit=20")

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == {
            "high_interest_low_availability": 1,
            "unavailable_searches": 1,
            "product_demand_availability": 0,
        }
    finally:
        _clear_auth()


def test_staff_can_access_inventory_analytics(monkeypatch):
    _install_staff_auth()
    monkeypatch.setattr(
        analytics_module.analytics_service,
        "get_inventory_analytics",
        lambda **kwargs: {
            "branches": [{"total_variants": 10}],
        },
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/analytics/inventory")

        assert response.status_code == 200
        assert response.json()["branches"] == [{"total_variants": 10}]
        assert response.json()["count"]["branches"] == 1
    finally:
        _clear_auth()


def test_customer_cannot_access_demand_analytics(monkeypatch):
    _install_customer_auth()
    called = {"value": False}

    def fake_analytics(**kwargs):
        called["value"] = True
        return {}

    monkeypatch.setattr(
        analytics_module.analytics_service,
        "get_demand_analytics",
        fake_analytics,
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/analytics/demand")

        assert response.status_code == 403
        assert called["value"] is False
    finally:
        _clear_auth()


def test_customer_cannot_access_inventory_analytics(monkeypatch):
    _install_customer_auth()
    called = {"value": False}

    def fake_analytics(**kwargs):
        called["value"] = True
        return {}

    monkeypatch.setattr(
        analytics_module.analytics_service,
        "get_inventory_analytics",
        fake_analytics,
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/analytics/inventory")

        assert response.status_code == 403
        assert called["value"] is False
    finally:
        _clear_auth()


def test_demand_analytics_service_error_returns_500(monkeypatch):
    _install_staff_auth()
    monkeypatch.setattr(
        analytics_module.analytics_service,
        "get_demand_analytics",
        lambda **kwargs: (_ for _ in ()).throw(
            AnalyticsServiceError("Analytics data could not be loaded.")
        ),
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/analytics/demand")

        assert response.status_code == 500
        assert response.json()["detail"] == (
            "Analytics data could not be loaded."
        )
    finally:
        _clear_auth()


def test_invalid_analytics_limit_is_rejected():
    _install_staff_auth()

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/analytics/demand?limit=0")

        assert response.status_code == 422
    finally:
        _clear_auth()

def test_staff_can_ask_analytics(monkeypatch):
    _install_staff_auth()
    monkeypatch.setattr(
        analytics_module.analytics_agent,
        "answer",
        lambda question: {
            "answer": f"Analytics answer for: {question}",
            "data_status": "available",
            "sources": [],
        },
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/analytics/ask",
                json={"question": "Which variants are unavailable?"},
            )

        assert response.status_code == 200
        assert response.json()["data_status"] == "available"
        assert "Which variants are unavailable?" in response.json()["answer"]
    finally:
        _clear_auth()


def test_customer_cannot_ask_analytics(monkeypatch):
    _install_customer_auth()
    called = {"value": False}

    def fake_answer(question):
        called["value"] = True
        return {"answer": "Should not run"}

    monkeypatch.setattr(
        analytics_module.analytics_agent,
        "answer",
        fake_answer,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/analytics/ask",
                json={"question": "Show unmet demand"},
            )

        assert response.status_code == 403
        assert called["value"] is False
    finally:
        _clear_auth()


@pytest.mark.parametrize(
    "payload",
    [
        {"question": ""},
        {"question": "   "},
        {"question": "x" * 1001},
        {},
    ],
)
def test_invalid_analytics_question_is_rejected(payload):
    _install_staff_auth()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/analytics/ask",
                json=payload,
            )

        assert response.status_code == 422
    finally:
        _clear_auth()


def test_analytics_agent_value_error_returns_422(monkeypatch):
    _install_staff_auth()

    def reject_question(question):
        raise ValueError("Please enter a question.")

    monkeypatch.setattr(
        analytics_module.analytics_agent,
        "answer",
        reject_question,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/analytics/ask",
                json={"question": "Demand"},
            )

        assert response.status_code == 422
        assert response.json()["detail"] == "Please enter a question."
    finally:
        _clear_auth()
