from types import SimpleNamespace

from app.agents import recommendation_agent as agent_module
from app.services import recommendation_service


class FakePreferenceQuery:
    def __init__(self, rows):
        self.rows = rows

    def select(self, fields):
        return self

    def eq(self, field, value):
        return self

    def limit(self, count):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


def test_disabled_consent_does_not_load_memory(monkeypatch):
    query = FakePreferenceQuery([
        {
            "preferred_categories": ["Kurtas"],
            "preferred_colors": ["Blue"],
            "preferred_sizes": ["M"],
            "preferred_styles": [],
            "budget_min": 1000,
            "budget_max": 5000,
            "allow_personalized_recommendations": False,
        }
    ])

    monkeypatch.setattr(
        recommendation_service,
        "supabase_admin",
        SimpleNamespace(table=lambda name: query),
    )

    def fail_if_called(customer_id):
        raise AssertionError(
            "Memory must not be loaded without consent"
        )

    monkeypatch.setattr(
        recommendation_service,
        "get_customer_context_snapshot",
        fail_if_called,
    )

    context = recommendation_service.get_recommendation_context(
        "customer-1"
    )

    assert context == {
        "personalization_allowed": False,
        "preferences": {},
        "remembered_facts": [],
    }


def test_missing_preference_row_does_not_load_memory(monkeypatch):
    query = FakePreferenceQuery([])

    monkeypatch.setattr(
        recommendation_service,
        "supabase_admin",
        SimpleNamespace(table=lambda name: query),
    )

    def fail_if_called(customer_id):
        raise AssertionError(
            "Memory must not be loaded without a preference row"
        )

    monkeypatch.setattr(
        recommendation_service,
        "get_customer_context_snapshot",
        fail_if_called,
    )

    context = recommendation_service.get_recommendation_context(
        "customer-1"
    )

    assert context["personalization_allowed"] is False
    assert context["preferences"] == {}
    assert context["remembered_facts"] == []


def test_explicit_filters_work_without_personalization(monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "get_recommendation_context",
        lambda customer_id: {
            "personalization_allowed": False,
            "preferences": {},
            "remembered_facts": [],
        },
    )

    captured = {}

    def fake_search(**kwargs):
        captured.update(kwargs)
        return [{"variant_id": "variant-1"}]

    monkeypatch.setattr(
        agent_module.product_agent,
        "search",
        fake_search,
    )

    results = agent_module.RecommendationAgent().recommend(
        customer_id="customer-1",
        query="blue kurta",
        category="Kurtas",
        color="Blue",
        size="M",
        min_price=1000,
        max_price=5000,
    )

    assert results == [{"variant_id": "variant-1"}]
    assert captured["query"] == "blue kurta"
    assert captured["category"] == "Kurtas"
    assert captured["color"] == "Blue"
    assert captured["size"] == "M"
    assert captured["min_price"] == 1000
    assert captured["max_price"] == 5000


def test_opted_in_preferences_and_memory_are_used(monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "get_recommendation_context",
        lambda customer_id: {
            "personalization_allowed": True,
            "preferences": {
                "preferred_categories": ["Kurtas"],
                "preferred_colors": ["Blue"],
                "preferred_sizes": ["M"],
                "preferred_styles": [],
                "budget_min": 1000,
                "budget_max": 5000,
            },
            "remembered_facts": [
                {
                    "memory_key": "preferred_material",
                    "memory_value": "Cotton",
                }
            ],
        },
    )

    captured = {}

    def fake_search(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        agent_module.product_agent,
        "search",
        fake_search,
    )

    agent_module.RecommendationAgent().recommend(
        customer_id="customer-1",
        query="",
    )

    assert captured["category"] == "Kurtas"
    assert captured["color"] == "Blue"
    assert captured["size"] == "M"
    assert captured["material"] == "Cotton"
    assert captured["min_price"] == 1000
    assert captured["max_price"] == 5000
    assert captured["query"] == "Kurtas Blue Cotton"


def test_current_filters_override_saved_preferences(monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "get_recommendation_context",
        lambda customer_id: {
            "personalization_allowed": True,
            "preferences": {
                "preferred_categories": ["Kurtas"],
                "preferred_colors": ["Blue"],
                "preferred_sizes": ["M"],
                "preferred_styles": [],
                "budget_min": 1000,
                "budget_max": 5000,
            },
            "remembered_facts": [],
        },
    )

    captured = {}

    def fake_search(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        agent_module.product_agent,
        "search",
        fake_search,
    )

    agent_module.RecommendationAgent().recommend(
        customer_id="customer-1",
        query="red shirt",
        category="Shirts",
        color="Red",
        size="L",
        min_price=2000,
        max_price=8000,
    )

    assert captured["category"] == "Shirts"
    assert captured["color"] == "Red"
    assert captured["size"] == "L"
    assert captured["min_price"] == 2000
    assert captured["max_price"] == 8000
