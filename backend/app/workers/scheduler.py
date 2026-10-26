"""
Background job scheduler (Phase 17).

One asyncio task per job. Each tick runs the (blocking) job function in a
worker thread, so a slow Supabase call never blocks the API's event loop.

Guarantees
----------
* A failing job never stops the scheduler or any other job.
* After a failure the job backs off exponentially (capped), then resumes its
  normal interval on the first success.
* Every run is logged as structured JSON (event="job_run").
* Heartbeats are persisted to the `job_runs` table through an optional
  recorder. Failures are persisted immediately; successes at most every
  `persist_every_seconds`, so a 2-second job does not write twice a second.
* In-process state backs GET /health/jobs (no database round trip).

Multi-instance note: jobs are idempotent and use `for update skip locked`
inside the database (activate_due_promotions, release_expired_reservations,
claim_notification_deliveries), so two API instances can safely run the same
job. Running several instances only duplicates (cheap) work.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger("retailigent.scheduler")

MAX_BACKOFF_SECONDS = 300
DEFAULT_PERSIST_EVERY_SECONDS = 15
STALE_AFTER_INTERVALS = 3
STALE_MIN_SECONDS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


@dataclass
class Job:
    name: str
    interval_seconds: float
    func: Callable[[], Any]
    description: str = ""


@dataclass
class JobState:
    started_at: Optional[datetime] = None       # last run started
    finished_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_status: Optional[str] = None           # "ok" | "failed"
    last_error: Optional[str] = None
    last_duration_ms: Optional[int] = None
    last_result: Any = None
    run_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    # persistence bookkeeping
    unpersisted_runs: int = 0
    unpersisted_failures: int = 0
    last_persisted_at: float = 0.0


Recorder = Callable[..., None]


def summarize_result(result: Any) -> Any:
    """Keep job results small and JSON-safe for logs and the heartbeat table."""

    if result is None or isinstance(result, (bool, int, float, str)):
        return {"value": result}

    if isinstance(result, dict):
        return {
            str(k): v
            for k, v in list(result.items())[:20]
            if isinstance(v, (bool, int, float, str, type(None)))
        }

    if isinstance(result, (list, tuple)):
        return {"count": len(result)}

    return {"type": type(result).__name__}


class Scheduler:
    def __init__(
        self,
        jobs: list[Job],
        recorder: Optional[Recorder] = None,
        persist_every_seconds: float = DEFAULT_PERSIST_EVERY_SECONDS,
    ) -> None:
        names = [job.name for job in jobs]

        if len(set(names)) != len(names):
            raise ValueError("Job names must be unique")

        self.jobs: dict[str, Job] = {job.name: job for job in jobs}
        self.state: dict[str, JobState] = {job.name: JobState() for job in jobs}
        self._recorder = recorder
        self._persist_every = persist_every_seconds
        self._tasks: list[asyncio.Task] = []
        self.started_at: Optional[datetime] = None
        self.running = False

    # ------------------------------------------------------------------ run

    def run_job_blocking(self, job: Job) -> bool:
        """
        Execute one tick of one job synchronously and record the outcome.
        Returns True on success. Never raises.
        """

        state = self.state[job.name]
        previous_failures = state.consecutive_failures
        started = _now()
        t0 = time.perf_counter()
        ok = True
        error: Optional[str] = None
        result: Any = None

        try:
            result = job.func()
        except Exception as exc:  # noqa: BLE001 - a job must never kill the scheduler
            ok = False
            error = f"{type(exc).__name__}: {exc}"
            logger.error(
                "job_run",
                extra={
                    "event": "job_run",
                    "job": job.name,
                    "status": "failed",
                    "error": error[:500],
                },
                exc_info=True,
            )

        duration_ms = int((time.perf_counter() - t0) * 1000)
        summary = summarize_result(result) if ok else None

        state.started_at = started
        state.finished_at = _now()
        state.last_duration_ms = duration_ms
        state.run_count += 1
        state.unpersisted_runs += 1

        if ok:
            state.last_status = "ok"
            state.last_success_at = state.finished_at
            state.last_error = None
            state.last_result = summary
            state.consecutive_failures = 0
        else:
            state.last_status = "failed"
            state.last_error = error
            state.failure_count += 1
            state.unpersisted_failures += 1
            state.consecutive_failures += 1

        if ok:
            # Quiet by default: idle ticks (nothing to do) log at DEBUG, ticks
            # that actually did something log at INFO.
            did_work = bool(summary) and any(
                isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0
                for v in summary.values()
            )
            logger.log(
                logging.INFO if did_work else logging.DEBUG,
                "job_run",
                extra={
                    "event": "job_run",
                    "job": job.name,
                    "status": "ok",
                    "duration_ms": duration_ms,
                    "result": summary,
                },
            )

        self._persist(
            job, state, ok, error, duration_ms, summary, started, previous_failures
        )

        return ok

    def _persist(
        self,
        job: Job,
        state: JobState,
        ok: bool,
        error: Optional[str],
        duration_ms: int,
        summary: Any,
        started: datetime,
        previous_failures: int,
    ) -> None:
        if self._recorder is None:
            return

        now = time.monotonic()
        due = (now - state.last_persisted_at) >= self._persist_every
        first = state.last_persisted_at == 0.0
        # A failure streak starting or ending is always worth recording at once.
        transition = (not ok and previous_failures == 0) or (ok and previous_failures > 0)

        if not (due or first or transition):
            return

        try:
            self._recorder(
                job_name=job.name,
                interval_seconds=max(int(job.interval_seconds), 1),
                ok=ok,
                error=error,
                duration_ms=duration_ms,
                result=summary,
                started_at=started,
                runs_delta=state.unpersisted_runs,
                failures_delta=state.unpersisted_failures,
                consecutive_failures=state.consecutive_failures,
            )
            state.unpersisted_runs = 0
            state.unpersisted_failures = 0
            state.last_persisted_at = now
        except Exception:  # noqa: BLE001 - heartbeats are best effort
            logger.warning(
                "job_heartbeat_failed",
                extra={"event": "job_heartbeat_failed", "job": job.name},
                exc_info=True,
            )

    # -------------------------------------------------------------- loop

    def next_delay(self, job: Job) -> float:
        failures = self.state[job.name].consecutive_failures

        if failures == 0:
            return job.interval_seconds

        backoff = min(job.interval_seconds * (2 ** min(failures, 8)), MAX_BACKOFF_SECONDS)

        # Never retry sooner than the job's own interval (a 10-minute job
        # must not be pulled forward to the 5-minute backoff cap).
        return float(max(job.interval_seconds, backoff))

    async def _job_loop(self, job: Job) -> None:
        logger.info(
            "job_started",
            extra={
                "event": "job_started",
                "job": job.name,
                "interval_seconds": job.interval_seconds,
            },
        )

        while True:
            try:
                await asyncio.to_thread(self.run_job_blocking, job)
                await asyncio.sleep(self.next_delay(job))
            except asyncio.CancelledError:
                logger.info(
                    "job_stopped", extra={"event": "job_stopped", "job": job.name}
                )
                raise
            except Exception:  # noqa: BLE001 - last line of defence
                logger.exception(
                    "job_loop_error",
                    extra={"event": "job_loop_error", "job": job.name},
                )
                await asyncio.sleep(job.interval_seconds)

    def start(self) -> None:
        if self.running:
            return

        self.running = True
        self.started_at = _now()
        self._tasks = [
            asyncio.create_task(self._job_loop(job), name=f"job:{job.name}")
            for job in self.jobs.values()
        ]
        logger.info(
            "scheduler_started",
            extra={"event": "scheduler_started", "jobs": list(self.jobs)},
        )

    async def stop(self) -> None:
        if not self.running:
            return

        self.running = False

        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        logger.info("scheduler_stopped", extra={"event": "scheduler_stopped"})

    # ------------------------------------------------------------ health

    def is_stale(self, job: Job, now: Optional[datetime] = None) -> bool:
        now = now or _now()
        state = self.state[job.name]
        threshold = timedelta(
            seconds=max(job.interval_seconds * STALE_AFTER_INTERVALS, STALE_MIN_SECONDS)
        )
        reference = state.last_success_at or self.started_at

        if reference is None:
            return False

        return (now - reference) > threshold

    def snapshot(self, include_errors: bool = False) -> dict[str, Any]:
        now = _now()
        jobs = []
        degraded = False

        for job in self.jobs.values():
            state = self.state[job.name]
            stale = self.is_stale(job, now) if self.running else False

            if stale or state.consecutive_failures >= 3:
                degraded = True

            entry: dict[str, Any] = {
                "name": job.name,
                "description": job.description,
                "interval_seconds": job.interval_seconds,
                "last_started_at": _iso(state.started_at),
                "last_finished_at": _iso(state.finished_at),
                "last_success_at": _iso(state.last_success_at),
                "last_status": state.last_status,
                "last_duration_ms": state.last_duration_ms,
                "run_count": state.run_count,
                "failure_count": state.failure_count,
                "consecutive_failures": state.consecutive_failures,
                "stale": stale,
            }

            if include_errors:
                entry["last_error"] = state.last_error
                entry["last_result"] = state.last_result

            jobs.append(entry)

        return {
            "status": (
                "disabled" if not self.running
                else "degraded" if degraded
                else "ok"
            ),
            "scheduler_started_at": _iso(self.started_at),
            "jobs": jobs,
        }
