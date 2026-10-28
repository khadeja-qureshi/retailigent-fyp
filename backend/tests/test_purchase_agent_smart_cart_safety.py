from app.agents import purchase_agent as purchase_agent_module
from app.agents.purchase_agent import PurchaseAgent


def make_rule(**overrides):
    rule = {
        "id": "test-rule-001",
        "customer_id": "test-customer",
        "variant_id": "test-variant",
        "branch_id": None,
        "quantity": 1,
        "target_price": 1500,
        "min_discount_percentage": None,
        "authorization_mode": "auto_buy",
        "status": "triggered",
    }
    rule.update(overrides)
    return rule


def setup_agent(monkeypatch, rule, pricing):
    monkeypatch.setattr(
        purchase_agent_module,
        "get_smart_cart_rule_for_system",
        lambda rule_id: rule,
    )
    monkeypatch.setattr(
        purchase_agent_module,
        "get_effective_prices",
        lambda variant_ids: pricing,
    )

    agent = PurchaseAgent()
    calls = []

    def fake_purchase_direct(**kwargs):
        calls.append(kwargs)
        return {"success": True, "order_id": "unit-test-order"}

    monkeypatch.setattr(agent, "purchase_direct", fake_purchase_direct)
    return agent, calls


def test_auto_buy_refuses_price_above_target(monkeypatch):
    rule = make_rule(target_price=1500)
    pricing = {
        "test-variant": {
            "base_price": 2490,
            "effective_price": 2490,
            "discount_amount": 0,
        }
    }
    agent, calls = setup_agent(monkeypatch, rule, pricing)

    result = agent.process_auto_buy_rule("test-rule-001")

    assert result == {
        "processed": False,
        "reason": "target_price_not_met",
    }
    assert calls == []


def test_auto_buy_refuses_unavailable_pricing(monkeypatch):
    agent, calls = setup_agent(
        monkeypatch,
        make_rule(),
        {},
    )

    result = agent.process_auto_buy_rule("test-rule-001")

    assert result["processed"] is False
    assert result["reason"] == "price_unavailable"
    assert calls == []


def test_auto_buy_allows_price_at_target(monkeypatch):
    agent, calls = setup_agent(
        monkeypatch,
        make_rule(target_price=1500),
        {
            "test-variant": {
                "base_price": 2490,
                "effective_price": 1500,
                "discount_amount": 990,
            }
        },
    )

    result = agent.process_auto_buy_rule("test-rule-001")

    assert result["processed"] is True
    assert len(calls) == 1
    assert calls[0]["idempotency_key"] == "smart-cart:test-rule-001"


def test_auto_buy_refuses_unmet_minimum_discount(monkeypatch):
    agent, calls = setup_agent(
        monkeypatch,
        make_rule(
            target_price=None,
            min_discount_percentage=30,
        ),
        {
            "test-variant": {
                "base_price": 2490,
                "effective_price": 2000,
                "discount_amount": 490,
            }
        },
    )

    result = agent.process_auto_buy_rule("test-rule-001")

    assert result["processed"] is False
    assert result["reason"] == "minimum_discount_not_met"
    assert calls == []


def test_auto_buy_allows_met_minimum_discount(monkeypatch):
    agent, calls = setup_agent(
        monkeypatch,
        make_rule(
            target_price=None,
            min_discount_percentage=30,
        ),
        {
            "test-variant": {
                "base_price": 2490,
                "effective_price": 1700,
                "discount_amount": 790,
            }
        },
    )

    result = agent.process_auto_buy_rule("test-rule-001")

    assert result["processed"] is True
    assert len(calls) == 1


def test_auto_buy_fails_closed_when_pricing_raises(monkeypatch):
    monkeypatch.setattr(
        purchase_agent_module,
        "get_smart_cart_rule_for_system",
        lambda rule_id: make_rule(),
    )

    def pricing_failure(variant_ids):
        raise RuntimeError("Pricing service unavailable")

    monkeypatch.setattr(
        purchase_agent_module,
        "get_effective_prices",
        pricing_failure,
    )

    agent = PurchaseAgent()
    calls = []

    def fake_purchase_direct(**kwargs):
        calls.append(kwargs)
        return {"success": True}

    monkeypatch.setattr(agent, "purchase_direct", fake_purchase_direct)

    result = agent.process_auto_buy_rule("test-rule-001")

    assert result["processed"] is False
    assert result["reason"] == "price_verification_failed"
    assert calls == []
