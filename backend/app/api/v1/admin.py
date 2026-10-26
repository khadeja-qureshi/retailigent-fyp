from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_staff
from app.core.supabase_client import supabase_admin


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
)


def _safe_rows(response: Any) -> list[dict[str, Any]]:
    """
    Convert a Supabase response into a safe list of rows.
    """

    return list(response.data or [])


def _as_float(value: Any) -> float | None:
    """
    Safely convert numeric database values to float.
    """

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ============================================================================
# Inventory
# ============================================================================


@router.get("/inventory")
def list_staff_inventory(
    limit: int = Query(
        default=200,
        ge=1,
        le=500,
    ),
    _role: str = Depends(require_staff),
) -> dict[str, Any]:
    """
    Return branch inventory enriched with branch,
    product, variant, colour and size information.
    """

    try:
        inventory = _safe_rows(
            supabase_admin
            .table("branch_inventory")
            .select(
                "id, branch_id, variant_id, "
                "on_hand_quantity, reserved_quantity, "
                "safety_stock, available_quantity, "
                "updated_at"
            )
            .order(
                "updated_at",
                desc=True,
            )
            .limit(limit)
            .execute()
        )

        if not inventory:
            return {
                "inventory": [],
                "count": 0,
            }

        branch_ids = sorted(
            {
                str(row["branch_id"])
                for row in inventory
                if row.get("branch_id")
            }
        )

        variant_ids = sorted(
            {
                str(row["variant_id"])
                for row in inventory
                if row.get("variant_id")
            }
        )

        branches: dict[str, dict[str, Any]] = {}

        if branch_ids:
            branches = {
                str(row["id"]): row
                for row in _safe_rows(
                    supabase_admin
                    .table("branches")
                    .select(
                        "id, name, city, area, is_active"
                    )
                    .in_(
                        "id",
                        branch_ids,
                    )
                    .execute()
                )
            }

        variants_list: list[dict[str, Any]] = []

        if variant_ids:
            variants_list = _safe_rows(
                supabase_admin
                .table("product_variants")
                .select(
                    "id, product_id, sku, color_id, "
                    "size_id, price, is_active"
                )
                .in_(
                    "id",
                    variant_ids,
                )
                .execute()
            )

        variants = {
            str(row["id"]): row
            for row in variants_list
        }

        product_ids = sorted(
            {
                str(row["product_id"])
                for row in variants_list
                if row.get("product_id")
            }
        )

        color_ids = sorted(
            {
                str(row["color_id"])
                for row in variants_list
                if row.get("color_id")
            }
        )

        size_ids = sorted(
            {
                str(row["size_id"])
                for row in variants_list
                if row.get("size_id")
            }
        )

        products: dict[str, dict[str, Any]] = {}

        if product_ids:
            products = {
                str(row["id"]): row
                for row in _safe_rows(
                    supabase_admin
                    .table("products")
                    .select(
                        "id, name, sku, brand, is_active"
                    )
                    .in_(
                        "id",
                        product_ids,
                    )
                    .execute()
                )
            }

        colors: dict[str, dict[str, Any]] = {}

        if color_ids:
            colors = {
                str(row["id"]): row
                for row in _safe_rows(
                    supabase_admin
                    .table("colors")
                    .select(
                        "id, name"
                    )
                    .in_(
                        "id",
                        color_ids,
                    )
                    .execute()
                )
            }

        sizes: dict[str, dict[str, Any]] = {}

        if size_ids:
            sizes = {
                str(row["id"]): row
                for row in _safe_rows(
                    supabase_admin
                    .table("sizes")
                    .select(
                        "id, name"
                    )
                    .in_(
                        "id",
                        size_ids,
                    )
                    .execute()
                )
            }

        result: list[dict[str, Any]] = []

        for row in inventory:
            variant = variants.get(
                str(row.get("variant_id") or ""),
                {},
            )

            branch = branches.get(
                str(row.get("branch_id") or ""),
                {},
            )

            product = products.get(
                str(
                    variant.get("product_id")
                    or ""
                ),
                {},
            )

            color = colors.get(
                str(
                    variant.get("color_id")
                    or ""
                ),
                {},
            )

            size = sizes.get(
                str(
                    variant.get("size_id")
                    or ""
                ),
                {},
            )

            result.append(
                {
                    **row,
                    "branch_name": branch.get("name"),
                    "branch_city": branch.get("city"),
                    "branch_area": branch.get("area"),
                    "branch_active": branch.get("is_active"),
                    "variant_sku": variant.get("sku"),
                    "variant_price": _as_float(
                        variant.get("price")
                    ),
                    "variant_active": variant.get("is_active"),
                    "product_id": variant.get("product_id"),
                    "product_name": product.get("name"),
                    "product_sku": product.get("sku"),
                    "product_brand": product.get("brand"),
                    "product_active": product.get("is_active"),
                    "color_name": color.get("name"),
                    "size_name": size.get("name"),
                }
            )

        return {
            "inventory": result,
            "count": len(result),
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load staff inventory: {exc}",
        ) from exc


