
from __future__ import annotations

import re

from app.schemas.chat import (
    ExtractedEntities,
    ParsedCustomerMessage,
)


# ============================================================================
# Vocabulary
# ============================================================================


ROMAN_URDU_MARKERS = {
    "mujhe",
    "mujhay",
    "chahiye",
    "chahye",
    "dikhao",
    "dikha",
    "hai",
    "hain",
    "wala",
    "wali",
    "isko",
    "isse",
    "yeh",
    "ye",
    "agar",
    "neeche",
    "kam",
    "karo",
    "karna",
    "daal",
    "dalo",
    "khareed",
    "kharid",
    "batana",
    "mein",
    "ka",
    "ki",
    "ke",
}


ENGLISH_MARKERS = {
    "show",
    "find",
    "search",
    "product",
    "products",
    "stock",
    "available",
    "availability",
    "cart",
    "wishlist",
    "buy",
    "purchase",
    "price",
    "discount",
    "size",
    "color",
    "colour",
    "blue",
    "black",
    "white",
    "red",
    "green",
    "first",
    "second",
    "third",
    "notify",
    "alert",
}


COLOR_ALIASES = {
    "black": "Black",
    "white": "White",
    "blue": "Blue",
    "navy": "Navy",
    "red": "Red",
    "green": "Green",
    "beige": "Beige",
    "brown": "Brown",
    "pink": "Pink",
    "purple": "Purple",
    "maroon": "Maroon",
    "grey": "Grey",
    "gray": "Grey",
    "yellow": "Yellow",
    "orange": "Orange",
}


MATERIAL_ALIASES = {
    "cotton": "Cotton",
    "lawn": "Lawn",
    "silk": "Silk",
    "linen": "Linen",
    "khaddar": "Khaddar",
    "chiffon": "Chiffon",
    "organza": "Organza",
    "velvet": "Velvet",
    "denim": "Denim",
}


CATEGORY_ALIASES = {
    "kurta": "kurta",
    "kurtas": "kurta",
    "shirt": "shirt",
    "shirts": "shirt",
    "dress": "dress",
    "dresses": "dress",
    "suit": "suit",
    "suits": "suit",
    "trouser": "trouser",
    "trousers": "trouser",
    "dupatta": "dupatta",
    "dupattas": "dupatta",
    "shalwar": "shalwar",
    "kameez": "kameez",
}


BRANCH_ALIASES = {
    "gulberg": "Gulberg",
    "clifton": "Clifton",
    "dha": "DHA",
}


SIZE_ALIASES = {
    "xs": "XS",
    "extra small": "XS",
    "small": "S",
    "s": "S",
    "medium": "M",
    "m": "M",
    "large": "L",
    "l": "L",
    "xl": "XL",
    "extra large": "XL",
    "xxl": "XXL",
}


ORDINAL_ALIASES = {
    "first": 1,
    "1st": 1,
    "pehla": 1,
    "pehli": 1,
    "second": 2,
    "2nd": 2,
    "dusra": 2,
    "doosra": 2,
    "dusri": 2,
    "doosri": 2,
    "third": 3,
    "3rd": 3,
    "teesra": 3,
    "teesri": 3,
    "fourth": 4,
    "4th": 4,
    "fifth": 5,
    "5th": 5,
}


CONTEXT_REFERENCE_WORDS = {
    "it",
    "this",
    "that",
    "this one",
    "that one",
    "isko",
    "isse",
    "yeh",
    "ye",
    "wala",
    "wali",
}


UUID_RE = re.compile(
    r"\b"
    r"[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}"
    r"\b"
)


NUMBER = r"([0-9]+(?:\.[0-9]+)?)"


# ============================================================================
# Utility helpers
# ============================================================================


def _normalize(
    text: str,
) -> str:
    text = text.strip().lower()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


def _has_phrase(
    text: str,
    phrase: str,
) -> bool:
    if " " in phrase:
        return phrase in text

    return bool(
        re.search(
            rf"\b{re.escape(phrase)}\b",
            text,
        )
    )


def _contains_any(
    text: str,
    phrases: set[str],
) -> bool:
    return any(
        _has_phrase(
            text,
            phrase,
        )
        for phrase in phrases
    )


def _parse_number(
    value: str,
) -> float:
    return float(
        value.replace(
            ",",
            "",
        )
    )


# ============================================================================
# Language
# ============================================================================


