"""
The job registry: which background jobs run, how often, and what they call.

Every automated duty of the backend lives here, in one place:

  activate_promotions          emit sale_started events for promotions whose
                               start time has arrived (every minute)
  release_expired_reservations return stock held by expired reservations
  notification_delivery        drain notification_deliveries (retry/backoff/
                               dead-letter handled in the database)
  smart_cart_auto_buy          execute triggered Smart Cart Auto Buy rules

An interval of 0 (or <= 0) disables that job. SCHEDULER_ENABLED=false disables
all of them (for example in tests or one-off scripts).
"""
from __future__ import annotations

from app.config import Settings
from app.services import job_service
from app.services.reservation_service import release_expired_reservations
from app.services.smart_cart_service import activate_due_promotions
from app.workers.notification_worker import process_pending_deliveries
from app.workers.scheduler import Job, Scheduler
from app.workers.smart_cart_worker import process_pending_auto_buys


def _auto_buy_job() -> dict:
    results = process_pending_auto_buys()
    return {"processed": len(results)}


def build_jobs(settings: Settings) -> list[Job]:
    jobs: list[Job] = []

    def add(name: str, interval: float, func, description: str) -> None:
        if interval and interval > 0:
            jobs.append(Job(name, float(interval), func, description))

    add(
        "activate_promotions",
        settings.promotion_activation_interval_seconds,
        lambda: {"activated": activate_due_promotions()},
        "Fire sale_started events for promotions that have just started",
    )
    add(
        "release_expired_reservations",
        settings.reservation_expiry_interval_seconds,
        lambda: {"released": release_expired_reservations().get("released_count", 0)},
        "Release expired reservations and return their stock",
    )

    if settings.notification_worker_enabled:
        add(
            "notification_delivery",
            settings.notification_worker_interval_seconds,
            process_pending_deliveries,
            "Deliver queued notifications (retry, backoff, dead-letter)",
        )

    if settings.smart_cart_worker_enabled:
        add(
            "smart_cart_auto_buy",
            settings.smart_cart_worker_interval_seconds,
            _auto_buy_job,
            "Execute triggered Smart Cart Auto Buy rules",
        )

    return jobs


def build_scheduler(settings: Settings) -> Scheduler | None:
    if not settings.scheduler_enabled:
        return None

    jobs = build_jobs(settings)

    if not jobs:
        return None

    return Scheduler(
        jobs,
        recorder=job_service.record_heartbeat,
        persist_every_seconds=settings.job_heartbeat_persist_seconds,
    )
