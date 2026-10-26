import asyncio
import logging
from datetime import datetime, timedelta, timezone

import pytest

from app.workers.scheduler import (
    MAX_BACKOFF_SECONDS,
    Job,
    Scheduler,
    summarize_result,
)


def make(job_func, interval=60, recorder=None, persist_every=15):
    job = Job("test_job", interval, job_func, "a test job")
    return Scheduler([job], recorder=recorder, persist_every_seconds=persist_every), job


# ----------------------------------------------------------- one tick

def test_successful_tick_updates_state():
    scheduler, job = make(lambda: {"released": 3})

    assert scheduler.run_job_blocking(job) is True

    state = scheduler.state["test_job"]
    assert state.last_status == "ok"
    assert state.last_success_at is not None
    assert state.run_count == 1
    assert state.failure_count == 0
    assert state.consecutive_failures == 0
    assert state.last_result == {"released": 3}
    assert state.last_duration_ms is not None


def test_failing_job_is_contained_and_recorded():
    def boom():
        raise RuntimeError("db unreachable")

    scheduler, job = make(boom)

    assert scheduler.run_job_blocking(job) is False      # does not raise

    state = scheduler.state["test_job"]
    assert state.last_status == "failed"
    assert "db unreachable" in state.last_error
    assert state.failure_count == 1
    assert state.consecutive_failures == 1
    assert state.last_success_at is None


def test_recovery_resets_the_failure_streak_but_keeps_totals():
    outcomes = iter([RuntimeError("x"), RuntimeError("y"), 5])

    def flaky():
        value = next(outcomes)
        if isinstance(value, Exception):
            raise value
        return value

    scheduler, job = make(flaky)

    scheduler.run_job_blocking(job)
    scheduler.run_job_blocking(job)
    assert scheduler.state["test_job"].consecutive_failures == 2

    scheduler.run_job_blocking(job)

    state = scheduler.state["test_job"]
    assert state.consecutive_failures == 0
    assert state.failure_count == 2
    assert state.run_count == 3
    assert state.last_error is None


# ------------------------------------------------------------ backoff

def test_backoff_grows_exponentially_and_is_capped():
    scheduler, job = make(lambda: None, interval=2)
    state = scheduler.state["test_job"]

    assert scheduler.next_delay(job) == 2                 # healthy: normal interval

    state.consecutive_failures = 1
    assert scheduler.next_delay(job) == 4
    state.consecutive_failures = 2
    assert scheduler.next_delay(job) == 8
    state.consecutive_failures = 50
    assert scheduler.next_delay(job) == MAX_BACKOFF_SECONDS


def test_backoff_never_goes_below_the_interval():
    scheduler, job = make(lambda: None, interval=600)     # longer than the cap
    scheduler.state["test_job"].consecutive_failures = 1

    assert scheduler.next_delay(job) >= 600


# ------------------------------------------------------- heartbeats

class Recorder:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def __call__(self, **kwargs):
        if self.fail:
            raise RuntimeError("heartbeat store down")
        self.calls.append(kwargs)


def test_first_run_is_persisted_and_fast_successes_are_throttled():
    recorder = Recorder()
    scheduler, job = make(lambda: {"n": 1}, interval=2, recorder=recorder)

    for _ in range(10):
        scheduler.run_job_blocking(job)

    assert len(recorder.calls) == 1                       # not 10 writes
    assert recorder.calls[0]["ok"] is True
    assert recorder.calls[0]["runs_delta"] == 1
    assert recorder.calls[0]["job_name"] == "test_job"
    assert recorder.calls[0]["interval_seconds"] == 2


def test_failure_streak_start_and_end_are_persisted_immediately():
    recorder = Recorder()
    outcomes = iter(["ok", "ok", "fail", "fail", "ok"])

    def job_func():
        if next(outcomes) == "fail":
            raise RuntimeError("down")
        return None

    scheduler, job = make(job_func, recorder=recorder)

    for _ in range(5):
        scheduler.run_job_blocking(job)

    kinds = [(c["ok"], c["consecutive_failures"]) for c in recorder.calls]
    # first run, first failure of the streak, recovery. The second failure is throttled.
    assert kinds == [(True, 0), (False, 1), (True, 0)]


def test_deltas_carry_over_so_no_runs_are_lost():
    recorder = Recorder()
    scheduler, job = make(lambda: None, recorder=recorder, persist_every=0)

    for _ in range(4):
        scheduler.run_job_blocking(job)

    assert sum(c["runs_delta"] for c in recorder.calls) == 4
    assert scheduler.state["test_job"].unpersisted_runs == 0


def test_a_broken_heartbeat_store_does_not_break_the_job():
    scheduler, job = make(lambda: {"ok": 1}, recorder=Recorder(fail=True))

    assert scheduler.run_job_blocking(job) is True
    assert scheduler.state["test_job"].last_status == "ok"


