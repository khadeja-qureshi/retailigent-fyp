"""Persistence and admin reporting for scheduler jobs."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.supabase_client import supabase_admin

logger = logging.getLogger(__name__)

DEAD_LETTER_SAMPLE_SIZE = 10


class JobServiceError(Exception):
    """Raised when job information cannot be read or changed."""


def record_heartbeat(
    *,
    job_name: str,
    interval_seconds: int,
    ok: bool,
    error: str | None,
    duration_ms: int,
    result: Any,
    started_at: datetime,
    runs_delta: int,
    failures_delta: int,
    consecutive_failures: int,
) -> None:
    """Scheduler recorder: upsert the job's row in `job_runs`."""

    supabase_admin.rpc(
        "record_job_run",
        {
            "p_job": job_name,
            "p_interval_seconds": interval_seconds,
            "p_ok": ok,
            "p_error": error,
            "p_duration_ms": duration_ms,
            "p_result": result,
            "p_started_at": started_at.isoformat(),
            "p_runs_delta": runs_delta,
            "p_failures_delta": failures_delta,
            "p_consecutive_failures": consecutive_failures,
        },
    ).execute()


def _count(query) -> int:
    return int(query.execute().count or 0)


def get_job_overview() -> dict[str, Any]:
    """Heartbeats from the database plus the notification delivery backlog."""

    try:
        runs = (
            supabase_admin
            .table("job_runs")
            .select("*")
            .order("job_name")
            .execute()
            .data
            or []
        )

        deliveries = supabase_admin.table("notification_deliveries")

        backlog = {
            "pending": _count(
                supabase_admin.table("notification_deliveries")
                .select("id", count="exact")
                .eq("status", "pending")
                .is_("dead_lettered_at", "null")
                .limit(1)
            ),
            "retrying": _count(
                supabase_admin.table("notification_deliveries")
                .select("id", count="exact")
                .eq("status", "failed")
                .is_("dead_lettered_at", "null")
                .limit(1)
            ),
            "processing": _count(
                supabase_admin.table("notification_deliveries")
                .select("id", count="exact")
                .eq("status", "processing")
                .limit(1)
            ),
            "dead_lettered": _count(
                supabase_admin.table("notification_deliveries")
                .select("id", count="exact")
                .not_.is_("dead_lettered_at", "null")
                .limit(1)
            ),
        }

        dead_letters = (
            deliveries
            .select("id, channel, attempts, error_message, last_attempt_at, dead_lettered_at")
            .not_.is_("dead_lettered_at", "null")
            .order("dead_lettered_at", desc=True)
            .limit(DEAD_LETTER_SAMPLE_SIZE)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        logger.exception("Could not read job status")
        raise JobServiceError("Could not load job status.") from exc

    now = datetime.now(timezone.utc)
    jobs = []

    for row in runs:
        interval = int(row.get("interval_seconds") or 60)
        reference = row.get("last_success_at") or row.get("updated_at")
        stale = False

        if reference:
            try:
                age = (now - datetime.fromisoformat(reference)).total_seconds()
                stale = age > max(interval * 3, 30)
            except ValueError:
                stale = False

        jobs.append({**row, "stale": stale})

    return {
        "jobs": jobs,
        "notification_backlog": backlog,
        "notification_dead_letters": dead_letters,
    }


def requeue_dead_letters(delivery_ids: list[str] | None) -> int:
    try:
        response = supabase_admin.rpc(
            "requeue_dead_letter_deliveries",
            {"p_delivery_ids": delivery_ids},
        ).execute()
    except Exception as exc:
        logger.exception("Could not requeue dead-lettered deliveries")
        raise JobServiceError("Could not requeue deliveries.") from exc

    return int(response.data or 0)
