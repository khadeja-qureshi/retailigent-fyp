from app.core.supabase_client import supabase_admin


def get_inventory_row(
    variant_id: str,
    branch_id: str,
):
    response = (
        supabase_admin
        .table("branch_inventory")
        .select(
            "id, branch_id, variant_id, "
            "on_hand_quantity, reserved_quantity, "
            "safety_stock, available_quantity"
        )
        .eq("variant_id", variant_id)
        .eq("branch_id", branch_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]


def get_inventory_snapshot(
    variant_id: str,
):
    response = (
        supabase_admin
        .table("branch_inventory")
        .select(
            "id, branch_id, variant_id, "
            "on_hand_quantity, reserved_quantity, "
            "safety_stock, available_quantity"
        )
        .eq("variant_id", variant_id)
        .order("branch_id")
        .execute()
    )

    return response.data or []