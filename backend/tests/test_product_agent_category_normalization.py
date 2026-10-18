from app.agents.product_agent import (
    _category_matches,
    _normalize_category_tokens,
)


def test_singular_category_matches_plural_name():
    assert _category_matches(
        "kurta",
        "Kurtas",
        "test-men-kurtas",
    )


def test_plural_category_matches_plural_name():
    assert _category_matches(
        "Kurtas",
        "Kurtas",
        "test-women-kurtas",
    )


def test_singular_multiword_category_matches():
    assert _category_matches(
        "casual shirt",
        "Casual Shirts",
        "test-men-shirts",
    )


def test_category_does_not_match_unrelated_category():
    assert not _category_matches(
        "kurta",
        "Casual Shirts",
        "test-men-shirts",
    )


def test_plural_normalization():
    tokens = _normalize_category_tokens(
        "Kurtas"
    )

    assert "kurtas" in tokens
    assert "kurta" in tokens


def test_dress_is_not_corrupted():
    tokens = _normalize_category_tokens(
        "dress"
    )

    assert "dress" in tokens
    assert "dres" not in tokens