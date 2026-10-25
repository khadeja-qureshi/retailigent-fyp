import asyncio
import logging

from app.config import (
    settings,
)

from app.services.notification_service import (
    claim_deliveries,
    complete_delivery,
    dead_letter_delivery,
    deliver,
    fail_delivery,
)

from app.workers.job_state import (
    record_job_failure,
    record_job_start,
    record_job_success,
)


logger = logging.getLogger(
    __name__
)


JOB_NAME = (
    "notification_delivery"
)


def process_pending_deliveries() -> dict:
    """
    Drain one notification batch.

    Retry scheduling is controlled atomically in PostgreSQL.

    A delivery:
      - succeeds -> sent
      - fails before max attempts -> failed and retried later
      - fails on final attempt -> dead_letter
    """

    summary = {
        "claimed":
            0,

        "sent":
            0,

        "failed":
            0,

        "dead_lettered":
            0,
    }


    deliveries = (
        claim_deliveries()
    )


    summary[
        "claimed"
    ] = len(
        deliveries
    )


    for delivery in deliveries:
        delivery_id = str(
            delivery[
                "id"
            ]
        )


        attempts = int(
            delivery.get(
                "attempts",
                0,
            )
            or
            0
        )


        try:
            deliver(
                delivery
            )


            complete_delivery(
                delivery_id
            )


            summary[
                "sent"
            ] += 1


        except Exception as exc:
            error_message = str(
                exc
            )


            logger.exception(
                "Notification delivery %s failed "
                "(attempt=%s/%s)",
                delivery_id,
                attempts,
                settings.notification_max_attempts,
            )


            try:
                if (
                    attempts
                    >=
                    settings.notification_max_attempts
                ):
                    dead_letter_delivery(
                        delivery_id,
                        error_message,
                    )


                    summary[
                        "dead_lettered"
                    ] += 1


                    logger.error(
                        "Notification delivery %s moved to dead letter",
                        delivery_id,
                    )

                else:
                    fail_delivery(
                        delivery_id,
                        error_message,
                    )


                    summary[
                        "failed"
                    ] += 1


            except Exception:
                logger.exception(
                    "Could not record failure state for notification "
                    "delivery %s",
                    delivery_id,
                )


    return summary


async def notification_loop(
    interval_seconds: int = 5,
):
    interval_seconds = max(
        int(
            interval_seconds
        ),
        1,
    )


    logger.info(
        "Notification worker started "
        "(interval=%ss)",
        interval_seconds,
    )


    while True:
        started_at = (
            record_job_start(
                JOB_NAME
            )
        )


        try:
            result = (
                await asyncio.to_thread(
                    process_pending_deliveries
                )
            )


            record_job_success(
                JOB_NAME,
                started_at,
                result,
            )


        except asyncio.CancelledError:
            logger.info(
                "Notification worker stopped"
            )

            raise


        except Exception as exc:
            record_job_failure(
                JOB_NAME,
                started_at,
                exc,
            )


            logger.exception(
                "Unexpected notification worker error"
            )


        await asyncio.sleep(
            interval_seconds
        )