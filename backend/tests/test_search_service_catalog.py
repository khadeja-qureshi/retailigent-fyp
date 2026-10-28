from unittest.mock import MagicMock, patch

from app.services import search_service


def test_active_product_categories_returns_categories_with_active_products():
    products_response = MagicMock()
    products_response.data = [
        {"category_id": "cat-2"},
        {"category_id": "cat-1"},
        {"category_id": "cat-2"},
        {"category_id": None},
    ]

    categories = [
        {
            "id": "cat-1",
            "name": "Shirts",
            "sort_order": 1,
        },
        {
            "id": "cat-2",
            "name": "Shoes",
            "sort_order": 2,
        },
        {
            "id": "cat-3",
            "name": "Slippers",
            "sort_order": 3,
        },
    ]

    with (
        patch.object(
            search_service.supabase_admin,
            "table",
        ) as table,
        patch.object(
            search_service,
            "_fetch_active_categories",
            return_value=categories,
        ),
    ):
        table.return_value.select.return_value.eq.return_value.execute.return_value = (
            products_response
        )

        result = search_service.get_active_product_categories()

    assert result == ["Shirts", "Shoes"]


def test_active_product_categories_returns_empty_when_no_active_products():
    products_response = MagicMock()
    products_response.data = []

    with (
        patch.object(search_service.supabase_admin, "table") as table,
        patch.object(
            search_service,
            "_fetch_active_categories",
        ) as fetch_categories,
    ):
        table.return_value.select.return_value.eq.return_value.execute.return_value = (
            products_response
        )

        result = search_service.get_active_product_categories()

    assert result == []
    fetch_categories.assert_not_called()


def test_active_product_categories_ignores_missing_category_names():
    products_response = MagicMock()
    products_response.data = [
        {"category_id": "cat-1"},
        {"category_id": "cat-2"},
    ]

    categories = [
        {"id": "cat-1", "name": "   ", "sort_order": 1},
        {"id": "cat-2", "name": "Shirts", "sort_order": 2},
    ]

    with (
        patch.object(search_service.supabase_admin, "table") as table,
        patch.object(
            search_service,
            "_fetch_active_categories",
            return_value=categories,
        ),
    ):
        table.return_value.select.return_value.eq.return_value.execute.return_value = (
            products_response
        )

        result = search_service.get_active_product_categories()

    assert result == ["Shirts"]
