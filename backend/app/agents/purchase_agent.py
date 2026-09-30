from typing import Any

from app.services.purchase_service import (
    convert_customer_reservation_to_purchase,
    execute_customer_purchase,
)


class PurchaseAgent:
    """
    Purchase Agent for Retailigent.

    Responsible for completing customer purchases through the
    deterministic purchase service.

    The agent does not access the database directly. It delegates
    purchase operations to the purchase service.
    """

    def purchase_from_reservation(
        self,
        customer_id: str,
        reservation_id: str,
        idempotency_key: str,
        quantity: int | None = None,
    ) -> dict[str, Any]:
        """
        Convert an existing customer reservation into a purchase.
        """
        return convert_customer_reservation_to_purchase(
            customer_id=customer_id,
            reservation_id=reservation_id,
            idempotency_key=idempotency_key,
            quantity=quantity,
        )

    def purchase_direct(
        self,
        customer_id: str,
        variant_id: str,
        quantity: int,
        idempotency_key: str,
        branch_id: str | None = None,
        smart_cart_rule_id: str | None = None,
    ) -> dict[str, Any]:
        """
       Complete a direct customer purchase.

       The underlying purchase service executes the purchase
       atomically through the deterministic purchase RPC.
        """
        return execute_customer_purchase(
            customer_id=customer_id,
            variant_id=variant_id,
            quantity=quantity,
            idempotency_key=idempotency_key,
            branch_id=branch_id,
            smart_cart_rule_id=smart_cart_rule_id,
        )


purchase_agent = PurchaseAgent()