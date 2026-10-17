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

def get_inventory_snapshot_enriched(
    variant_id: str,
):
    """
    Return authoritative inventory for a variant,
    enriched with active branch information and the
    database-defined stock status.
    """

    inventory = get_inventory_snapshot(
        variant_id
    )

    if not inventory:
        return []

    branch_ids = {
        row["branch_id"]
        for row in inventory
        if row.get("branch_id")
    }

    branches = {}

    if branch_ids:
        branch_response = (
            supabase_admin
            .table("branches")
            .select(
                "id, name, city, area, address"
            )
            .in_(
                "id",
                list(branch_ids),
            )
            .eq(
                "is_active",
                True,
            )
            .execute()
        )

        branches = {
            row["id"]: row
            for row in (
                branch_response.data
                or []
            )
        }

    result = []

    for row in inventory:
        branch = branches.get(
            row["branch_id"]
        )

        # Do not expose inventory from
        # inactive/missing branches.
        if not branch:
            continue

        status_response = (
            supabase_admin
            .rpc(
                "get_stock_status",
                {
                    "p_available_quantity":
                        row[
                            "available_quantity"
                        ],
                },
            )
            .execute()
        )

        result.append(
            {
                **row,
                "branch": branch,
                "status":
                    status_response.data,
            }
        )

    return result