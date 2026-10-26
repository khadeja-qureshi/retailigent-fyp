import json
import logging
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app.api.v1.jobs as jobs_module
from app.core.auth import get_current_user_roles
from app.core.logging_config import JsonFormatter, configure_logging
from app.main import app
from app.services import job_service
from app.services.job_service import JobServiceError
from app.workers.jobs import build_jobs, build_scheduler
from app.workers.scheduler import Job, Scheduler


@pytest.fixture(autouse=True)
def _reset():
    yield
    app.dependency_overrides.clear()
    app.state.scheduler = None


def _as(roles):
    app.dependency_overrides[get_current_user_roles] = lambda: roles


def _settings(**overrides):
    base = dict(
        scheduler_enabled=True,
        promotion_activation_interval_seconds=60,
        reservation_expiry_interval_seconds=30,
        notification_worker_enabled=True,
        notification_worker_interval_seconds=5,
        smart_cart_worker_enabled=True,
        smart_cart_worker_interval_seconds=2,
        job_heartbeat_persist_seconds=15,
    )
    base.update(overrides)
    return type("S", (), base)()


# --------------------------------------------------------- /health/jobs

def test_health_jobs_is_public_and_reports_last_run_times():
    scheduler = Scheduler([Job("activate_promotions", 60, lambda: {"activated": 0})])
    scheduler.running = True
    scheduler.started_at = scheduler.started_at or __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    )
    scheduler.run_job_blocking(scheduler.jobs["activate_promotions"])

    with TestClient(app) as client:
        app.state.scheduler = scheduler           # no auth header at all
        response = client.get("/health/jobs")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    job = body["jobs"][0]
    assert job["name"] == "activate_promotions"
    assert job["last_success_at"] is not None
    assert job["last_started_at"] is not None
    assert "last_error" not in job


def test_health_jobs_never_leaks_error_text():
    def boom():
        raise RuntimeError("secret connection string")

    scheduler = Scheduler([Job("j", 60, boom)])
    scheduler.running = True
    scheduler.started_at = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    )
    scheduler.run_job_blocking(scheduler.jobs["j"])

    with TestClient(app) as client:
        app.state.scheduler = scheduler
        response = client.get("/health/jobs")

    assert "secret" not in response.text


def test_health_jobs_when_scheduler_is_disabled():
    with TestClient(app) as client:
        app.state.scheduler = None
        response = client.get("/health/jobs")

    assert response.status_code == 200
    assert response.json() == {
        "status": "disabled",
        "scheduler_started_at": None,
        "jobs": [],
    }


# ------------------------------------------------- admin jobs endpoints

@pytest.mark.parametrize("roles", [["customer"], ["staff"], ["manager"]])
def test_admin_jobs_endpoints_forbid_non_admins(monkeypatch, roles):
    _as(roles)
    called = []
    monkeypatch.setattr(
        jobs_module.job_service, "get_job_overview", lambda: called.append(1) or {}
    )
    monkeypatch.setattr(
        jobs_module.job_service, "requeue_dead_letters", lambda ids: called.append(2) or 0
    )

    with TestClient(app) as client:
        app.state.scheduler = None
        assert client.get("/api/v1/admin/jobs").status_code == 403
        assert (
            client.post(
                "/api/v1/admin/jobs/notification-dead-letters/requeue", json={}
            ).status_code
            == 403
        )

    assert called == []


def test_admin_can_see_jobs_backlog_and_dead_letters(monkeypatch):
    _as(["admin"])
    monkeypatch.setattr(
        jobs_module.job_service,
        "get_job_overview",
        lambda: {
            "jobs": [{"job_name": "notification_delivery", "stale": False}],
            "notification_backlog": {
                "pending": 1, "retrying": 2, "processing": 0, "dead_lettered": 3,
            },
            "notification_dead_letters": [{"id": "d1", "error_message": "no address"}],
        },
    )

    with TestClient(app) as client:
        app.state.scheduler = None
        response = client.get("/api/v1/admin/jobs")

    assert response.status_code == 200
    body = response.json()
    assert body["notification_backlog"]["dead_lettered"] == 3
    assert body["notification_dead_letters"][0]["id"] == "d1"
    assert body["scheduler"]["status"] == "disabled"


def test_admin_requeue_passes_ids_and_returns_count(monkeypatch):
    _as(["admin"])
    seen = []
    monkeypatch.setattr(
        jobs_module.job_service,
        "requeue_dead_letters",
        lambda ids: seen.append(ids) or 2,
    )

    with TestClient(app) as client:
        app.state.scheduler = None
        selected = client.post(
            "/api/v1/admin/jobs/notification-dead-letters/requeue",
            json={"delivery_ids": ["a", "b"]},
        )
        everything = client.post(
            "/api/v1/admin/jobs/notification-dead-letters/requeue", json={}
        )

    assert selected.json() == {"requeued": 2}
    assert everything.json() == {"requeued": 2}
    assert seen == [["a", "b"], None]


