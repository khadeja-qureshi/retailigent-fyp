from __future__ import annotations

from copy import deepcopy
from datetime import (
    datetime,
    timezone,
)
from threading import Lock
from typing import Any


_lock = Lock()


_jobs: dict[str, dict[str, Any]] = {}


def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def _iso(
    value: datetime | None,
) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def register_job(
    job_name: str,
) -> None:
    with _lock:
        if job_name in _jobs:
            return

        _jobs[job_name] = {
            "job_name": job_name,

            "started_at":
                _utc_now(),

            "last_started_at":
                None,

            "last_succeeded_at":
                None,

            "last_failed_at":
                None,

            "last_error":
                None,

            "last_duration_ms":
                None,

            "last_result":
                None,

            "run_count":
                0,

            "success_count":
                0,

            "failure_count":
                0,
        }


def record_job_start(
    job_name: str,
) -> datetime:
    register_job(
        job_name
    )

    started_at = (
        _utc_now()
    )

    with _lock:
        job = (
            _jobs[
                job_name
            ]
        )

        job[
            "last_started_at"
        ] = started_at

        job[
            "run_count"
        ] += 1

    return started_at


def record_job_success(
    job_name: str,
    started_at: datetime,
    result: Any = None,
) -> None:
    register_job(
        job_name
    )

    completed_at = (
        _utc_now()
    )

    duration_ms = (
        completed_at
        -
        started_at
    ).total_seconds() * 1000


    with _lock:
        job = (
            _jobs[
                job_name
            ]
        )

        job[
            "last_succeeded_at"
        ] = completed_at

        job[
            "last_duration_ms"
        ] = round(
            duration_ms,
            2,
        )

        job[
            "last_result"
        ] = result

        job[
            "last_error"
        ] = None

        job[
            "success_count"
        ] += 1


def record_job_failure(
    job_name: str,
    started_at: datetime,
    error: Exception | str,
) -> None:
    register_job(
        job_name
    )

    completed_at = (
        _utc_now()
    )

    duration_ms = (
        completed_at
        -
        started_at
    ).total_seconds() * 1000


    with _lock:
        job = (
            _jobs[
                job_name
            ]
        )

        job[
            "last_failed_at"
        ] = completed_at

        job[
            "last_duration_ms"
        ] = round(
            duration_ms,
            2,
        )

        job[
            "last_error"
        ] = str(
            error
        )[:1000]

        job[
            "failure_count"
        ] += 1


def get_job_states(
    expected_intervals: dict[str, int],
    stale_multiplier: int = 3,
) -> dict:
    """
    Return serializable worker health information.

    A job is:
      - starting: it has not completed a run yet
      - healthy: most recent successful run is recent
      - stale: last successful run is older than expected
      - failing: latest failure is newer than latest success
    """

    now = (
        _utc_now()
    )


    with _lock:
        copied = deepcopy(
            _jobs
        )


    result: dict[
        str,
        dict[str, Any],
    ] = {}


    for (
        job_name,
        job,
    ) in copied.items():

        expected_interval = (
            expected_intervals.get(
                job_name
            )
        )


        last_success = (
            job.get(
                "last_succeeded_at"
            )
        )

        last_failure = (
            job.get(
                "last_failed_at"
            )
        )


        status = (
            "starting"
        )


        if (
            last_failure is not None
            and
            (
                last_success is None
                or
                last_failure
                >
                last_success
            )
        ):
            status = (
                "failing"
            )

        elif (
            last_success is not None
        ):
            status = (
                "healthy"
            )


            if (
                expected_interval
                is not None
                and
                expected_interval > 0
            ):
                age_seconds = (
                    now
                    -
                    last_success
                ).total_seconds()


                stale_after = (
                    expected_interval
                    *
                    max(
                        stale_multiplier,
                        1,
                    )
                )


                if (
                    age_seconds
                    >
                    stale_after
                ):
                    status = (
                        "stale"
                    )


        result[
            job_name
        ] = {
            "status":
                status,

            "expected_interval_seconds":
                expected_interval,

            "started_at":
                _iso(
                    job.get(
                        "started_at"
                    )
                ),

            "last_started_at":
                _iso(
                    job.get(
                        "last_started_at"
                    )
                ),

            "last_succeeded_at":
                _iso(
                    last_success
                ),

            "last_failed_at":
                _iso(
                    last_failure
                ),

            "last_duration_ms":
                job.get(
                    "last_duration_ms"
                ),

            "run_count":
                job.get(
                    "run_count",
                    0,
                ),

            "success_count":
                job.get(
                    "success_count",
                    0,
                ),

            "failure_count":
                job.get(
                    "failure_count",
                    0,
                ),

            "last_error":
                job.get(
                    "last_error"
                ),

            "last_result":
                job.get(
                    "last_result"
                ),
        }


    return result