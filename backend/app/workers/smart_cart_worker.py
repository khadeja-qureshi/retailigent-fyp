import asyncio
import logging

from app.agents.purchase_agent import purchase_agent
from app.services.smart_cart_service import (
    list_triggered_auto_buy_rules,
)


logger = logging.getLogger(__name__)


def process_pending_auto_buys():
    """
    Process all currently-triggered Auto Buy rules.

    One failed rule must not stop the remaining rules.
    """
    results = []

    try:
        rules = list_triggered_auto_buy_rules()
    except Exception:
        logger.exception(
            "Failed to fetch triggered Smart Cart rules"
        )
        return results

    for rule in rules:
        rule_id = rule.get("id")

        try:
            result = (
                purchase_agent
                .process_auto_buy_rule(
                    rule_id
                )
            )

            results.append(result)

        except Exception:
            logger.exception(
                "Smart Cart auto-buy failed for rule %s",
                rule_id,
            )

    return results


async def auto_buy_loop(
    interval_seconds: int = 2,
):
    """
    Continuous Smart Cart worker.

    Important:
    A temporary Supabase/network error must NOT
    terminate the background worker permanently.
    """
    logger.info(
        "Smart Cart worker started "
        "(interval=%ss)",
        interval_seconds,
    )

    while True:
        try:
            await asyncio.to_thread(
                process_pending_auto_buys
            )

        except asyncio.CancelledError:
            logger.info(
                "Smart Cart worker stopped"
            )
            raise

        except Exception:
            # Never allow one transient DB/network
            # problem to kill the worker forever.
            logger.exception(
                "Unexpected Smart Cart worker error"
            )

        await asyncio.sleep(
            interval_seconds
        )