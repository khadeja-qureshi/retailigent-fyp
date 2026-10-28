from __future__ import annotations

from typing import Any

from app.core.supabase_client import supabase_admin
from app.services.embedding_service import generate_embedding
from app.services.pricing_service import get_effective_prices


DEFAULT_MATCH_COUNT = 10
DEFAULT_KEYWORD_WEIGHT = 0.35
DEFAULT_SEMANTIC_WEIGHT = 0.65


def _normalize_tokens(value: str) -> set[str]:
    text = (
        str(value or "")
        .strip()
        .lower()
        .replace("-", " ")
        .replace("_", " ")
    )

    tokens: set[str] = set()

    for raw in text.split():
        token = raw.strip()

        if not token:
            continue

        tokens.add(token)

        if (
            len(token) > 4
            and token.endswith("ies")
        ):
            tokens.add(
                token[:-3] + "y"
            )

        elif (
            len(token) > 3
            and token.endswith("s")
            and not token.endswith("ss")
        ):
            tokens.add(
                token[:-1]
            )

    return tokens


def _category_matches_request(
    requested: str,
    *,
    name: str,
    slug: str,
) -> bool:
    requested_tokens = _normalize_tokens(
        requested
    )

    if not requested_tokens:
        return True

    candidate_tokens = (
        _normalize_tokens(name)
        |
        _normalize_tokens(slug)
    )

    return requested_tokens.issubset(
        candidate_tokens
    )


def _fetch_active_categories() -> list[dict[str, Any]]:
    response = (
        supabase_admin
        .table("categories")
        .select(
            "id, name, slug, parent_id, sort_order"
        )
        .eq("is_active", True)
        .execute()
    )

    return response.data or []


def get_active_product_categories() -> list[str]:
    """
    Return active category names that contain active products.

    Category names and ordering come from the database, not a
    hardcoded catalog list.
    """
    product_response = (
        supabase_admin
        .table("products")
        .select("category_id")
        .eq("is_active", True)
        .execute()
    )

    product_category_ids = {
        str(product.get("category_id"))
        for product in (product_response.data or [])
        if product.get("category_id")
    }

    if not product_category_ids:
        return []

    categories = _fetch_active_categories()

    matching_categories = [
        category
        for category in categories
        if str(category.get("id") or "")
        in product_category_ids
        and str(category.get("name") or "").strip()
    ]

    matching_categories.sort(
        key=lambda category: (
            category.get("sort_order")
            if isinstance(category.get("sort_order"), (int, float))
            else 0,
            str(category.get("name") or "").casefold(),
        )
    )

    return list(
        dict.fromkeys(
            str(category["name"]).strip()
            for category in matching_categories
        )
    )


def _resolve_category_ids(
    requested_category: str,
) -> set[str]:
    """
    Resolve a requested category to all matching active category IDs,
    including descendants.

    Examples:
      footwear -> footwear, footwear-men, footwear-women,
                  footwear-shoes, footwear-slippers, ...

      footwear-shoes -> only that subtree
    """

    categories = _fetch_active_categories()

    if not categories:
        return set()

    matched: set[str] = {
        str(category["id"])
        for category in categories
        if _category_matches_request(
            requested_category,
            name=str(
                category.get("name")
                or ""
            ),
            slug=str(
                category.get("slug")
                or ""
            ),
        )
    }

    if not matched:
        return set()

    # Include every active descendant of every directly matched category.
    changed = True

    while changed:
        changed = False

        for category in categories:
            category_id = str(
                category.get("id")
                or ""
            )
            parent_id = str(
                category.get("parent_id")
                or ""
            )

            if (
                category_id
                and parent_id in matched
                and category_id not in matched
            ):
                matched.add(category_id)
                changed = True

    return matched


def _query_relevance(
    query: str,
    product_name: str,
    category_name: str,
    category_slug: str,
) -> float:
    query_tokens = _normalize_tokens(
        query
    )

    # Remove generic shopping words so "show me sneakers" ranks
    # using "sneaker" rather than "show" / "me".
    query_tokens -= {
        "show",
        "me",
        "find",
        "need",
        "want",
        "give",
        "some",
        "product",
        "products",
        "item",
        "items",
    }

    candidate_tokens = (
        _normalize_tokens(product_name)
        |
        _normalize_tokens(category_name)
        |
        _normalize_tokens(category_slug)
    )

    if not query_tokens:
        return 0.5

    overlap = len(
        query_tokens
        & candidate_tokens
    )

    return overlap / len(
        query_tokens
    )


