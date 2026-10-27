from typing import Any, Optional

from app.services.search_service import (
    search_variants,
    search_variants_by_category,
)
from app.services.demand_signal_service import record_demand_signal


def _normalize_category_tokens(
    value: str,
) -> set[str]:
    """
    Normalize natural-language category terms.

    Examples:
    - "kurta" -> {"kurta"}
    - "Kurtas" -> {"kurtas", "kurta"}
    - "Casual Shirts" ->
      {"casual", "shirts", "shirt"}
    - "test-men-kurtas" ->
      {"test", "men", "kurtas", "kurta"}
    """
    text = (
        str(value or "")
        .strip()
        .lower()
        .replace("-", " ")
        .replace("_", " ")
    )

    tokens: set[str] = set()

    for raw_token in text.split():
        token = raw_token.strip()

        if not token:
            continue

        tokens.add(token)

        # Basic English plural normalization.
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


def _category_matches(
    requested: str,
    category_name: str,
    category_slug: str,
) -> bool:
    requested_tokens = (
        _normalize_category_tokens(
            requested
        )
    )

    candidate_tokens = (
        _normalize_category_tokens(
            category_name
        )
        |
        _normalize_category_tokens(
            category_slug
        )
    )

    if not requested_tokens:
        return True

    return requested_tokens.issubset(
        candidate_tokens
    )


