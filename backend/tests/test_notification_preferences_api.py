from fastapi.testclient import TestClient

import app.api.v1.notifications as notifications_module
from app.core.auth import (
    get_current_user_id,
    get_current_user_role,
    get_current_user_roles,
    require_customer,
)
from app.main import app


def _customer_id():
    return "customer-1"


def _customer_role():
    return "customer"


def _install_customer_auth():
    app.dependency_overrides[get_current_user_id] = _customer_id
    app.dependency_overrides[require_customer] = _customer_role
    app.dependency_overrides[get_current_user_roles] = lambda: ["customer"]


def _clear_auth():
    app.dependency_overrides.clear()


def test_customer_can_read_email_notification_preference(monkeypatch):
    _install_customer_auth()
    calls = []

    def fake_get(customer_id):
        calls.append(customer_id)
        return {"allow_email_notifications": True}

    monkeypatch.setattr(
        notifications_module,
        "get_email_notification_preference",
        fake_get,
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/notifications/preferences")

        assert response.status_code == 200
        assert response.json() == {"allow_email_notifications": True}
        assert calls == ["customer-1"]
    finally:
        _clear_auth()


def test_missing_preference_defaults_to_opted_out(monkeypatch):
    _install_customer_auth()
    monkeypatch.setattr(
        notifications_module,
        "get_email_notification_preference",
        lambda customer_id: {"allow_email_notifications": False},
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/notifications/preferences")

        assert response.status_code == 200
        assert response.json()["allow_email_notifications"] is False
    finally:
        _clear_auth()


def test_customer_can_update_own_email_preference(monkeypatch):
    _install_customer_auth()
    calls = []

    def fake_set(customer_id, enabled):
        calls.append((customer_id, enabled))
        return {"allow_email_notifications": enabled}

    monkeypatch.setattr(
        notifications_module,
        "set_email_notification_preference",
        fake_set,
    )
    try:
        with TestClient(app) as client:
            response = client.patch(
                "/api/v1/notifications/preferences",
                json={"allow_email_notifications": True},
            )

        assert response.status_code == 200
        assert response.json()["allow_email_notifications"] is True
        assert calls == [("customer-1", True)]
    finally:
        _clear_auth()


def test_invalid_preference_payload_is_rejected():
    _install_customer_auth()
    try:
        with TestClient(app) as client:
            response = client.patch(
                "/api/v1/notifications/preferences",
                json={"allow_email_notifications": "yes"},
            )

        assert response.status_code == 422
    finally:
        _clear_auth()


def test_non_customer_cannot_update_email_preference(monkeypatch):
    app.dependency_overrides[get_current_user_id] = _customer_id
    app.dependency_overrides[get_current_user_role] = lambda: "staff"
    app.dependency_overrides[get_current_user_roles] = lambda: ["staff"]
    calls = []
    monkeypatch.setattr(
        notifications_module,
        "set_email_notification_preference",
        lambda *args: calls.append(args),
    )
    try:
        with TestClient(app) as client:
            response = client.patch(
                "/api/v1/notifications/preferences",
                json={"allow_email_notifications": True},
            )

        assert response.status_code == 403
        assert calls == []
    finally:
        _clear_auth()