def _enrich_search_matches(
    search_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Enrich variant/product IDs with authoritative catalog data."""

    if not search_results:
        return []

    variant_ids = {
        str(result["variant_id"])
        for result in search_results
        if result.get("variant_id")
    }

    product_ids = {
        str(result["product_id"])
        for result in search_results
        if result.get("product_id")
    }

    if not variant_ids or not product_ids:
        return []

    pricing_by_variant = get_effective_prices(
        list(variant_ids)
    )

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
        str(product["id"]): product
        for product in (
            product_response.data
            or []
        )
    }

    category_ids = {
        str(product["category_id"])
        for product in products.values()
        if product.get("category_id")
    }

    categories: dict[str, dict[str, Any]] = {}

    if category_ids:
        category_response = (
            supabase_admin
            .table("categories")
            .select(
                "id, name, slug, parent_id"
            )
            .in_("id", list(category_ids))
            .eq("is_active", True)
            .execute()
        )

        categories = {
            str(category["id"]): category
            for category in (
                category_response.data
                or []
            )
        }

    for product in products.values():
        category_id = product.get(
            "category_id"
        )

        product["category"] = (
            categories.get(
                str(category_id)
            )
            if category_id
            else None
        )

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
        str(variant["id"]): variant
        for variant in (
            variant_response.data
            or []
        )
    }

    color_ids = {
        str(variant["color_id"])
        for variant in variants.values()
        if variant.get("color_id")
    }

    colors: dict[str, dict[str, Any]] = {}

    if color_ids:
        color_response = (
            supabase_admin
            .table("colors")
            .select(
                "id, name, hex_code"
            )
            .in_("id", list(color_ids))
            .eq("is_active", True)
            .execute()
        )

        colors = {
            str(color["id"]): color
            for color in (
                color_response.data
                or []
            )
        }

    size_ids = {
        str(variant["size_id"])
        for variant in variants.values()
        if variant.get("size_id")
    }

    sizes: dict[str, dict[str, Any]] = {}

    if size_ids:
        size_response = (
            supabase_admin
            .table("sizes")
            .select(
                "id, name, size_group"
            )
            .in_("id", list(size_ids))
            .eq("is_active", True)
            .execute()
        )

        sizes = {
            str(size["id"]): size
            for size in (
                size_response.data
                or []
            )
        }

    image_response = (
        supabase_admin
        .table("product_images")
        .select(
            "id, product_id, variant_id, image_url, alt_text, "
            "sort_order, is_primary"
        )
        .in_("product_id", list(product_ids))
        .order("sort_order")
        .execute()
    )

    images_by_variant: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    images_without_variant_by_product: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for image in (
        image_response.data
        or []
    ):
        product_id_for_image = str(image["product_id"])
        variant_id_for_image = image.get("variant_id")

        if variant_id_for_image:
            images_by_variant.setdefault(
                str(variant_id_for_image),
                [],
            ).append(image)
        else:
            images_without_variant_by_product.setdefault(
                product_id_for_image,
                [],
            ).append(image)

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

    inventory_rows = (
        inventory_response.data
        or []
    )

    branch_ids = {
        str(inventory["branch_id"])
        for inventory in inventory_rows
        if inventory.get("branch_id")
    }

    branches: dict[str, dict[str, Any]] = {}

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
            str(branch["id"]): branch
            for branch in (
                branch_response.data
                or []
            )
        }

    inventory_by_variant: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for inventory in inventory_rows:
        stock_status_response = (
            supabase_admin.rpc(
                "get_stock_status",
                {
                    "p_available_quantity": (
                        inventory[
                            "available_quantity"
                        ]
                    )
                },
            ).execute()
        )

        inventory["status"] = (
            stock_status_response.data
        )

        inventory["branch"] = (
            branches.get(
                str(
                    inventory[
                        "branch_id"
                    ]
                )
            )
        )

        inventory_by_variant.setdefault(
            str(
                inventory[
                    "variant_id"
                ]
            ),
            [],
        ).append(inventory)

    enriched_results: list[
        dict[str, Any]
    ] = []

    for result in search_results:
        variant_id = str(
            result.get("variant_id")
            or ""
        )
        product_id = str(
            result.get("product_id")
            or ""
        )

        product = products.get(
            product_id
        )
        variant = variants.get(
            variant_id
        )

        if not product or not variant:
            continue

        enriched_results.append(
            {
                "variant_id": variant_id,
                "product_id": product_id,
                "score": {
                    "combined": float(
                        result.get(
                            "combined_score"
                        )
                        or 0.0
                    ),
                    "keyword": float(
                        result.get(
                            "keyword_score"
                        )
                        or 0.0
                    ),
                    "semantic": float(
                        result.get(
                            "semantic_score"
                        )
                        or 0.0
                    ),
                },
                "product": product,
                "variant": {
                    **variant,
                    "color": colors.get(
                        str(
                            variant.get(
                                "color_id"
                            )
                            or ""
                        )
                    ),
                    "size": sizes.get(
                        str(
                            variant.get(
                                "size_id"
                            )
                            or ""
                        )
                    ),
                },
                "pricing": (
                    pricing_by_variant.get(
                        variant_id
                    )
                ),
                "images": (
                    images_by_variant.get(
                        variant_id,
                    )
                    or images_without_variant_by_product.get(
                        product_id,
                        [],
                    )
                ),
                "inventory": (
                    inventory_by_variant.get(
                        variant_id,
                        [],
                    )
                ),
            }
        )

    return enriched_results


def search_variants(
    query: str,
    match_count: int = DEFAULT_MATCH_COUNT,
    keyword_weight: float = DEFAULT_KEYWORD_WEIGHT,
    semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
) -> list[dict[str, Any]]:
    """Perform the existing hybrid keyword + semantic search."""

    if not query or not query.strip():
        return []

    query = query.strip()
    query_embedding = generate_embedding(query)

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

    return _enrich_search_matches(
        response.data or []
    )


def search_all_active_variants() -> list[dict[str, Any]]:
    """
    Retrieve active variants across the complete active product catalog.

    This browse path deliberately avoids embeddings and semantic ranking.
    Database enrichment remains responsible for authoritative product,
    variant, category, pricing, inventory, and image data.
    """
    page_size = 500

    def fetch_active_rows(
        table_name: str,
        columns: str,
        product_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0

        while True:
            query = (
                supabase_admin
                .table(table_name)
                .select(columns)
                .eq("is_active", True)
            )

            if product_ids is not None:
                query = query.in_("product_id", product_ids)

            response = (
                query
                .range(offset, offset + page_size - 1)
                .execute()
            )
            page = response.data or []
            rows.extend(page)

            if len(page) < page_size:
                break

            offset += page_size

        return rows

    products = fetch_active_rows(
        "products",
        "id",
    )
    product_ids = sorted({
        str(product["id"])
        for product in products
        if product.get("id")
    })

    if not product_ids:
        return []

    variants = fetch_active_rows(
        "product_variants",
        "id, product_id",
        product_ids,
    )

    matches = [
        {
            "variant_id": str(variant["id"]),
            "product_id": str(variant["product_id"]),
            "combined_score": 0.0,
            "keyword_score": 0.0,
            "semantic_score": 0.0,
        }
        for variant in variants
        if variant.get("id") and variant.get("product_id")
    ]

    matches.sort(
        key=lambda item: (
            item["product_id"],
            item["variant_id"],
        )
    )

    return _enrich_search_matches(matches)


def search_variants_by_category(
    *,
    category: str,
    query: str,
    match_count: int = 100,
) -> list[dict[str, Any]]:
    """
    Deterministic catalog fallback for hard category requests.

    It does NOT depend on product embeddings. This is important for newly
    inserted products whose embeddings are missing or have not yet been
    regenerated.
    """

    if not category or not category.strip():
        return []

    category_ids = _resolve_category_ids(
        category.strip()
    )

    if not category_ids:
        return []

    product_response = (
        supabase_admin
        .table("products")
        .select(
            "id, category_id, name"
        )
        .in_(
            "category_id",
            list(category_ids),
        )
        .eq("is_active", True)
        .execute()
    )

    products = (
        product_response.data
        or []
    )

    if not products:
        return []

    product_ids = [
        str(product["id"])
        for product in products
        if product.get("id")
    ]

    if not product_ids:
        return []

    # Fetch category metadata once for relevance scoring.
    categories = {
        str(category_row["id"]): category_row
        for category_row in _fetch_active_categories()
    }

    product_score: dict[str, float] = {}

    for product in products:
        product_id = str(
            product.get("id")
            or ""
        )
        category_row = categories.get(
            str(
                product.get(
                    "category_id"
                )
                or ""
            ),
            {},
        )

        product_score[product_id] = (
            _query_relevance(
                query,
                str(
                    product.get("name")
                    or ""
                ),
                str(
                    category_row.get("name")
                    or ""
                ),
                str(
                    category_row.get("slug")
                    or ""
                ),
            )
        )

    variant_response = (
        supabase_admin
        .table("product_variants")
        .select(
            "id, product_id"
        )
        .in_(
            "product_id",
            product_ids,
        )
        .eq("is_active", True)
        .execute()
    )

    matches: list[
        dict[str, Any]
    ] = []

    for variant in (
        variant_response.data
        or []
    ):
        product_id = str(
            variant.get("product_id")
            or ""
        )
        score = product_score.get(
            product_id,
            0.0,
        )

        matches.append(
            {
                "variant_id": str(
                    variant["id"]
                ),
                "product_id": product_id,
                "combined_score": score,
                "keyword_score": score,
                "semantic_score": 0.0,
            }
        )

    matches.sort(
        key=lambda item: (
            -float(
                item.get(
                    "combined_score"
                )
                or 0.0
            ),
            str(
                item.get("product_id")
                or ""
            ),
            str(
                item.get("variant_id")
                or ""
            ),
        )
    )

    # Keep a wider pool for downstream color/size/price filtering.
    return _enrich_search_matches(
        matches[: max(match_count, 100)]
    )
