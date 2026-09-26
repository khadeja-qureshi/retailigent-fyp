from fastapi import APIRouter, HTTPException, Query

from app.core.supabase_client import supabase_admin

router = APIRouter(
    prefix="/api/v1/inventory",
    tags=["Inventory"],
)

@router.get("/variant/{variant_id}")
def get_variant_inventory(
    variant_id: str,
    branch_id: str | None = Query(default=None),
):
    query = (
        supabase_admin
        .table("branch_inventory")
        .select(
            "id, branch_id, variant_id, "
            "on_hand_quantity, reserved_quantity, "
            "safety_stock, available_quantity"
        )
        .eq("variant_id", variant_id)
    )

    if branch_id:
        query = query.eq("branch_id", branch_id)

    inventory_response = query.execute()

    if not inventory_response.data:
        raise HTTPException(
            status_code=404,
            detail="Inventory not found for this variant",
        )

    inventory = inventory_response.data

    branch_ids = {
        item["branch_id"]
        for item in inventory
        if item.get("branch_id")
    }

    branches = {}

    if branch_ids:
        branch_response = (
            supabase_admin
            .table("branches")
            .select(
                "id, name, city, area, address, "
                "latitude, longitude, phone, "
                "opening_time, closing_time"
            )
            .in_("id", list(branch_ids))
            .eq("is_active", True)
            .execute()
        )

        branches = {
            branch["id"]: branch
            for branch in branch_response.data
        }

    for item in inventory:
        stock_status_response = supabase_admin.rpc(
            "get_stock_status",
            {
                "p_available_quantity": item["available_quantity"]
            },
        ).execute()

        item["status"] = stock_status_response.data
        item["branch"] = branches.get(item["branch_id"])

    return {
        "variant_id": variant_id,
        "inventory": inventory,
        "count": len(inventory),
    }

@router.get("/product/{product_id}")
def get_product_inventory(product_id: str):
    # Verify product exists and is active
    product_response = (
        supabase_admin
        .table("products")
        .select("id, name, sku")
        .eq("id", product_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not product_response.data:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    product = product_response.data[0]

    # Get active variants
    variant_response = (
        supabase_admin
        .table("product_variants")
        .select(
            "id, product_id, color_id, size_id, "
            "sku, price, barcode, attributes"
        )
        .eq("product_id", product_id)
        .eq("is_active", True)
        .order("sku")
        .execute()
    )

    variants = variant_response.data

    if not variants:
        return {
            "product": product,
            "variants": [],
            "count": 0,
        }

    # Collect color and size IDs
    color_ids = {
        variant["color_id"]
        for variant in variants
        if variant.get("color_id")
    }

    size_ids = {
        variant["size_id"]
        for variant in variants
        if variant.get("size_id")
    }

    # Get colors
    colors = {}

    if color_ids:
        color_response = (
            supabase_admin
            .table("colors")
            .select("id, name, hex_code")
            .in_("id", list(color_ids))
            .eq("is_active", True)
            .execute()
        )

        colors = {
            color["id"]: color
            for color in color_response.data
        }

    # Get sizes
    sizes = {}

    if size_ids:
        size_response = (
            supabase_admin
            .table("sizes")
            .select("id, name, size_group")
            .in_("id", list(size_ids))
            .eq("is_active", True)
            .execute()
        )

        sizes = {
            size["id"]: size
            for size in size_response.data
        }

    # Get inventory
    variant_ids = [variant["id"] for variant in variants]

    inventory_response = (
        supabase_admin
        .table("branch_inventory")
        .select(
            "id, branch_id, variant_id, "
            "on_hand_quantity, reserved_quantity, "
            "safety_stock, available_quantity"
        )
        .in_("variant_id", variant_ids)
        .execute()
    )

    inventory_by_variant = {}

    for inventory in inventory_response.data:
        inventory_by_variant.setdefault(
            inventory["variant_id"],
            []
        ).append(inventory)

    # Get branches
    branch_ids = {
        inventory["branch_id"]
        for inventory in inventory_response.data
        if inventory.get("branch_id")
    }

    branches = {}

    if branch_ids:
        branch_response = (
            supabase_admin
            .table("branches")
            .select(
                "id, name, city, area, address, "
                "latitude, longitude, phone, "
                "opening_time, closing_time"
            )
            .in_("id", list(branch_ids))
            .eq("is_active", True)
            .execute()
        )

        branches = {
            branch["id"]: branch
            for branch in branch_response.data
        }

    # Build variant inventory response
    for variant in variants:
        variant["color"] = colors.get(variant.get("color_id"))
        variant["size"] = sizes.get(variant.get("size_id"))

        variant_inventory = inventory_by_variant.get(
            variant["id"],
            []
        )

        for inventory in variant_inventory:
            stock_status_response = supabase_admin.rpc(
                "get_stock_status",
                {
                    "p_available_quantity": inventory["available_quantity"]
                },
            ).execute()

            inventory["status"] = stock_status_response.data
            inventory["branch"] = branches.get(
                inventory["branch_id"]
            )

        variant["inventory"] = variant_inventory

    return {
        "product": product,
        "variants": variants,
        "count": len(variants),
    }
@router.get("/variant/{variant_id}/status")
def get_variant_stock_status(
    variant_id: str,
    branch_id: str | None = Query(default=None),
):
    query = (
        supabase_admin
        .table("branch_inventory")
        .select(
            "variant_id, branch_id, available_quantity"
        )
        .eq("variant_id", variant_id)
    )

    if branch_id:
        query = query.eq("branch_id", branch_id)

    inventory_response = query.execute()

    if not inventory_response.data:
        raise HTTPException(
            status_code=404,
            detail="Inventory not found for this variant",
        )

    results = []

    for inventory in inventory_response.data:
        stock_status_response = supabase_admin.rpc(
            "get_stock_status",
            {
                "p_available_quantity": inventory["available_quantity"]
            },
        ).execute()

        results.append(
            {
                "variant_id": inventory["variant_id"],
                "branch_id": inventory["branch_id"],
                "available_quantity": inventory["available_quantity"],
                "status": stock_status_response.data,
            }
        )

    return {
        "variant_id": variant_id,
        "stock": results,
        "count": len(results),
    }