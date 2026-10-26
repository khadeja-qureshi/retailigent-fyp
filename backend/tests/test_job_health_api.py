from fastapi.testclient import TestClient

from app.main import app
from app.workers import job_state


def test_jobs_health_reports_registered_workers(monkeypatch):
    monkeypatch.setattr(
        "app.main.get_job_states",
        lambda expected_intervals, stale_multiplier: {
            name: {
                "job_name": name,
                "status": "healthy",
                "success_count": 1,
                "failure_count": 0,
                "last_error": None,
            }
            for name in expected_intervals
        },
    )

    with TestClient(app) as client:
        response = client.get("/health/jobs")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "healthy"

    expected_jobs = {
        "smart_cart_auto_buy",
        "notification_delivery",
        "promotion_activation",
        "reservation_expiry",
    }

    assert expected_jobs.issubset(payload["jobs"].keys())

    for name in expected_jobs:
        assert payload["jobs"][name]["enabled"] is True
        assert payload["jobs"][name]["status"] == "healthy"


def test_jobs_health_reports_degraded_enabled_worker(monkeypatch):
    def fake_job_states(expected_intervals, stale_multiplier):
        return {
            name: {
                "job_name": name,
                "status": (
                    "failing"
                    if name == "notification_delivery"
                    else "healthy"
                ),
                "success_count": 0,
                "failure_count": (
                    1
                    if name == "notification_delivery"
                    else 0
                ),
                "last_error": (
                    "Simulated worker failure"
                    if name == "notification_delivery"
                    else None
                ),
            }
            for name in expected_intervals
        }

    monkeypatch.setattr(
        "app.main.get_job_states",
        fake_job_states,
    )

    with TestClient(app) as client:
        response = client.get("/health/jobs")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "degraded"
    assert (
        payload["jobs"]["notification_delivery"]["status"]
        == "failing"
    )


def test_jobs_health_marks_disabled_worker(monkeypatch):
    monkeypatch.setattr(
        "app.main.get_job_states",
        lambda expected_intervals, stale_multiplier: {
            name: {
                "job_name": name,
                "status": "starting",
                "success_count": 0,
                "failure_count": 0,
                "last_error": None,
            }
            for name in expected_intervals
        },
    )

    monkeypatch.setattr(
        "app.main.settings.notification_worker_enabled",
        False,
    )

    with TestClient(app) as client:
        response = client.get("/health/jobs")

    assert response.status_code == 200
    payload = response.json()

    assert payload["jobs"]["notification_delivery"]["enabled"] is False
    assert payload["jobs"]["notification_delivery"]["status"] == "disabled"
    assert payload["status"] == "healthy"