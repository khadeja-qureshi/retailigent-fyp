import asyncio
import logging

from app.agents.purchase_agent import (
    purchase_agent,
)

from app.services.smart_cart_service import (
    list_triggered_auto_buy_rules,
)


logger = logging.getLogger(__name__)


def process_pending_auto_buys():
    rules = (
        list_triggered_auto_buy_rules()
    )

    results = []

    for rule in rules:
        try:
            result = (
                purchase_agent
                .process_auto_buy_rule(
                    rule["id"]
                )
            )

            results.append(result)

        except Exception:
            logger.exception(
                "Smart Cart auto-buy failed "
                "for rule %s",
                rule["id"],
            )

    return results


async def auto_buy_loop(
    interval_seconds: int = 2,
):
    while True:
        await asyncio.to_thread(
            process_pending_auto_buys
        )

        await asyncio.sleep(
            interval_seconds
        )