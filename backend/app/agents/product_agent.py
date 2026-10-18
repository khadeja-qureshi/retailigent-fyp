from typing import Any, Optional

from app.services.search_service import search_variants


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

        results = search_variants(
            query=query.strip(),
            match_count=match_count,
        )

        if not results:
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

        return filtered_results


product_agent = ProductAgent()