# ----------------------------------------------------------- logging

def test_each_run_emits_a_structured_job_run_event(caplog):
    scheduler, job = make(lambda: {"released": 2})

    with caplog.at_level(logging.DEBUG, logger="retailigent.scheduler"):
        scheduler.run_job_blocking(job)

    record = next(r for r in caplog.records if r.getMessage() == "job_run")
    assert record.event == "job_run"
    assert record.job == "test_job"
    assert record.status == "ok"
    assert record.result == {"released": 2}
    assert record.levelno == logging.INFO                 # did real work


def test_idle_ticks_log_at_debug_and_failures_at_error(caplog):
    idle, idle_job = make(lambda: {"released": 0})
    broken, broken_job = make(lambda: 1 / 0)

    with caplog.at_level(logging.DEBUG, logger="retailigent.scheduler"):
        idle.run_job_blocking(idle_job)
        broken.run_job_blocking(broken_job)

    levels = {r.status: r.levelno for r in caplog.records if r.getMessage() == "job_run"}
    assert levels == {"ok": logging.DEBUG, "failed": logging.ERROR}


# ------------------------------------------------------------ health

def test_snapshot_reports_last_run_times_and_hides_errors_by_default():
    scheduler, job = make(lambda: 1 / 0)
    scheduler.running = True
    scheduler.started_at = datetime.now(timezone.utc)
    scheduler.run_job_blocking(job)

    public = scheduler.snapshot()
    entry = public["jobs"][0]

    assert entry["last_started_at"] and entry["last_finished_at"]
    assert entry["last_status"] == "failed"
    assert "last_error" not in entry                      # nothing internal leaks

    detailed = scheduler.snapshot(include_errors=True)["jobs"][0]
    assert "division by zero" in detailed["last_error"]


def test_status_is_ok_degraded_or_disabled():
    scheduler, job = make(lambda: None)
    assert scheduler.snapshot()["status"] == "disabled"   # not started

    scheduler.running = True
    scheduler.started_at = datetime.now(timezone.utc)
    scheduler.run_job_blocking(job)
    assert scheduler.snapshot()["status"] == "ok"

    scheduler.state["test_job"].consecutive_failures = 3
    assert scheduler.snapshot()["status"] == "degraded"


def test_a_job_that_stops_succeeding_goes_stale():
    scheduler, job = make(lambda: None, interval=60)
    scheduler.running = True
    scheduler.started_at = datetime.now(timezone.utc) - timedelta(hours=1)

    assert scheduler.is_stale(job) is True                # never succeeded in an hour
    assert scheduler.snapshot()["status"] == "degraded"

    scheduler.run_job_blocking(job)

    assert scheduler.is_stale(job) is False
    assert scheduler.snapshot()["status"] == "ok"


def test_job_names_must_be_unique():
    with pytest.raises(ValueError):
        Scheduler([Job("a", 1, lambda: None), Job("a", 2, lambda: None)])


def test_summarize_result_is_small_and_json_safe():
    assert summarize_result(5) == {"value": 5}
    assert summarize_result([1, 2, 3]) == {"count": 3}
    assert summarize_result({"a": 1, "b": object()}) == {"a": 1}
    assert summarize_result(None) == {"value": None}


# -------------------------------------------------- the real asyncio loop

def test_loop_runs_jobs_isolates_failures_and_stops_cleanly():
    async def scenario():
        good_runs, bad_runs = [], []

        def good():
            good_runs.append(1)
            return {"n": len(good_runs)}

        def bad():
            bad_runs.append(1)
            raise RuntimeError("always fails")

        scheduler = Scheduler(
            [Job("good", 0.02, good), Job("bad", 0.02, bad)],
            persist_every_seconds=0,
        )
        scheduler.start()
        await asyncio.sleep(0.4)
        await scheduler.stop()

        return scheduler, good_runs, bad_runs

    scheduler, good_runs, bad_runs = asyncio.run(scenario())

    assert len(good_runs) >= 5                            # the healthy job kept running
    assert scheduler.state["good"].last_status == "ok"
    assert scheduler.state["bad"].last_status == "failed"
    assert len(bad_runs) < len(good_runs)                 # the failing job backed off
    assert scheduler.running is False


def test_every_job_runs_immediately_on_start():
    async def scenario():
        loop = asyncio.get_running_loop()
        ran = asyncio.Event()

        def job_func():
            loop.call_soon_threadsafe(ran.set)       # runs in a worker thread

        scheduler = Scheduler([Job("first", 3600, job_func)])
        scheduler.start()

        # Would hang for an hour if the first tick waited a full interval.
        await asyncio.wait_for(ran.wait(), timeout=2)
        await scheduler.stop()

    asyncio.run(scenario())
