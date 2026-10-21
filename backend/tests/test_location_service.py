from unittest.mock import patch

from app.services.location_service import search_active_branches


def test_search_filters_inactive_query_results_by_city_and_area():
    branches = [
        {
            "id": "b1", "name": "Gulberg Store", "city": "Lahore",
            "area": "Gulberg", "address": "Main Road",
            "latitude": 31.5, "longitude": 74.3, "phone": "123",
            "opening_time": "10:00:00", "closing_time": "22:00:00",
        },
        {
            "id": "b2", "name": "Clifton Store", "city": "Karachi",
            "area": "Clifton", "address": "Sea View",
            "latitude": None, "longitude": None, "phone": None,
            "opening_time": None, "closing_time": None,
        },
    ]

    class FakeQuery:
        def select(self, fields):
            return self
        def eq(self, field, value):
            assert field == "is_active"
            assert value is True
            return self
        def execute(self):
            class Result:
                data = branches
            return Result()

    class FakeSupabase:
        def table(self, name):
            assert name == "branches"
            return FakeQuery()

    with patch(
        "app.services.location_service.supabase_admin",
        FakeSupabase(),
    ):
        result = search_active_branches(city="karachi", area="clifton")

    assert len(result) == 1
    assert result[0]["branch_id"] == "b2"
    assert result[0]["name"] == "Clifton Store"
    assert result[0]["latitude"] is None


def test_variant_filter_requires_positive_inventory():
    branches = [
        {
            "id": "b1", "name": "Gulberg Store", "city": "Lahore",
            "area": "Gulberg", "address": None, "latitude": None,
            "longitude": None, "phone": None, "opening_time": None,
            "closing_time": None,
        },
        {
            "id": "b2", "name": "Clifton Store", "city": "Karachi",
            "area": "Clifton", "address": None, "latitude": None,
            "longitude": None, "phone": None, "opening_time": None,
            "closing_time": None,
        },
    ]

    class FakeQuery:
        def select(self, fields):
            return self
        def eq(self, field, value):
            return self
        def execute(self):
            class Result:
                data = branches
            return Result()

    class FakeSupabase:
        def table(self, name):
            return FakeQuery()

    inventory = [
        {"branch_id": "b1", "available_quantity": 0},
        {"branch_id": "b2", "available_quantity": 3},
    ]

    with (
        patch(
            "app.services.location_service.supabase_admin",
            FakeSupabase(),
        ),
        patch(
            "app.services.location_service.get_inventory_snapshot_enriched",
            return_value=inventory,
        ),
    ):
        result = search_active_branches(variant_id="variant-123")

    assert [branch["branch_id"] for branch in result] == ["b2"]