def test_admin_endpoint_errors_do_not_leak_details(monkeypatch):
    _as(["admin"])

    def boom():
        raise JobServiceError("Could not load job status.")

    monkeypatch.setattr(jobs_module.job_service, "get_job_overview", boom)

    with TestClient(app) as client:
        app.state.scheduler = None
        response = client.get("/api/v1/admin/jobs")

    assert response.status_code == 500
    assert response.json()["detail"] == "Could not load job status."


# --------------------------------------------------------- job registry

def test_registry_contains_every_automated_duty():
    names = [job.name for job in build_jobs(_settings())]

    assert names == [
        "activate_promotions",
        "release_expired_reservations",
        "notification_delivery",
        "smart_cart_auto_buy",
    ]


def test_promotions_run_every_minute_by_default_and_expiry_is_short():
    jobs = {job.name: job for job in build_jobs(_settings())}

    assert jobs["activate_promotions"].interval_seconds == 60
    assert jobs["release_expired_reservations"].interval_seconds == 30


def test_interval_zero_or_flag_disables_a_job():
    names = [
        job.name
        for job in build_jobs(
            _settings(
                promotion_activation_interval_seconds=0,
                notification_worker_enabled=False,
            )
        )
    ]

    assert "activate_promotions" not in names
    assert "notification_delivery" not in names
    assert "release_expired_reservations" in names


def test_master_switch_disables_the_scheduler():
    assert build_scheduler(_settings(scheduler_enabled=False)) is None


def test_registry_jobs_call_the_database_functions(monkeypatch):
    import app.workers.jobs as registry

    monkeypatch.setattr(registry, "activate_due_promotions", lambda: 4)
    monkeypatch.setattr(
        registry, "release_expired_reservations", lambda: {"released_count": 7}
    )
    monkeypatch.setattr(registry, "process_pending_auto_buys", lambda: [{}, {}])

    jobs = {job.name: job for job in build_jobs(_settings())}

    assert jobs["activate_promotions"].func() == {"activated": 4}
    assert jobs["release_expired_reservations"].func() == {"released": 7}
    assert jobs["smart_cart_auto_buy"].func() == {"processed": 2}


def test_lifespan_starts_and_stops_the_scheduler(monkeypatch):
    import app.main as main_module

    started, stopped = [], []

    class Fake:
        def start(self):
            started.append(1)

        async def stop(self):
            stopped.append(1)

    monkeypatch.setattr(main_module, "build_scheduler", lambda settings: Fake())

    with TestClient(app):
        assert started == [1]
        assert isinstance(app.state.scheduler, Fake)

    assert stopped == [1]


# --------------------------------------------------------- job_service

def test_heartbeat_maps_to_the_record_job_run_rpc(monkeypatch):
    from datetime import datetime, timezone

    client = MagicMock()
    monkeypatch.setattr(job_service, "supabase_admin", client)

    job_service.record_heartbeat(
        job_name="activate_promotions",
        interval_seconds=60,
        ok=True,
        error=None,
        duration_ms=12,
        result={"activated": 1},
        started_at=datetime(2026, 10, 27, tzinfo=timezone.utc),
        runs_delta=5,
        failures_delta=0,
        consecutive_failures=0,
    )

    name, params = client.rpc.call_args.args
    assert name == "record_job_run"
    assert params["p_job"] == "activate_promotions"
    assert params["p_runs_delta"] == 5
    assert params["p_started_at"].startswith("2026-10-27")


def test_requeue_returns_the_count_and_wraps_errors(monkeypatch):
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = 3
    monkeypatch.setattr(job_service, "supabase_admin", client)

    assert job_service.requeue_dead_letters(None) == 3

    client.rpc.return_value.execute.side_effect = RuntimeError("db: secret")
    with pytest.raises(JobServiceError) as caught:
        job_service.requeue_dead_letters(["a"])

    assert "secret" not in str(caught.value)


# ---------------------------------------------------------- logging

def test_json_formatter_emits_extra_fields_as_json():
    record = logging.LogRecord(
        "retailigent.scheduler", logging.INFO, __file__, 1, "job_run", (), None
    )
    record.job = "activate_promotions"
    record.duration_ms = 12
    record.result = {"activated": 2}

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "job_run"
    assert payload["level"] == "INFO"
    assert payload["job"] == "activate_promotions"
    assert payload["duration_ms"] == 12
    assert payload["result"] == {"activated": 2}
    assert payload["ts"].endswith("+00:00")


def test_json_formatter_includes_tracebacks():
    try:
        1 / 0
    except ZeroDivisionError:
        import sys

        record = logging.LogRecord(
            "x", logging.ERROR, __file__, 1, "failed", (), sys.exc_info()
        )

    assert "ZeroDivisionError" in json.loads(JsonFormatter().format(record))["exc_info"]


def test_configure_logging_is_idempotent():
    root = logging.getLogger()
    before = list(root.handlers)

    try:
        configure_logging("json")
        configure_logging("json")
        ours = [h for h in root.handlers if getattr(h, "_retailigent", False)]
        assert len(ours) == 1
        assert isinstance(ours[0].formatter, JsonFormatter)

        configure_logging("text")
        ours = [h for h in root.handlers if getattr(h, "_retailigent", False)]
        assert len(ours) == 1
        assert not isinstance(ours[0].formatter, JsonFormatter)
    finally:
        root.handlers[:] = before
