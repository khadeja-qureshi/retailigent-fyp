import logging

from app.agents.purchase_agent import purchase_agent
from app.services.smart_cart_service import (
    list_triggered_auto_buy_rules,
)


logger = logging.getLogger(__name__)


def process_pending_auto_buys():
    """
    Process all currently-triggered Auto Buy rules.

    One failed rule must not stop the remaining rules. Failing to fetch
    the rules at all propagates, so the scheduler records the job as
    failed (and backs off) instead of silently reporting success.
    """
    results = []

    rules = list_triggered_auto_buy_rules()

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
