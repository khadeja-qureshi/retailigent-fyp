from typing import Any

from app.services.inventory_service import (
    get_inventory_row,
    get_inventory_snapshot,
)


class InventoryAgent:
    """
    Inventory Agent for Retailigent.

    Responsible for checking exact product-variant availability
    at individual branches or across all branches.

    The agent does not access the database directly. It delegates
    inventory reads to the existing inventory service.
    """

    def get_branch_stock(
        self,
        variant_id: str,
        branch_id: str,
    ) -> dict[str, Any] | None:
        """
        Get inventory for a specific variant at a specific branch.
        """
        return get_inventory_row(
            variant_id=variant_id,
            branch_id=branch_id,
        )

    def get_stock_snapshot(
        self,
        variant_id: str,
    ) -> list[dict[str, Any]]:
        """
        Get inventory for a variant across all branches.
        """
        return get_inventory_snapshot(
            variant_id=variant_id,
        )


inventory_agent = InventoryAgent()