# ============================================================================
# Promotions
# ============================================================================


@router.get("/promotions")
def list_staff_promotions(
    limit: int = Query(
        default=200,
        ge=1,
        le=500,
    ),
    _role: str = Depends(require_staff),
) -> dict[str, Any]:
    """
    Return promotions enriched with relevant
    product and variant information.
    """

    try:
        promotions = _safe_rows(
            supabase_admin
            .table("promotions")
            .select(
                "id, name, product_id, variant_id, "
                "discount_type, discount_value, "
                "starts_at, ends_at, priority, "
                "is_active, metadata, created_at"
            )
            .order(
                "starts_at",
                desc=True,
            )
            .limit(limit)
            .execute()
        )

        if not promotions:
            return {
                "promotions": [],
                "count": 0,
            }

        product_ids = {
            str(row["product_id"])
            for row in promotions
            if row.get("product_id")
        }

        variant_ids = {
            str(row["variant_id"])
            for row in promotions
            if row.get("variant_id")
        }

        variants: dict[str, dict[str, Any]] = {}

        if variant_ids:
            variant_rows = _safe_rows(
                supabase_admin
                .table("product_variants")
                .select(
                    "id, product_id, sku"
                )
                .in_(
                    "id",
                    sorted(variant_ids),
                )
                .execute()
            )

            variants = {
                str(row["id"]): row
                for row in variant_rows
            }

            product_ids.update(
                str(row["product_id"])
                for row in variant_rows
                if row.get("product_id")
            )

        products: dict[str, dict[str, Any]] = {}

        if product_ids:
            products = {
                str(row["id"]): row
                for row in _safe_rows(
                    supabase_admin
                    .table("products")
                    .select(
                        "id, name, sku"
                    )
                    .in_(
                        "id",
                        sorted(product_ids),
                    )
                    .execute()
                )
            }

        result: list[dict[str, Any]] = []

        for row in promotions:
            variant = variants.get(
                str(row.get("variant_id") or ""),
                {},
            )

            effective_product_id = (
                row.get("product_id")
                or variant.get("product_id")
            )

            product = products.get(
                str(effective_product_id or ""),
                {},
            )

            result.append(
                {
                    **row,
                    "discount_value": _as_float(
                        row.get("discount_value")
                    ),
                    "product_name": product.get("name"),
                    "product_sku": product.get("sku"),
                    "variant_sku": variant.get("sku"),
                }
            )

        return {
            "promotions": result,
            "count": len(result),
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load promotions: {exc}",
        ) from exc


# ============================================================================
# Orders
# ============================================================================


@router.get("/orders")
def list_staff_orders(
    limit: int = Query(
        default=200,
        ge=1,
        le=500,
    ),
    _role: str = Depends(require_staff),
) -> dict[str, Any]:
    """
    Return recent orders enriched with customer,
    branch and order-item summary information.
    """

    try:
        orders = _safe_rows(
            supabase_admin
            .table("orders")
            .select(
                "id, customer_id, branch_id, "
                "status, subtotal, discount, total, "
                "currency, source, created_at, updated_at"
            )
            .order(
                "created_at",
                desc=True,
            )
            .limit(limit)
            .execute()
        )

        if not orders:
            return {
                "orders": [],
                "count": 0,
            }

        customer_ids = sorted(
            {
                str(row["customer_id"])
                for row in orders
                if row.get("customer_id")
            }
        )

        branch_ids = sorted(
            {
                str(row["branch_id"])
                for row in orders
                if row.get("branch_id")
            }
        )

        order_ids = sorted(
            {
                str(row["id"])
                for row in orders
                if row.get("id")
            }
        )

        profiles: dict[str, dict[str, Any]] = {}

        if customer_ids:
            profiles = {
                str(row["id"]): row
                for row in _safe_rows(
                    supabase_admin
                    .table("profiles")
                    .select(
                        "id, full_name, phone, is_active"
                    )
                    .in_(
                        "id",
                        customer_ids,
                    )
                    .execute()
                )
            }

        branches: dict[str, dict[str, Any]] = {}

        if branch_ids:
            branches = {
                str(row["id"]): row
                for row in _safe_rows(
                    supabase_admin
                    .table("branches")
                    .select(
                        "id, name, city, area"
                    )
                    .in_(
                        "id",
                        branch_ids,
                    )
                    .execute()
                )
            }

        order_items: list[dict[str, Any]] = []

        if order_ids:
            order_items = _safe_rows(
                supabase_admin
                .table("order_items")
                .select(
                    "order_id, quantity, line_total"
                )
                .in_(
                    "order_id",
                    order_ids,
                )
                .execute()
            )

        line_counts: dict[str, int] = {}
        quantity_counts: dict[str, int] = {}

        for item in order_items:
            order_id = str(
                item.get("order_id")
                or ""
            )

            if not order_id:
                continue

            line_counts[order_id] = (
                line_counts.get(
                    order_id,
                    0,
                )
                + 1
            )

            quantity_counts[order_id] = (
                quantity_counts.get(
                    order_id,
                    0,
                )
                + int(
                    item.get("quantity")
                    or 0
                )
            )

        result: list[dict[str, Any]] = []

        for row in orders:
            order_id = str(
                row.get("id")
                or ""
            )

            profile = profiles.get(
                str(
                    row.get("customer_id")
                    or ""
                ),
                {},
            )

            branch = branches.get(
                str(
                    row.get("branch_id")
                    or ""
                ),
                {},
            )

            result.append(
                {
                    **row,
                    "subtotal": _as_float(
                        row.get("subtotal")
                    ),
                    "discount": _as_float(
                        row.get("discount")
                    ),
                    "total": _as_float(
                        row.get("total")
                    ),
                    "customer_name": profile.get("full_name"),
                    "customer_phone": profile.get("phone"),
                    "customer_active": profile.get("is_active"),
                    "branch_name": branch.get("name"),
                    "branch_city": branch.get("city"),
                    "branch_area": branch.get("area"),
                    "line_count": line_counts.get(
                        order_id,
                        0,
                    ),
                    "item_quantity": quantity_counts.get(
                        order_id,
                        0,
                    ),
                }
            )

        return {
            "orders": result,
            "count": len(result),
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load staff orders: {exc}",
        ) from exc


