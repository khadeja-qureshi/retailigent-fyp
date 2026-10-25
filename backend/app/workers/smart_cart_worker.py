import asyncio
import logging

from app.agents.purchase_agent import (
    purchase_agent,
)

from app.services.smart_cart_service import (
    list_triggered_auto_buy_rules,
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
    "smart_cart_auto_buy"
)


def process_pending_auto_buys() -> dict:
    """
    Process all triggered Smart Cart rules that have explicit
    auto-buy authorization.

    One failing rule does not stop other rules.
    """

    summary = {
        "found":
            0,

        "processed":
            0,

        "failed":
            0,

        "results":
            [],
    }


    rules = (
        list_triggered_auto_buy_rules()
    )


    summary[
        "found"
    ] = len(
        rules
    )


    for rule in rules:
        rule_id = (
            rule.get(
                "id"
            )
        )


        if not rule_id:
            summary[
                "failed"
            ] += 1

            continue


        try:
            result = (
                purchase_agent
                .process_auto_buy_rule(
                    rule_id
                )
            )


            summary[
                "processed"
            ] += 1


            summary[
                "results"
            ].append(
                result
            )


        except Exception:
            summary[
                "failed"
            ] += 1


            logger.exception(
                "Smart Cart auto-buy failed for rule %s",
                rule_id,
            )


    return summary


async def auto_buy_loop(
    interval_seconds: int = 2,
):
    interval_seconds = max(
        int(
            interval_seconds
        ),
        1,
    )


    logger.info(
        "Smart Cart worker started "
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
                    process_pending_auto_buys
                )
            )


            record_job_success(
                JOB_NAME,
                started_at,
                result,
            )


        except asyncio.CancelledError:
            logger.info(
                "Smart Cart worker stopped"
            )

            raise


        except Exception as exc:
            record_job_failure(
                JOB_NAME,
                started_at,
                exc,
            )


            logger.exception(
                "Unexpected Smart Cart worker error"
            )


        await asyncio.sleep(
            interval_seconds
        )