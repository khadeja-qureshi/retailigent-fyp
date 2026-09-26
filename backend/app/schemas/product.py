from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ProductImage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    image_url: str
    alt_text: Optional[str] = None
    sort_order: int = 0
    is_primary: bool = False


class ProductVariant(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    color_id: Optional[str] = None
    size_id: Optional[str] = None
    sku: str
    price: Optional[float] = None
    barcode: Optional[str] = None
    attributes: dict[str, Any] = {}
    is_active: bool = True


class ProductSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category_id: Optional[str] = None
    name: str
    slug: str
    sku: str
    description: Optional[str] = None
    brand: Optional[str] = None
    gender: Optional[str] = None
    material: Optional[str] = None
    care_instructions: Optional[str] = None
    base_price: Optional[float] = None
    attributes: dict[str, Any] = {}
    is_active: bool = True
    images: list[ProductImage] = []