# ============================================================================
# Demand signals
# ============================================================================


@router.get("/demand-signals")
def list_staff_demand_signals(
    limit: int = Query(
        default=200,
        ge=1,
        le=500,
    ),
    _role: str = Depends(require_staff),
) -> dict[str, Any]:
    """
    Return recent unmet-demand signals enriched
    with product, variant and branch information.
    """

    try:
        signals = _safe_rows(
            supabase_admin
            .table("demand_signals")
            .select(
                "id, customer_id, product_id, "
                "variant_id, branch_id, signal_type, "
                "requested_size, requested_color, "
                "fulfilled, metadata, created_at"
            )
            .order(
                "created_at",
                desc=True,
            )
            .limit(limit)
            .execute()
        )

        if not signals:
            return {
                "demand_signals": [],
                "count": 0,
            }

        product_ids = {
            str(row["product_id"])
            for row in signals
            if row.get("product_id")
        }

        variant_ids = {
            str(row["variant_id"])
            for row in signals
            if row.get("variant_id")
        }

        branch_ids = {
            str(row["branch_id"])
            for row in signals
            if row.get("branch_id")
        }

        variants: dict[str, dict[str, Any]] = {}

        if variant_ids:
            variant_rows = _safe_rows(
                supabase_admin
                .table("product_variants")
                .select(
                    "id, product_id, sku"
                )
                .in_(
                    "id",
                    sorted(variant_ids),
                )
                .execute()
            )

            variants = {
                str(row["id"]): row
                for row in variant_rows
            }

            product_ids.update(
                str(row["product_id"])
                for row in variant_rows
                if row.get("product_id")
            )

        products: dict[str, dict[str, Any]] = {}

        if product_ids:
            products = {
                str(row["id"]): row
                for row in _safe_rows(
                    supabase_admin
                    .table("products")
                    .select(
                        "id, name, sku"
                    )
                    .in_(
                        "id",
                        sorted(product_ids),
                    )
                    .execute()
                )
            }

        branches: dict[str, dict[str, Any]] = {}

        if branch_ids:
            branches = {
                str(row["id"]): row
                for row in _safe_rows(
                    supabase_admin
                    .table("branches")
                    .select(
                        "id, name, city, area"
                    )
                    .in_(
                        "id",
                        sorted(branch_ids),
                    )
                    .execute()
                )
            }

        result: list[dict[str, Any]] = []

        for row in signals:
            variant = variants.get(
                str(row.get("variant_id") or ""),
                {},
            )

            effective_product_id = (
                row.get("product_id")
                or variant.get("product_id")
            )

            product = products.get(
                str(effective_product_id or ""),
                {},
            )

            branch = branches.get(
                str(row.get("branch_id") or ""),
                {},
            )

            result.append(
                {
                    **row,
                    "product_name": product.get("name"),
                    "product_sku": product.get("sku"),
                    "variant_sku": variant.get("sku"),
                    "branch_name": branch.get("name"),
                    "branch_city": branch.get("city"),
                    "branch_area": branch.get("area"),
                }
            )

        return {
            "demand_signals": result,
            "count": len(result),
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load demand signals: {exc}",
        ) from exc