from app.core.supabase_client import supabase_admin
from app.services.embedding_service import generate_embedding
from app.services.pricing_service import get_effective_prices


DEFAULT_MATCH_COUNT = 10
DEFAULT_KEYWORD_WEIGHT = 0.35
DEFAULT_SEMANTIC_WEIGHT = 0.65


def search_variants(
    query: str,
    match_count: int = DEFAULT_MATCH_COUNT,
    keyword_weight: float = DEFAULT_KEYWORD_WEIGHT,
    semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
) -> list[dict]:
    """
    Perform hybrid keyword + semantic search and enrich
    results with product, variant, color, size, pricing,
    image, branch, and inventory information.
    """

    if not query or not query.strip():
        return []

    query = query.strip()

    # ---------------------------------------------------------
    # 1. Generate query embedding
    # ---------------------------------------------------------
    query_embedding = generate_embedding(query)

    # ---------------------------------------------------------
    # 2. Run hybrid search
    # ---------------------------------------------------------
    response = supabase_admin.rpc(
        "search_variants_hybrid",
        {
            "query_text": query,
            "query_embedding": query_embedding,
            "match_count": match_count,
            "keyword_weight": keyword_weight,
            "semantic_weight": semantic_weight,
        },
    ).execute()

    search_results = response.data or []

    if not search_results:
        return []

    # ---------------------------------------------------------
    # 3. Collect IDs
    # ---------------------------------------------------------
    variant_ids = {
        result["variant_id"]
        for result in search_results
    }

    product_ids = {
        result["product_id"]
        for result in search_results
    }

    # ---------------------------------------------------------
    # 3.5 Fetch authoritative pricing for all variants
    # ---------------------------------------------------------
    pricing_by_variant = get_effective_prices(
        list(variant_ids)
    )

    # ---------------------------------------------------------
    # 4. Fetch products
    # ---------------------------------------------------------
    product_response = (
        supabase_admin
        .table("products")
        .select(
            "id, category_id, name, slug, sku, description, "
            "brand, gender, material, base_price, attributes"
        )
        .in_("id", list(product_ids))
        .eq("is_active", True)
        .execute()
    )

    products = {
        product["id"]: product
        for product in product_response.data
    }

    # ---------------------------------------------------------
    # 5. Fetch variants
    # ---------------------------------------------------------
    variant_response = (
        supabase_admin
        .table("product_variants")
        .select(
            "id, product_id, color_id, size_id, sku, "
            "price, barcode, attributes"
        )
        .in_("id", list(variant_ids))
        .eq("is_active", True)
        .execute()
    )

    variants = {
        variant["id"]: variant
        for variant in variant_response.data
    }

    # ---------------------------------------------------------
    # 6. Fetch colors
    # ---------------------------------------------------------
    color_ids = {
        variant["color_id"]
        for variant in variants.values()
        if variant.get("color_id")
    }

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

    # ---------------------------------------------------------
    # 7. Fetch sizes
    # ---------------------------------------------------------
    size_ids = {
        variant["size_id"]
        for variant in variants.values()
        if variant.get("size_id")
    }

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

    # ---------------------------------------------------------
    # 8. Fetch product images
    # ---------------------------------------------------------
    image_response = (
        supabase_admin
        .table("product_images")
        .select(
            "id, product_id, image_url, alt_text, "
            "sort_order, is_primary"
        )
        .in_("product_id", list(product_ids))
        .order("sort_order")
        .execute()
    )

    images_by_product = {}

    for image in image_response.data:
        images_by_product.setdefault(
            image["product_id"],
            []
        ).append(image)

    # ---------------------------------------------------------
    # 9. Fetch inventory
    # ---------------------------------------------------------
    inventory_response = (
        supabase_admin
        .table("branch_inventory")
        .select(
            "id, branch_id, variant_id, "
            "on_hand_quantity, reserved_quantity, "
            "safety_stock, available_quantity"
        )
        .in_("variant_id", list(variant_ids))
        .execute()
    )

    inventory_by_variant = {}

    # ---------------------------------------------------------
    # 10. Fetch branches
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # 11. Attach authoritative stock status and branch
    # ---------------------------------------------------------
    for inventory in inventory_response.data:

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

        inventory_by_variant.setdefault(
            inventory["variant_id"],
            []
        ).append(inventory)

    # ---------------------------------------------------------
    # 12. Build enriched results
    # ---------------------------------------------------------
    enriched_results = []

    for result in search_results:

        variant_id = result["variant_id"]
        product_id = result["product_id"]

        product = products.get(product_id)
        variant = variants.get(variant_id)

        if not product or not variant:
            continue

        enriched_results.append(
            {
                "variant_id": variant_id,
                "product_id": product_id,

                "score": {
                    "combined": result["combined_score"],
                    "keyword": result["keyword_score"],
                    "semantic": result["semantic_score"],
                },

                "product": product,

                "variant": {
                    **variant,
                    "color": colors.get(
                        variant.get("color_id")
                    ),
                    "size": sizes.get(
                        variant.get("size_id")
                    ),
                },

                "pricing": pricing_by_variant.get(
                    variant_id
                ),

                "images": images_by_product.get(
                    product_id,
                    []
                ),

                "inventory": inventory_by_variant.get(
                    variant_id,
                    [],
                ),
            }
        )

    return enriched_results