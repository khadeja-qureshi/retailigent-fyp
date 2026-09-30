from typing import Any


class ProductDetailBlock:
    """
    UI block for displaying detailed information about a single product
    variant.

    The block only formats data returned by the Product Agent.
    It does not perform database queries or business logic.
    """

    type = "product_detail"

    @staticmethod
    def build(
        result: dict[str, Any],
    ) -> dict[str, Any]:
        product = result.get("product") or {}
        variant = result.get("variant") or {}
        color = variant.get("color") or {}
        size = variant.get("size") or {}
        pricing = result.get("pricing") or {}
        images = result.get("images") or {}
        inventory = result.get("inventory") or []

        return {
            "type": ProductDetailBlock.type,
            "product_id": result.get("product_id"),
            "variant_id": result.get("variant_id"),
            "name": product.get("name"),
            "description": product.get("description"),
            "brand": product.get("brand"),
            "material": product.get("material"),
            "category": (
                product.get("category") or {}
            ),
            "color": color.get("name"),
            "size": size.get("name"),
            "sku": variant.get("sku"),
            "price": pricing.get(
                "effective_price",
                variant.get("price"),
            ),
            "base_price": pricing.get(
                "base_price",
                variant.get("price"),
            ),
            "discount_amount": pricing.get(
                "discount_amount",
                0,
            ),
            "images": images,
            "inventory": inventory,
        }