def detect_language(
    message: str,
) -> str:
    text = _normalize(
        message
    )

    tokens = set(
        re.findall(
            r"[a-zA-Z]+",
            text,
        )
    )

    has_roman_urdu = bool(
        tokens
        & ROMAN_URDU_MARKERS
    )

    has_english = bool(
        tokens
        & ENGLISH_MARKERS
    )

    if (
        has_roman_urdu
        and has_english
    ):
        return "mixed"

    if has_roman_urdu:
        return "roman_urdu"

    return "english"


# ============================================================================
# Entity extraction
# ============================================================================


def _extract_variant_id(
    text: str,
) -> str | None:
    match = UUID_RE.search(
        text
    )

    if not match:
        return None

    return match.group(0)


def _extract_color(
    text: str,
) -> str | None:
    for word, normalized in COLOR_ALIASES.items():
        if _has_phrase(
            text,
            word,
        ):
            return normalized

    return None


def _extract_material(
    text: str,
) -> str | None:
    for word, normalized in MATERIAL_ALIASES.items():
        if _has_phrase(
            text,
            word,
        ):
            return normalized

    return None


def _extract_category(
    text: str,
) -> str | None:
    for word, normalized in CATEGORY_ALIASES.items():
        if _has_phrase(
            text,
            word,
        ):
            return normalized

    return None


def _extract_branch(
    text: str,
) -> str | None:
    for word, normalized in BRANCH_ALIASES.items():
        if _has_phrase(
            text,
            word,
        ):
            return normalized

    return None


def _extract_size(
    text: str,
) -> str | None:
    size_match = re.search(
        r"\bsize\s*[:\-]?\s*"
        r"(xxl|xl|xs|s|m|l|"
        r"small|medium|large|"
        r"extra small|extra large)"
        r"\b",
        text,
        flags=re.IGNORECASE,
    )

    if size_match:
        raw = size_match.group(1).lower()

        return SIZE_ALIASES.get(
            raw
        )

    # Explicit short form:
    # "kurta M"
    short_match = re.search(
        r"\b(?:kurta|shirt|dress|suit)"
        r"\s+(xs|s|m|l|xl|xxl)\b",
        text,
        flags=re.IGNORECASE,
    )

    if short_match:
        return short_match.group(1).upper()

    return None


def _extract_ordinal(
    text: str,
) -> int | None:
    for word, ordinal in ORDINAL_ALIASES.items():
        if _has_phrase(
            text,
            word,
        ):
            return ordinal

    return None


