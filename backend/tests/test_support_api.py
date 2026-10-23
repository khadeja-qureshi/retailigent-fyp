from fastapi.testclient import TestClient

import app.api.v1.support as support_module
from app.core.auth import get_current_user_id, get_current_user_role, get_current_user_roles
from app.main import app
from app.services.support_admin_service import SupportAdminServiceError


TICKET_ID = "00000000-0000-0000-0000-000000000001"


def _install_customer_auth():
    app.dependency_overrides[get_current_user_role] = lambda: "customer"
    app.dependency_overrides[get_current_user_roles] = lambda: ["customer"]
    app.dependency_overrides[get_current_user_id] = lambda: "customer-1"


def _install_staff_auth():
    app.dependency_overrides[get_current_user_role] = lambda: "staff"
    app.dependency_overrides[get_current_user_roles] = lambda: ["staff"]
    app.dependency_overrides[get_current_user_id] = lambda: "staff-1"


def _clear_auth():
    app.dependency_overrides.clear()


def test_customer_cannot_access_support_queue(monkeypatch):
    _install_customer_auth()
    called = {"queue": False}

    def fake_list(**kwargs):
        called["queue"] = True
        return []

    monkeypatch.setattr(
        support_module.support_admin_service,
        "list_support_tickets",
        fake_list,
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/support/tickets")

        assert response.status_code == 403
        assert called["queue"] is False
    finally:
        _clear_auth()


def test_staff_can_access_support_queue(monkeypatch):
    _install_staff_auth()
    monkeypatch.setattr(
        support_module.support_admin_service,
        "list_support_tickets",
        lambda **kwargs: [{"id": TICKET_ID, "priority": "urgent"}],
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/support/tickets?status=open")

        assert response.status_code == 200
        assert response.json()["count"] == 1
        assert response.json()["tickets"][0]["priority"] == "urgent"
    finally:
        _clear_auth()


def test_staff_queue_rejects_invalid_filters():
    _install_staff_auth()

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/support/tickets?priority=critical")

        assert response.status_code == 422
    finally:
        _clear_auth()


def test_staff_can_read_ticket_detail(monkeypatch):
    _install_staff_auth()
    monkeypatch.setattr(
        support_module.support_admin_service,
        "get_support_ticket",
        lambda ticket_id: {"id": ticket_id, "subject": "Order delay"},
    )

    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/support/tickets/{TICKET_ID}")

        assert response.status_code == 200
        assert response.json()["subject"] == "Order delay"
    finally:
        _clear_auth()


def test_missing_ticket_returns_404(monkeypatch):
    _install_staff_auth()
    monkeypatch.setattr(
        support_module.support_admin_service,
        "get_support_ticket",
        lambda ticket_id: None,
    )

    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/support/tickets/{TICKET_ID}")

        assert response.status_code == 404
    finally:
        _clear_auth()


def test_staff_can_update_ticket(monkeypatch):
    _install_staff_auth()
    called = {}

    def fake_update(**kwargs):
        called.update(kwargs)
        return {
            "id": kwargs["ticket_id"],
            "status": kwargs["status"],
            "priority": kwargs["priority"],
        }

    monkeypatch.setattr(
        support_module.support_admin_service,
        "update_support_ticket",
        fake_update,
    )

    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/api/v1/support/tickets/{TICKET_ID}",
                json={"status": "in_progress", "priority": "high"},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "in_progress"
        assert called["ticket_id"] == TICKET_ID
        assert called["update_assignment"] is False
    finally:
        _clear_auth()


def test_staff_reply_uses_authenticated_staff_id(monkeypatch):
    _install_staff_auth()
    monkeypatch.setattr(
        support_module.support_admin_service,
        "get_support_ticket",
        lambda ticket_id: {"id": ticket_id},
    )
    called = {}

    def fake_reply(**kwargs):
        called.update(kwargs)
        return {
            "id": "message-1",
            "sender_id": kwargs["staff_id"],
            "sender_type": "staff",
            "message": kwargs["message"],
        }

    monkeypatch.setattr(
        support_module.support_admin_service,
        "add_staff_ticket_message",
        fake_reply,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/support/tickets/{TICKET_ID}/messages",
                json={"message": "We are investigating."},
            )

        assert response.status_code == 201
        assert called["staff_id"] == "staff-1"
        assert response.json()["sender_type"] == "staff"
    finally:
        _clear_auth()


def test_staff_reply_rejects_blank_message():
    _install_staff_auth()

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/support/tickets/{TICKET_ID}/messages",
                json={"message": "   "},
            )

        assert response.status_code == 422
    finally:
        _clear_auth()


def test_customer_cannot_send_staff_reply(monkeypatch):
    _install_customer_auth()
    called = {"ticket": False}

    def fake_get_ticket(ticket_id):
        called["ticket"] = True
        return {"id": ticket_id}

    monkeypatch.setattr(
        support_module.support_admin_service,
        "get_support_ticket",
        fake_get_ticket,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/support/tickets/{TICKET_ID}/messages",
                json={"message": "A reply"},
            )

        assert response.status_code == 403
        assert called["ticket"] is False
    finally:
        _clear_auth()


def test_support_service_error_returns_500(monkeypatch):
    _install_staff_auth()

    def fail(**kwargs):
        raise SupportAdminServiceError("queue unavailable")

    monkeypatch.setattr(
        support_module.support_admin_service,
        "list_support_tickets",
        fail,
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/support/tickets")

        assert response.status_code == 500
        assert response.json()["detail"] == "queue unavailable"
    finally:
        _clear_auth()

def test_staff_role_is_accepted_when_user_has_multiple_roles():
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
    from app.core.auth import get_current_user_roles, require_staff

    test_app = FastAPI()

    @test_app.get("/staff-only")
    def staff_only(role=Depends(require_staff)):
        return {"role": role}

    test_app.dependency_overrides[get_current_user_roles] = (
        lambda: ["customer", "staff"]
    )

    response = TestClient(test_app).get("/staff-only")

    assert response.status_code == 200
    assert response.json()["role"] == "staff"
