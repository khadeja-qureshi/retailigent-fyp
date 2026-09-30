from typing import Any, Optional

from app.services.search_service import search_variants


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
            product = result.get("product") or {}
            variant = result.get("variant") or {}
            variant_color = variant.get("color") or {}
            variant_size = variant.get("size") or {}
            pricing = result.get("pricing") or {}
            inventory = result.get("inventory") or []

            # ---------------------------------------------------------
            # Color filter
            # ---------------------------------------------------------
            if color:
                actual_color = str(
                    variant_color.get("name") or ""
                ).strip().lower()

                if actual_color != color.strip().lower():
                    continue

            # ---------------------------------------------------------
            # Size filter
            # ---------------------------------------------------------
            if size:
                actual_size = str(
                    variant_size.get("name") or ""
                ).strip().lower()

                if actual_size != size.strip().lower():
                    continue

            # ---------------------------------------------------------
            # Material filter
            # ---------------------------------------------------------
            if material:
                actual_material = str(
                    product.get("material") or ""
                ).strip().lower()

                if actual_material != material.strip().lower():
                    continue

            # ---------------------------------------------------------
            # Category filter
            # ---------------------------------------------------------
            if category:
                category_data = product.get("category") or {}

                category_name = str(
                    category_data.get("name") or ""
                ).strip().lower()

                category_slug = str(
                    category_data.get("slug") or ""
                ).strip().lower()

                requested_category = category.strip().lower()

                if requested_category not in {
                    category_name,
                    category_slug,
                }:
                    continue
            # ---------------------------------------------------------
            # Price filters
            # ---------------------------------------------------------
            effective_price = pricing.get("effective_price")

            if effective_price is None:
                effective_price = variant.get("price")

            if effective_price is not None:
                effective_price = float(effective_price)

                if (
                    min_price is not None
                    and effective_price < min_price
                ):
                    continue

                if (
                    max_price is not None
                    and effective_price > max_price
                ):
                    continue

            # ---------------------------------------------------------
            # City filter
            # ---------------------------------------------------------
            if city:
                requested_city = city.strip().lower()

                matching_city = False

                for inventory_row in inventory:
                    branch = inventory_row.get("branch") or {}
                    branch_city = str(
                        branch.get("city") or ""
                    ).strip().lower()

                    if branch_city == requested_city:
                        matching_city = True
                        break

                if not matching_city:
                    continue

            filtered_results.append(result)

        return filtered_results


product_agent = ProductAgent()
