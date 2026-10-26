import logging

from app.services.notification_service import (
    PermanentDeliveryError,
    claim_deliveries,
    complete_delivery,
    deliver,
    fail_delivery,
)


logger = logging.getLogger(__name__)


def process_pending_deliveries() -> dict:
    """
    Drain one batch of notification_deliveries (a scheduler job).

    * One failing delivery never blocks the rest of the batch.
    * Temporary failures are retried by the database with exponential
      backoff until the attempt limit, then dead-lettered.
    * Permanent failures (no email address, record deleted, ...) are
      dead-lettered at once.
    * If the batch cannot even be claimed, the error propagates so the
      scheduler records the job as failed and backs off.
    """
    summary = {"sent": 0, "failed": 0, "dead_lettered": 0}

    deliveries = claim_deliveries()

    for delivery in deliveries:
        delivery_id = str(delivery["id"])

        try:
            deliver(delivery)
            complete_delivery(delivery_id)
            summary["sent"] += 1
            continue

        except PermanentDeliveryError as exc:
            permanent = True
            error = str(exc)
            logger.warning(
                "notification_delivery_permanent_failure",
                extra={
                    "event": "notification_delivery_failed",
                    "delivery_id": delivery_id,
                    "permanent": True,
                    "error": error,
                },
            )

        except Exception as exc:
            permanent = False
            error = str(exc)
            logger.warning(
                "notification_delivery_failed",
                extra={
                    "event": "notification_delivery_failed",
                    "delivery_id": delivery_id,
                    "permanent": False,
                    "attempt": delivery.get("attempts"),
                    "error": error[:300],
                },
            )

        summary["failed"] += 1

        if permanent:
            summary["dead_lettered"] += 1

        try:
            fail_delivery(delivery_id, error, permanent=permanent)
        except Exception:
            logger.exception(
                "Could not record failure for delivery %s", delivery_id
            )

    return summary
