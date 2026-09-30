from typing import Any


class StockStatusBlock:
    """
    UI block for displaying stock availability information.

    The block only formats inventory data returned by the Inventory
    or Product Agent. It does not perform database queries or
    business logic.
    """

    type = "stock_status"

    @staticmethod
    def build(
        inventory: list[dict[str, Any]],
    ) -> dict[str, Any]:
        branches = []

        for row in inventory:
            branch = row.get("branch") or {}

            available_quantity = int(
                row.get("available_quantity") or 0
            )

            status = row.get("status")

            branches.append(
                {
                    "branch_id": row.get("branch_id"),
                    "branch_name": branch.get("name"),
                    "city": branch.get("city"),
                    "area": branch.get("area"),
                    "address": branch.get("address"),
                    "available_quantity": available_quantity,
                    "status": status,
                }
            )

        total_available = sum(
            branch["available_quantity"]
            for branch in branches
        )

        return {
            "type": StockStatusBlock.type,
            "total_available": total_available,
            "has_stock": total_available > 0,
            "branches": branches,
        }