def _extract_quantity(
    text: str,
) -> int | None:
    patterns = [
        r"\b(?:quantity|qty)\s*[:\-]?\s*(\d+)\b",
        r"\b(\d+)\s*(?:items?|pieces?|pcs?|units?)\b",
        r"\bx\s*(\d+)\b",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            quantity = int(
                match.group(1)
            )

            if quantity > 0:
                return quantity

    return None


def _extract_discount(
    text: str,
) -> float | None:
    match = re.search(
        r"\b"
        r"([0-9]+(?:\.[0-9]+)?)"
        r"\s*%"
        r"(?:\s*discount|\s*off)?",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    value = float(
        match.group(1)
    )

    if 0 <= value <= 100:
        return value

    return None


def _extract_price_range(
    text: str,
) -> tuple[
    float | None,
    float | None,
]:
    between = re.search(
        r"\bbetween\s+"
        r"(?:rs\.?|pkr)?\s*"
        + NUMBER
        + r"\s+(?:and|to)\s+"
        r"(?:rs\.?|pkr)?\s*"
        + NUMBER,
        text,
        flags=re.IGNORECASE,
    )

    if between:
        return (
            _parse_number(
                between.group(1)
            ),
            _parse_number(
                between.group(2)
            ),
        )

    min_price = None
    max_price = None

    min_patterns = [
        (
            r"\b(?:above|over|more than|"
            r"greater than)\s+"
            r"(?:rs\.?|pkr)?\s*"
            + NUMBER
        ),
        (
            r"\b"
            + NUMBER
            + r"\s*(?:se zyada|se upar)\b"
        ),
    ]

    max_patterns = [
        (
            r"\b(?:under|below|less than|"
            r"up to)\s+"
            r"(?:rs\.?|pkr)?\s*"
            + NUMBER
        ),
        (
            r"\b"
            + NUMBER
            + r"\s*(?:se neeche|se kam)\b"
        ),
    ]

    for pattern in min_patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            min_price = _parse_number(
                match.group(1)
            )
            break

    for pattern in max_patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            max_price = _parse_number(
                match.group(1)
            )
            break

    return (
        min_price,
        max_price,
    )


def _extract_target_price(
    text: str,
) -> float | None:
    patterns = [
        (
            r"\b(?:below|under|less than)\s+"
            r"(?:rs\.?|pkr)?\s*"
            + NUMBER
        ),
        (
            r"\b"
            + NUMBER
            + r"\s*(?:se neeche|se kam)\b"
        ),
        (
            r"\b(?:price\s*)?"
            r"(?:drops?|falls?)\s+"
            r"(?:below|under)\s+"
            r"(?:rs\.?|pkr)?\s*"
            + NUMBER
        ),
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return _parse_number(
                match.group(1)
            )

    return None


def _extract_authorization_mode(
    text: str,
) -> str | None:
    auto_buy_phrases = {
        "auto buy",
        "autobuy",
        "buy automatically",
        "automatically buy",
        "automatic purchase",
        "khud buy",
        "khud khareed",
        "khud kharid",
    }

    if _contains_any(
        text,
        auto_buy_phrases,
    ):
        return "auto_buy"

    conditional_buy = (
        _contains_any(
            text,
            {
                "buy",
                "purchase",
                "khareed",
                "kharid",
            },
        )
        and _contains_any(
            text,
            {
                "if",
                "agar",
                "when",
            },
        )
    )

    if conditional_buy:
        return "auto_buy"

    notify_phrases = {
        "notify me",
        "alert me",
        "tell me when",
        "mujhe batana",
        "notify karna",
    }

    if _contains_any(
        text,
        notify_phrases,
    ):
        return "notify_only"

    return None


def extract_entities(
    message: str,
    *,
    intent: str,
) -> ExtractedEntities:
    text = _normalize(
        message
    )

    min_price, max_price = _extract_price_range(text)

    target_price = None

    if intent == "smart_cart_create":
        target_price = _extract_target_price(text)

        # A Smart Cart target should not
        # also become a product-search
        # max-price filter.
        if target_price is not None:
            max_price = None

    return ExtractedEntities(
        variant_id=_extract_variant_id(text),
        category=_extract_category(text),
        color=_extract_color(text),
        size=_extract_size(text),
        material=_extract_material(text),
        branch_name=_extract_branch(text),
        min_price=min_price,
        max_price=max_price,
        target_price=target_price,
        min_discount_percentage=_extract_discount(text),
        quantity=_extract_quantity(text),
        authorization_mode=_extract_authorization_mode(text),
        ordinal_reference=_extract_ordinal(text),
    )


# ============================================================================
# Intent classification
# ============================================================================

def classify_intent(
    message: str,
) -> str:
    text = _normalize(
        message
    )

    # Explicit Smart Cart wording has
    # highest priority.
    if _contains_any(
        text,
        {
            "smart cart",
            "auto buy",
            "autobuy",
            "buy automatically",
            "automatically buy",
            "automatic purchase",
        },
    ):
        return "smart_cart_create"

    # Discount-based notify request is also
    # treated as a notify-only Smart Cart rule.
    #
    # IMPORTANT: this variable must be defined
    # OUTSIDE the previous if block.
    discount_notify_request = (
        bool(
            re.search(
                r"\b\d+(?:\.\d+)?\s*%",
                text,
                flags=re.IGNORECASE,
            )
        )
        and _contains_any(
            text,
            {
                "notify me",
                "notify karna",
                "mujhe batana",
                "tell me when",
            },
        )
    )

    if discount_notify_request:
        return "smart_cart_create"

    # Ordinary alerts come after Smart Cart
    # detection.
    if _contains_any(
        text,
        {
            "notify me",
            "alert me",
            "tell me when",
            "mujhe batana",
            "price alert",
            "restock alert",
            "sale alert",
        },
    ):
        return "alert_create"

    conditional_purchase = (
        _contains_any(
            text,
            {
                "if",
                "agar",
                "when",
            },
        )
        and _contains_any(
            text,
            {
                "buy",
                "purchase",
                "khareed",
                "kharid",
            },
        )
    )

    if conditional_purchase:
        return "smart_cart_create"
    

    cart_add_phrase = (
        _contains_any(
            text,
            {
                "add to cart",
                "put in cart",
                "put it in cart",
                "cart mein daal",
                "cart me daal",
                "cart mein dalo",
                "cart me dalo",
            },
        )
        or bool(
            re.search(
                r"\badd\b.*\bto\s+(?:my\s+)?cart\b",
                text,
                flags=re.IGNORECASE,
            )
        )
        or bool(
            re.search(
                r"\bput\b.*\bin\s+(?:my\s+)?cart\b",
                text,
                flags=re.IGNORECASE,
            )
        )
    )

    if cart_add_phrase:
        return "add_to_cart"

    wishlist_add_phrase = (
        _contains_any(
            text,
            {
                "add to wishlist",
                "save to wishlist",
                "wishlist mein",
                "wishlist me",
            },
        )
        or bool(
            re.search(
                r"\badd\b.*\bto\s+(?:my\s+)?wishlist\b",
                text,
                flags=re.IGNORECASE,
            )
        )
        or bool(
            re.search(
                r"\bput\b.*\bin\s+(?:my\s+)?wishlist\b",
                text,
                flags=re.IGNORECASE,
            )
        )
    )

    if wishlist_add_phrase:
        return "add_to_wishlist"

    if _contains_any(
        text,
        {
            "reserve",
            "hold this",
            "hold it",
            "hold for me",
            "mere liye hold",
        },
    ):
        return "reservation_create"

    if _contains_any(
        text,
        {
            "in stock",
            "stock mein",
            "stock me",
            "available",
            "availability",
            "stock available",
            "stock check",
        },
    ):
        return "stock_check"

    if _contains_any(
        text,
        {
            "buy",
            "purchase",
            "checkout",
            "check out",
            "khareed lo",
            "kharid lo",
            "order this",
            "order it",
        },
    ):
        return "purchase"

    if _contains_any(
        text,
        {
            "show",
            "find",
            "search",
            "looking for",
            "i want",
            "i need",
            "mujhe",
            "chahiye",
            "chahye",
            "dikhao",
            "dikha do",
        },
    ):
        return "product_search"

    return "unknown"


# ============================================================================
# Clarification
# ============================================================================


def _has_context_reference(
    text: str,
) -> bool:
    return _contains_any(
        text,
        CONTEXT_REFERENCE_WORDS,
    )


def _has_item_reference(
    text: str,
    entities: ExtractedEntities,
) -> bool:
    return bool(
        entities.variant_id
        or entities.ordinal_reference
        or _has_context_reference(text)
        or entities.category
    )


def _clarification_for(
    *,
    intent: str,
    text: str,
    entities: ExtractedEntities,
) -> tuple[
    bool,
    str | None,
]:
    needs_item = {
        "stock_check",
        "add_to_cart",
        "add_to_wishlist",
        "reservation_create",
        "smart_cart_create",
        "purchase",
        "alert_create",
    }

    if (
        intent in needs_item
        and not _has_item_reference(
            text,
            entities,
        )
    ):
        return (
            True,
            (
                "Which item do you mean? "
                "You can choose one from the "
                "previous results or tell me "
                "the product you want."
            ),
        )

    if (
        intent == "smart_cart_create"
        and entities.target_price is None
        and entities.min_discount_percentage is None
    ):
        return (
            True,
            (
                "What price or minimum "
                "discount should trigger "
                "the Smart Cart rule?"
            ),
        )

    if (
        intent == "smart_cart_create"
        and entities.authorization_mode is None
    ):
        return (
            True,
            (
                "Should I only notify you "
                "when the condition matches, "
                "or are you authorizing "
                "automatic purchase?"
            ),
        )

    if intent == "unknown":
        return (
            True,
            (
                "What would you like help "
                "with? I can search products, "
                "check stock, manage your cart, "
                "set Smart Cart rules, or help "
                "with a purchase."
            ),
        )

    return (
        False,
        None,
    )


# ============================================================================
# Customer Interaction Agent
# ============================================================================


class CustomerInteractionAgent:
    """
    Deterministic language-understanding layer.

    This agent extracts customer intent and entities. It does not determine
    authoritative prices, inventory, branch availability, or purchase results.
    Those remain the responsibility of specialist agents and database-backed
    services.
    """

    agent_key = "customer_interaction_agent"

    def parse(
        self,
        message: str,
    ) -> ParsedCustomerMessage:
        raw_message = message.strip()

        language = detect_language(raw_message)
        intent = classify_intent(raw_message)

        entities = extract_entities(
            raw_message,
            intent=intent,
        )

        text = _normalize(raw_message)

        (
            requires_clarification,
            clarification_question,
        ) = _clarification_for(
            intent=intent,
            text=text,
            entities=entities,
        )

        return ParsedCustomerMessage(
            raw_message=raw_message,
            language=language,
            intent=intent,
            entities=entities,
            requires_clarification=requires_clarification,
            clarification_question=clarification_question,
        )


customer_interaction_agent = CustomerInteractionAgent()