def _diversify_results_by_product(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Round-robin variants across distinct products.

    Broad category browsing can otherwise be dominated by many size/color
    variants of the same product.  This keeps the original relevance order
    within each product while ensuring different products are represented
    early in the carousel.
    """

    if not results:
        return []

    groups: dict[str, list[dict[str, Any]]] = {}
    product_order: list[str] = []

    for index, result in enumerate(results):
        product_id = str(
            result.get("product_id")
            or (result.get("product") or {}).get("id")
            or f"__missing_product_{index}"
        )

        if product_id not in groups:
            groups[product_id] = []
            product_order.append(product_id)

        groups[product_id].append(result)

    diversified: list[dict[str, Any]] = []
    depth = 0

    while True:
        added_any = False

        for product_id in product_order:
            variants = groups[product_id]

            if depth < len(variants):
                diversified.append(variants[depth])
                added_any = True

        if not added_any:
            break

        depth += 1

    return diversified


class ProductAgent:
    """
    Product Agent for Retailigent.

    Combines hybrid semantic/keyword retrieval with deterministic
    structured filtering.

    Semantic search is handled by the existing search_service and
    embedding pipeline. Structured constraints are applied after
    retrieval so correctness-sensitive attributes such as color,
    size, price, and branch/city are not left to semantic similarity.
    """

    def search(
        self,
        query: str,
        match_count: int = 10,
        color: Optional[str] = None,
        size: Optional[str] = None,
        city: Optional[str] = None,
        material: Optional[str] = None,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        track_demand: bool = False,
        customer_id: Optional[str] = None,
        branch_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Search products using hybrid semantic/keyword retrieval and
        optional structured filters.

        Args:
            query: Natural-language product search query.
            match_count: Maximum number of results requested.
            color: Exact color name.
            size: Exact size name.
            city: Exact branch city.
            material: Product material/fabric.
            category: Product category name.
            min_price: Minimum effective price.
            max_price: Maximum effective price.

        Returns:
            Filtered and enriched product/variant results.
        """

        if not query or not query.strip():
            return []

        normalized_query = query.strip()

        # Structured constraints are correctness gates, not ranking hints.
        # Retrieve a wider candidate pool whenever a hard filter is present
        # so recently-added products (for example footwear whose embeddings
        # have not yet ranked into the top 10) are not lost before the
        # deterministic filtering step below.
        has_hard_filter = any(
            value is not None
            for value in (
                color,
                size,
                city,
                material,
                category,
                min_price,
                max_price,
            )
        )

        retrieval_count = (
            max(match_count, 100)
            if has_hard_filter
            else match_count
        )

        results = search_variants(
            query=normalized_query,
            match_count=retrieval_count,
        )

        # ---------------------------------------------------------
        # Deterministic category fallback
        # ---------------------------------------------------------
        #
        # Hybrid search can miss newly inserted catalog rows when
        # their embeddings are absent or stale.  A category supplied
        # by the parser is a hard constraint, so we also fetch the
        # active category subtree directly from PostgreSQL and merge
        # those variants into the candidate pool.
        #
        # Example:
        #   category="footwear"
        # includes child categories such as:
        #   footwear-shoes
        #   footwear-slippers
        #   footwear-khussa
        #   footwear-heels
        #
        if category:
            category_results = (
                search_variants_by_category(
                    category=category,
                    query=normalized_query,
                    match_count=retrieval_count,
                )
            )

            merged_by_variant: dict[
                str,
                dict[str, Any],
            ] = {}

            # Category-derived rows are deterministic hard-category
            # candidates and therefore take precedence when duplicate
            # variants also appear in semantic search.
            for result in category_results:
                variant_id = str(
                    result.get("variant_id")
                    or ""
                )

                if variant_id:
                    merged_by_variant[
                        variant_id
                    ] = result

            for result in results:
                variant_id = str(
                    result.get("variant_id")
                    or ""
                )

                if (
                    variant_id
                    and variant_id
                    not in merged_by_variant
                ):
                    merged_by_variant[
                        variant_id
                    ] = result

            results = list(
                merged_by_variant.values()
            )

            # Preserve relevance ordering from the category fallback.
            results.sort(
                key=lambda result: -float(
                    (
                        result.get("score")
                        or {}
                    ).get(
                        "combined"
                    )
                    or 0.0
                )
            )

        if not results:
            if track_demand:
                record_demand_signal(
                    signal_type="no_catalog_match",
                    customer_id=customer_id,
                    branch_id=branch_id,
                    requested_size=size,
                    requested_color=color,
                    metadata={"query": normalized_query},
                )
            return []

        filtered_results = []

        for result in results:
            product = (
                result.get("product")
                or {}
            )

            variant = (
                result.get("variant")
                or {}
            )

            variant_color = (
                variant.get("color")
                or {}
            )

            variant_size = (
                variant.get("size")
                or {}
            )

            pricing = (
                result.get("pricing")
                or {}
            )

            inventory = (
                result.get("inventory")
                or []
            )

            # ---------------------------------------------------------
            # Color filter
            # ---------------------------------------------------------
            if color:
                actual_color = str(
                    variant_color.get("name")
                    or ""
                ).strip().lower()

                if (
                    actual_color
                    != color.strip().lower()
                ):
                    continue

            # ---------------------------------------------------------
            # Size filter
            # ---------------------------------------------------------
            if size:
                actual_size = str(
                    variant_size.get("name")
                    or ""
                ).strip().lower()

                if (
                    actual_size
                    != size.strip().lower()
                ):
                    continue

            # ---------------------------------------------------------
            # Material filter
            # ---------------------------------------------------------
            if material:
                actual_material = str(
                    product.get("material")
                    or ""
                ).strip().lower()

                if (
                    actual_material
                    != material.strip().lower()
                ):
                    continue

            # ---------------------------------------------------------
            # Category filter
            # ---------------------------------------------------------
            if category:
                category_data = (
                    product.get("category")
                    or {}
                )

                category_name = str(
                    category_data.get("name")
                    or ""
                )

                category_slug = str(
                    category_data.get("slug")
                    or ""
                )

                if not _category_matches(
                    category,
                    category_name,
                    category_slug,
                ):
                    continue

            # ---------------------------------------------------------
            # Price filters
            # ---------------------------------------------------------
            effective_price = (
                pricing.get(
                    "effective_price"
                )
            )

            if effective_price is None:
                effective_price = (
                    variant.get("price")
                )

            if effective_price is not None:
                effective_price = float(
                    effective_price
                )

                if (
                    min_price is not None
                    and effective_price
                    < min_price
                ):
                    continue

                if (
                    max_price is not None
                    and effective_price
                    > max_price
                ):
                    continue

            elif (
                min_price is not None
                or max_price is not None
            ):
                # A price constraint is a hard correctness gate.  If an
                # authoritative price cannot be resolved, do not include the
                # variant as though it satisfied the customer's budget.
                continue

            # ---------------------------------------------------------
            # City filter
            # ---------------------------------------------------------
            if city:
                requested_city = (
                    city.strip().lower()
                )

                matching_city = False

                for inventory_row in inventory:
                    branch = (
                        inventory_row.get(
                            "branch"
                        )
                        or {}
                    )

                    branch_city = str(
                        branch.get("city")
                        or ""
                    ).strip().lower()

                    if (
                        branch_city
                        == requested_city
                    ):
                        matching_city = True
                        break

                if not matching_city:
                    continue

            filtered_results.append(
                result
            )

        if not filtered_results and track_demand:
            # Attribute the signal to a real candidate only when its
            # identifiers are available. Requested attributes and
            # candidate_count remain the primary evidence of unmet demand.
            candidate = results[0]

            record_demand_signal(
                signal_type="requested_variant_unavailable",
                customer_id=customer_id,
                product_id=candidate.get("product_id"),
                variant_id=candidate.get("variant_id"),
                branch_id=branch_id,
                requested_size=size,
                requested_color=color,
                metadata={
                    "query": normalized_query,
                    "requested_material": material,
                    "requested_category": category,
                    "min_price": min_price,
                    "max_price": max_price,
                    "requested_city": city,
                    "candidate_count": len(results),
                },
            )

        # Broad category browsing should show product variety before showing
        # many size/color variants of the same product.  For example,
        # "show me shoes" should surface sneakers, slippers, sandals and
        # khussa instead of filling all 10 cards with khussa sizes.
        #
        # Exact variant requests (size/color/material/city/price constraints)
        # keep their normal relevance order because those prompts are already
        # specific enough that variant-level ranking is desired.
        is_broad_category_browse = bool(
            category
            and size is None
            and color is None
            and material is None
            and city is None
            and min_price is None
            and max_price is None
        )

        if is_broad_category_browse:
            filtered_results = _diversify_results_by_product(
                filtered_results
            )

        # Broad category browsing should expose the full set of matching
        # variants (up to the deterministic retrieval pool) so customers
        # can see all available colors/sizes for the category.  The
        # round-robin ordering above keeps different products visible early.
        #
        # Specific queries (size/color/material/city/price constraints)
        # remain capped to ``match_count`` and therefore return only the
        # exact matching variants.
        if is_broad_category_browse:
            return filtered_results

        return filtered_results[:match_count]


product_agent = ProductAgent()