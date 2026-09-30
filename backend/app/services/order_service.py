from fastapi import HTTPException

from app.core.supabase_client import supabase_admin


def get_customer_orders(customer_id: str):
    try:
        orders_response = (
            supabase_admin
            .table("orders")
            .select(
                "id, branch_id, status, subtotal, discount, "
                "total, currency, source, created_at"
            )
            .eq("customer_id", customer_id)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    orders = orders_response.data or []

    if not orders:
        return []

    order_ids = [order["id"] for order in orders]

    try:
        items_response = (
            supabase_admin
            .table("order_items")
            .select(
                "order_id, variant_id, quantity, unit_price, "
                "line_total, product_snapshot"
            )
            .in_("order_id", order_ids)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    items = items_response.data or []

    items_by_order = {}

    for item in items:
        order_id = item["order_id"]

        if order_id not in items_by_order:
            items_by_order[order_id] = []

        items_by_order[order_id].append(
            {
                "variant_id": str(item["variant_id"]),
                "quantity": item["quantity"],
                "unit_price": float(item["unit_price"]),
                "line_total": float(item["line_total"]),
                "product_snapshot": item["product_snapshot"] or {},
            }
        )

    result = []

    for order in orders:
        order_id = order["id"]

        result.append(
            {
                "id": str(order_id),
                "branch_id": (
                    str(order["branch_id"])
                    if order["branch_id"]
                    else None
                ),
                "status": order["status"],
                "subtotal": float(order["subtotal"]),
                "discount": float(order["discount"]),
                "total": float(order["total"]),
                "currency": order["currency"],
                "source": order["source"],
                "created_at": order["created_at"],
                "items": items_by_order.get(order_id, []),
            }
        )

    return result