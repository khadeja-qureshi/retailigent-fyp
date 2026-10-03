import asyncio
import logging

from app.services.notification_service import (
    claim_deliveries,
    complete_delivery,
    deliver,
    fail_delivery,
)


logger = logging.getLogger(__name__)


def process_pending_deliveries() -> dict:
    """
    Drain one batch of notification_deliveries.

    One failing delivery never blocks the rest. Failures are recorded and
    retried with exponential backoff until the max-attempt limit.
    """
    summary = {"sent": 0, "failed": 0}

    try:
        deliveries = claim_deliveries()
    except Exception:
        logger.exception("Failed to claim notification deliveries")
        return summary

    for delivery in deliveries:
        delivery_id = str(delivery["id"])

        try:
            deliver(delivery)
            complete_delivery(delivery_id)
            summary["sent"] += 1

        except Exception as exc:
            logger.exception(
                "Notification delivery %s failed", delivery_id
            )
            summary["failed"] += 1

            try:
                fail_delivery(delivery_id, str(exc))
            except Exception:
                logger.exception(
                    "Could not record failure for delivery %s",
                    delivery_id,
                )

    return summary


async def notification_loop(interval_seconds: int = 5):
    logger.info(
        "Notification worker started (interval=%ss)", interval_seconds
    )

    while True:
        try:
            await asyncio.to_thread(process_pending_deliveries)

        except asyncio.CancelledError:
            logger.info("Notification worker stopped")
            raise

        except Exception:
            logger.exception("Unexpected notification worker error")

        await asyncio.sleep(interval_seconds)
