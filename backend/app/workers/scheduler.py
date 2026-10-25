import asyncio
import logging

from app.services.reservation_service import (
    release_expired_reservations,
)
from app.services.smart_cart_service import (
    activate_due_promotions,
)
from app.workers.job_state import (
    record_job_failure,
    record_job_start,
    record_job_success,
)


logger = logging.getLogger(
    __name__
)


PROMOTION_JOB_NAME = (
    "promotion_activation"
)

RESERVATION_JOB_NAME = (
    "reservation_expiry"
)


def process_due_promotions() -> dict:
    """
    Activate any promotion whose start time has arrived.

    The database RPC is authoritative and idempotent.
    """

    activated_count = (
        activate_due_promotions()
    )


    result = {
        "activated_count":
            int(
                activated_count
                or
                0
            ),
    }


    if (
        result[
            "activated_count"
        ]
        > 0
    ):
        logger.info(
            "Activated %s due promotion(s)",
            result[
                "activated_count"
            ],
        )


    return result


def process_expired_reservations() -> dict:
    """
    Release reservations whose expiry time has passed.

    Inventory mutation remains inside the deterministic
    PostgreSQL RPC.
    """

    result = (
        release_expired_reservations()
    )


    released_count = int(
        result.get(
            "released_count",
            0,
        )
        or
        0
    )


    normalized = {
        "released_count":
            released_count,
    }


    if released_count > 0:
        logger.info(
            "Released %s expired reservation(s)",
            released_count,
        )


    return normalized


async def promotion_scheduler_loop(
    interval_seconds: int = 60,
):
    interval_seconds = max(
        int(
            interval_seconds
        ),
        1,
    )


    logger.info(
        "Promotion scheduler started "
        "(interval=%ss)",
        interval_seconds,
    )


    while True:
        started_at = (
            record_job_start(
                PROMOTION_JOB_NAME
            )
        )


        try:
            result = (
                await asyncio.to_thread(
                    process_due_promotions
                )
            )


            record_job_success(
                PROMOTION_JOB_NAME,
                started_at,
                result,
            )

        except asyncio.CancelledError:
            logger.info(
                "Promotion scheduler stopped"
            )

            raise

        except Exception as exc:
            record_job_failure(
                PROMOTION_JOB_NAME,
                started_at,
                exc,
            )


            logger.exception(
                "Promotion scheduler run failed"
            )


        await asyncio.sleep(
            interval_seconds
        )


async def reservation_scheduler_loop(
    interval_seconds: int = 30,
):
    interval_seconds = max(
        int(
            interval_seconds
        ),
        1,
    )


    logger.info(
        "Reservation expiry scheduler started "
        "(interval=%ss)",
        interval_seconds,
    )


    while True:
        started_at = (
            record_job_start(
                RESERVATION_JOB_NAME
            )
        )


        try:
            result = (
                await asyncio.to_thread(
                    process_expired_reservations
                )
            )


            record_job_success(
                RESERVATION_JOB_NAME,
                started_at,
                result,
            )

        except asyncio.CancelledError:
            logger.info(
                "Reservation expiry scheduler stopped"
            )

            raise

        except Exception as exc:
            record_job_failure(
                RESERVATION_JOB_NAME,
                started_at,
                exc,
            )


            logger.exception(
                "Reservation expiry scheduler run failed"
            )


        await asyncio.sleep(
            interval_seconds
        )