import json

import httpx

from app.agents import feedback_classifier_agent as classifier_module


def mock_ollama(monkeypatch, output):
    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": json.dumps(output)}

    monkeypatch.setattr(
        classifier_module.httpx,
        "post",
        lambda *args, **kwargs: MockResponse(),
    )


def test_classify_valid_ai_response(monkeypatch):
    mock_ollama(
        monkeypatch,
        {
            "category": "delivery",
            "sentiment": "negative",
            "needs_review": True,
            "rationale": "Customer reports a late delivery.",
        },
    )

    result, used_ai = (
        classifier_module.feedback_classifier_agent.classify(
            "My parcel is late and I am disappointed.",
            rating=2,
            feedback_type="delivery",
        )
    )

    assert used_ai is True
    assert result.category == "delivery"
    assert result.sentiment == "negative"
    assert result.needs_review is True


def test_low_rating_forces_review_even_if_model_misses_it(
    monkeypatch,
):
    mock_ollama(
        monkeypatch,
        {
            "category": "product",
            "sentiment": "positive",
            "needs_review": False,
            "rationale": "Model output for safeguard test.",
        },
    )

    result, used_ai = (
        classifier_module.feedback_classifier_agent.classify(
            "The product is okay.",
            rating=1,
            feedback_type="product",
        )
    )

    assert used_ai is True
    assert result.needs_review is True


def test_invalid_model_output_uses_fallback(monkeypatch):
    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": '{"category":"unknown"}'}

    monkeypatch.setattr(
        classifier_module.httpx,
        "post",
        lambda *args, **kwargs: MockResponse(),
    )

    result, used_ai = (
        classifier_module.feedback_classifier_agent.classify(
            "My delivery was late and the service was poor.",
            rating=1,
            feedback_type="delivery",
        )
    )

    assert used_ai is False
    assert result.category == "delivery"
    assert result.sentiment == "negative"
    assert result.needs_review is True
    assert "fallback" in result.rationale.lower()


def test_ollama_connection_failure_uses_fallback(monkeypatch):
    def fail_request(*args, **kwargs):
        raise httpx.ConnectError(
            "Ollama unavailable",
            request=httpx.Request(
                "POST",
                "http://localhost:11434/api/generate",
            ),
        )

    monkeypatch.setattr(
        classifier_module.httpx,
        "post",
        fail_request,
    )

    result, used_ai = (
        classifier_module.feedback_classifier_agent.classify(
            "The staff were helpful, thank you.",
            rating=5,
            feedback_type="service",
        )
    )

    assert used_ai is False
    assert result.sentiment == "positive"
    assert result.needs_review is False


def test_empty_message_is_rejected():
    import pytest

    with pytest.raises(ValueError, match="cannot be empty"):
        classifier_module.feedback_classifier_agent.classify("   ")


def test_model_cannot_disable_negative_review_flag(monkeypatch):
    mock_ollama(
        monkeypatch,
        {
            "category": "service",
            "sentiment": "negative",
            "needs_review": False,
            "rationale": "Negative feedback.",
        },
    )

    result, used_ai = (
        classifier_module.feedback_classifier_agent.classify(
            "The service was terrible.",
            rating=3,
            feedback_type="service",
        )
    )

    assert used_ai is True
    assert result.sentiment == "negative"
    assert result.needs_review is True

def test_fallback_handles_negated_negative_word(monkeypatch):
    def fail_request(*args, **kwargs):
        raise httpx.ConnectError(
            "Ollama unavailable",
            request=httpx.Request(
                "POST",
                "http://localhost:11434/api/generate",
            ),
        )

    monkeypatch.setattr(
        classifier_module.httpx,
        "post",
        fail_request,
    )

    result, used_ai = (
        classifier_module.feedback_classifier_agent.classify(
            "The delivery was not late.",
            feedback_type="delivery",
        )
    )

    assert used_ai is False
    assert result.sentiment == "neutral"
    assert result.needs_review is False


def test_fallback_handles_not_bad_as_positive(monkeypatch):
    def fail_request(*args, **kwargs):
        raise httpx.ConnectError(
            "Ollama unavailable",
            request=httpx.Request(
                "POST",
                "http://localhost:11434/api/generate",
            ),
        )

    monkeypatch.setattr(
        classifier_module.httpx,
        "post",
        fail_request,
    )

    result, used_ai = (
        classifier_module.feedback_classifier_agent.classify(
            "The product quality is not bad.",
            feedback_type="product",
        )
    )

    assert used_ai is False
    assert result.sentiment == "positive"
    assert result.needs_review is False


def test_fallback_prioritizes_negative_mixed_feedback(monkeypatch):
    def fail_request(*args, **kwargs):
        raise httpx.ConnectError(
            "Ollama unavailable",
            request=httpx.Request(
                "POST",
                "http://localhost:11434/api/generate",
            ),
        )

    monkeypatch.setattr(
        classifier_module.httpx,
        "post",
        fail_request,
    )

    result, used_ai = (
        classifier_module.feedback_classifier_agent.classify(
            "The product is good, but delivery was terrible.",
            feedback_type="delivery",
        )
    )

    assert used_ai is False
    assert result.category == "delivery"
    assert result.sentiment == "negative"
    assert result.needs_review is True


def test_low_rating_still_requires_review_with_positive_wording(
    monkeypatch,
):
    def fail_request(*args, **kwargs):
        raise httpx.ConnectError(
            "Ollama unavailable",
            request=httpx.Request(
                "POST",
                "http://localhost:11434/api/generate",
            ),
        )

    monkeypatch.setattr(
        classifier_module.httpx,
        "post",
        fail_request,
    )

    result, used_ai = (
        classifier_module.feedback_classifier_agent.classify(
            "The product is good.",
            rating=1,
            feedback_type="product",
        )
    )

    assert used_ai is False
    assert result.needs_review is True
