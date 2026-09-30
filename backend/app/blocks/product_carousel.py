from typing import Any


class ProductCarouselBlock:
    """
    UI block for displaying a collection of product results.

    The block only formats data returned by the Product Agent.
    It does not perform database queries or business logic.
    """

    type = "product_carousel"

    @staticmethod
    def build(
        products: list[dict[str, Any]],
    ) -> dict[str, Any]:
        items = []

        for result in products:
            product = result.get("product") or {}
            variant = result.get("variant") or {}
            color = variant.get("color") or {}
            size = variant.get("size") or {}
            pricing = result.get("pricing") or {}
            images = result.get("images") or []

            primary_image = next(
                (
                    image
                    for image in images
                    if image.get("is_primary")
                ),
                None,
            )

            if primary_image is None and images:
                primary_image = images[0]

            items.append(
                {
                    "product_id": result.get("product_id"),
                    "variant_id": result.get("variant_id"),
                    "name": product.get("name"),
                    "image_url": (
                        primary_image.get("image_url")
                        if primary_image
                        else None
                    ),
                    "color": color.get("name"),
                    "size": size.get("name"),
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
                    "sku": variant.get("sku"),
                }
            )

        return {
            "type": ProductCarouselBlock.type,
            "items": items,
        }
