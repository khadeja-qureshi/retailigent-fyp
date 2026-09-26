from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.supabase_client import supabase_admin
from app.services.pricing_service import get_effective_prices


router = APIRouter(
    prefix="/api/v1/products",
    tags=["Products"],
)


@router.get("")
def list_products(
    gender: Optional[str] = Query(default=None),
    brand: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    min_price: Optional[float] = Query(default=None, ge=0),
    max_price: Optional[float] = Query(default=None, ge=0),
):
    # Get active products
    query = (
        supabase_admin
        .table("products")
        .select("*")
        .eq("is_active", True)
    )

    # Basic product-level filters
    if gender:
        query = query.eq("gender", gender)

    if brand:
        query = query.ilike("brand", brand)

    if min_price is not None:
        query = query.gte("base_price", min_price)

    if max_price is not None:
        query = query.lte("base_price", max_price)

    # Fetch products
    product_response = query.order("name").execute()
    products = product_response.data

    if not products:
        return {
            "products": [],
            "count": 0,
        }

    # Collect category IDs
    category_ids = {
        product["category_id"]
        for product in products
        if product.get("category_id")
    }

    # Fetch categories
    categories = {}

    if category_ids:
        category_response = (
            supabase_admin
            .table("categories")
            .select(
                "id, parent_id, name, slug, description, sort_order"
            )
            .in_("id", list(category_ids))
            .eq("is_active", True)
            .execute()
        )

        categories = {
            category["id"]: category
            for category in category_response.data
        }

    # Collect parent category IDs
    parent_category_ids = {
        category["parent_id"]
        for category in categories.values()
        if category.get("parent_id")
    }

    # Fetch parent categories
    parent_categories = {}

    if parent_category_ids:
        parent_response = (
            supabase_admin
            .table("categories")
            .select(
                "id, parent_id, name, slug, description, sort_order"
            )
            .in_("id", list(parent_category_ids))
            .eq("is_active", True)
            .execute()
        )

        parent_categories = {
            category["id"]: category
            for category in parent_response.data
        }

    # Filter by category name/slug or parent category name/slug
    if category:
        category_lower = category.lower()

        # Categories directly matching the requested category
        matching_category_ids = {
            category_data["id"]
            for category_data in categories.values()
            if (
                category_data["name"].lower() == category_lower
                or category_data["slug"].lower() == category_lower
            )
        }

        # Parent categories matching the requested category
        matching_parent_ids = {
            category_data["id"]
            for category_data in parent_categories.values()
            if (
                category_data["name"].lower() == category_lower
                or category_data["slug"].lower() == category_lower
            )
        }

        # Keep products whose category directly matches
        # OR whose category belongs to a matching parent category
        products = [
            product
            for product in products
            if (
                product.get("category_id") in matching_category_ids
                or categories.get(
                    product.get("category_id"),
                    {},
                ).get("parent_id") in matching_parent_ids
            )
        ]

    # Get images for all remaining products
    product_ids = [
        product["id"]
        for product in products
    ]

    images_by_product = {}

    if product_ids:
        image_response = (
            supabase_admin
            .table("product_images")
            .select(
                "id, product_id, image_url, "
                "alt_text, sort_order, is_primary"
            )
            .in_("product_id", product_ids)
            .order("sort_order")
            .execute()
        )

        for image in image_response.data:
            images_by_product.setdefault(
                image["product_id"],
                [],
            ).append(image)

    # Build catalog response
    for product in products:
        category_data = categories.get(
            product.get("category_id")
        )

        product["category"] = category_data

        if category_data and category_data.get("parent_id"):
            product["parent_category"] = parent_categories.get(
                category_data["parent_id"]
            )
        else:
            product["parent_category"] = None

        product["images"] = images_by_product.get(
            product["id"],
            [],
        )

    return {
        "products": products,
        "count": len(products),
    }


@router.get("/{product_id}")
def get_product(product_id: str):
    # Get product
    product_response = (
        supabase_admin
        .table("products")
        .select("*")
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

    # Get product images
    image_response = (
        supabase_admin
        .table("product_images")
        .select(
            "id, product_id, image_url, "
            "alt_text, sort_order, is_primary"
        )
        .eq("product_id", product_id)
        .order("sort_order")
        .execute()
    )

    product["images"] = image_response.data

    # Get active variants
    variant_response = (
        supabase_admin
        .table("product_variants")
        .select("*")
        .eq("product_id", product_id)
        .eq("is_active", True)
        .order("sku")
        .execute()
    )

    variants = variant_response.data

    # Collect variant IDs
    variant_ids = [
        variant["id"]
        for variant in variants
    ]

    # Get authoritative pricing for all variants
    pricing_by_variant = get_effective_prices(
        variant_ids
    )

    # Collect referenced color and size IDs
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

    # Fetch colors
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

    # Fetch sizes
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

    # Attach color, size, and authoritative pricing
    for variant in variants:
        color_id = variant.get("color_id")
        size_id = variant.get("size_id")

        variant["color"] = colors.get(color_id)
        variant["size"] = sizes.get(size_id)

        variant["pricing"] = pricing_by_variant.get(
            variant["id"]
        )

    # Get inventory for all active variants
    inventory_by_variant = {}

    if variant_ids:
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

        for inventory in inventory_response.data:
            inventory_by_variant.setdefault(
                inventory["variant_id"],
                [],
            ).append(inventory)

        # Collect branch IDs
        branch_ids = {
            inventory["branch_id"]
            for inventory in inventory_response.data
            if inventory.get("branch_id")
        }

        # Fetch active branches
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

        # Attach branch information and stock status
        for inventory_list in inventory_by_variant.values():
            for inventory in inventory_list:
                stock_status_response = supabase_admin.rpc(
                    "get_stock_status",
                    {
                        "p_available_quantity": inventory[
                            "available_quantity"
                        ]
                    },
                ).execute()

                inventory["status"] = stock_status_response.data

                inventory["branch"] = branches.get(
                    inventory["branch_id"]
                )

    # Attach inventory to each variant
    for variant in variants:
        variant["inventory"] = inventory_by_variant.get(
            variant["id"],
            [],
        )

    product["variants"] = variants

    return product