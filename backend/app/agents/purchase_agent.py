from typing import Any
from app.services.pricing_service import get_effective_prices
from app.services.purchase_service import (
    convert_customer_reservation_to_purchase,
    execute_customer_purchase,
    find_purchase_branch,
)
from app.services.smart_cart_service import (
    get_smart_cart_rule_for_system,
)


class PurchaseAgent:
    """
    Purchase Agent for Retailigent.

    Coordinates customer purchases while leaving
    pricing, inventory validation, idempotency, and
    purchase execution to deterministic services/RPCs.
    """

    def purchase_from_reservation(
        self,
        customer_id: str,
        reservation_id: str,
        idempotency_key: str,
        quantity: int | None = None,
    ) -> dict[str, Any]:
        """
        Convert an existing customer reservation
        into a purchase.
        """
        return (
            convert_customer_reservation_to_purchase(
                customer_id=customer_id,
                reservation_id=reservation_id,
                idempotency_key=idempotency_key,
                quantity=quantity,
            )
        )

    def purchase_direct(
        self,
        customer_id: str,
        variant_id: str,
        quantity: int,
        idempotency_key: str,
        branch_id: str | None = None,
        smart_cart_rule_id: (
            str | None
        ) = None,
    ) -> dict[str, Any]:
        """
        Complete a direct customer purchase.

        If no branch is explicitly pinned, resolve an
        actual active branch that currently has enough
        sellable stock before executing the purchase.
        """

        resolved_branch_id = branch_id

        if not resolved_branch_id:
            resolved_branch_id = (
                find_purchase_branch(
                    variant_id=variant_id,
                    quantity=quantity,
                )
            )

        if not resolved_branch_id:
            return {
                "success": False,
                "order_id": None,
                "purchase_attempt_id": None,
                "reason_code":
                    "no_branch_with_stock",
                "reason": (
                    "No active branch currently "
                    "has enough available stock."
                ),
            }

        return execute_customer_purchase(
            customer_id=customer_id,
            variant_id=variant_id,
            quantity=quantity,
            idempotency_key=idempotency_key,
            branch_id=resolved_branch_id,
            smart_cart_rule_id=(
                smart_cart_rule_id
            ),
        )

    def purchase(
        self,
        customer_id: str,
        variant_id: str,
        quantity: int,
        idempotency_key: str,
        branch_id: str | None = None,
        reservation_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Unified customer purchase entry point.

        If a matching reservation is explicitly
        supplied, convert that reservation.

        Otherwise perform a direct deterministic
        purchase.
        """

        if reservation_id:
            return (
                self.purchase_from_reservation(
                    customer_id=customer_id,
                    reservation_id=(
                        reservation_id
                    ),
                    idempotency_key=(
                        idempotency_key
                    ),
                    quantity=quantity,
                )
            )

        return self.purchase_direct(
            customer_id=customer_id,
            variant_id=variant_id,
            quantity=quantity,
            idempotency_key=idempotency_key,
            branch_id=branch_id,
        )

    def process_auto_buy_rule(
        self,
        rule_id: str,
    ) -> dict[str, Any]:
        """
        Process a triggered Smart Cart auto-buy rule.

        Revalidate the rule's price conditions immediately before
        purchase. Fail closed if authoritative pricing is unavailable.
        """

        rule = get_smart_cart_rule_for_system(rule_id)

        if rule["status"] != "triggered":
            return {
                "processed": False,
                "reason": "rule_not_triggered",
            }

        if rule["authorization_mode"] != "auto_buy":
            return {
                "processed": False,
                "reason": "not_auto_buy",
            }

        # Never purchase using stale or unverified price conditions.
        try:
            pricing_by_variant = get_effective_prices(
                [rule["variant_id"]]
            )
            pricing = pricing_by_variant.get(
                str(rule["variant_id"])
            )

            if not pricing:
                return {
                    "processed": False,
                    "reason": "price_unavailable",
                }

            from decimal import Decimal

            effective_price = Decimal(
                str(pricing["effective_price"])
            )
            regular_price = Decimal(
                str(pricing["base_price"])
            )

            if (
                not effective_price.is_finite()
                or not regular_price.is_finite()
                or effective_price < 0
                or regular_price < 0
            ):
                return {
                    "processed": False,
                    "reason": "invalid_price",
                }

            target_price = rule.get("target_price")

            if target_price is not None:
                target = Decimal(str(target_price))

                if (
                    not target.is_finite()
                    or target < 0
                    or effective_price > target
                ):
                    return {
                        "processed": False,
                        "reason": "target_price_not_met",
                    }

            min_discount = rule.get(
                "min_discount_percentage"
            )

            if min_discount is not None:
                minimum_discount = Decimal(
                    str(min_discount)
                )

                if (
                    not minimum_discount.is_finite()
                    or not Decimal("0")
                    <= minimum_discount
                    <= Decimal("100")
                ):
                    return {
                        "processed": False,
                        "reason": "invalid_discount_condition",
                    }

                if regular_price <= 0:
                    return {
                        "processed": False,
                        "reason": "discount_unverifiable",
                    }

                actual_discount = (
                    (regular_price - effective_price)
                    / regular_price
                    * Decimal("100")
                )

                if actual_discount < minimum_discount:
                    return {
                        "processed": False,
                        "reason": "minimum_discount_not_met",
                    }

        except Exception:
            return {
                "processed": False,
                "reason": "price_verification_failed",
            }

        branch_id = rule.get("branch_id")
        idempotency_key = f"smart-cart:{rule['id']}"

        result = self.purchase_direct(
            customer_id=rule["customer_id"],
            variant_id=rule["variant_id"],
            quantity=rule["quantity"],
            idempotency_key=idempotency_key,
            branch_id=branch_id,
            smart_cart_rule_id=rule["id"],
        )

        return {
            "processed": True,
            "rule_id": rule["id"],
            "result": result,
        }
purchase_agent = PurchaseAgent()
