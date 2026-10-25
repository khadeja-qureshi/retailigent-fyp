from __future__ import annotations

import re

from app.schemas.chat import (
    ExtractedEntities,
    ParsedCustomerMessage,
    StockStatusBlock,
)


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


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _has_phrase(text: str, phrase: str) -> bool:
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
        _has_phrase(text, phrase)
        for phrase in phrases
    )


def _parse_number(value: str) -> float:
    return float(
        value.replace(",", "")
    )


def detect_language(message: str) -> str:
    text = _normalize(message)

    tokens = set(
        re.findall(
            r"[a-zA-Z]+",
            text,
        )
    )

    has_roman_urdu = bool(
        tokens & ROMAN_URDU_MARKERS
    )

    has_english = bool(
        tokens & ENGLISH_MARKERS
    )

    if has_roman_urdu and has_english:
        return "mixed"

    if has_roman_urdu:
        return "roman_urdu"

    return "english"


def _extract_variant_id(
    text: str,
) -> str | None:
    match = UUID_RE.search(text)

    if not match:
        return None

    return match.group(0)


def _extract_product_name(
    text: str,
) -> str | None:
    """
    Extract a product phrase from natural
    branch/location questions.
    """

    patterns = [
        (
            r"\bwhich\s+"
            r"(?:branch|store)\s+"
            r"has\s+"
            r"(.+?)"
            r"(?:[?.!]|$)"
        ),
        (
            r"\bwhere\s+"
            r"(?:can\s+i\s+find|is)\s+"
            r"(.+?)"
            r"(?:[?.!]|$)"
        ),
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        value = (
            match.group(1).strip()
        )

        # "Which branch has size M?"
        # means refine previous product context,
        # not a product literally called "size M".
        if re.match(
            r"^(?:size|stock|availability)\b",
            value,
            flags=re.IGNORECASE,
        ):
            return None

        return value

    return None


def _extract_color(
    text: str,
) -> str | None:
    for word, normalized in (
        COLOR_ALIASES.items()
    ):
        if _has_phrase(text, word):
            return normalized

    return None


def _extract_material(
    text: str,
) -> str | None:
    for word, normalized in (
        MATERIAL_ALIASES.items()
    ):
        if _has_phrase(text, word):
            return normalized

    return None


def _extract_category(
    text: str,
) -> str | None:
    for word, normalized in (
        CATEGORY_ALIASES.items()
    ):
        if _has_phrase(text, word):
            return normalized

    return None


def _extract_branch(
    text: str,
) -> str | None:
    for word, normalized in (
        BRANCH_ALIASES.items()
    ):
        if _has_phrase(text, word):
            return normalized

    return None


def _extract_size(
    text: str,
) -> str | None:
    size_first_match = re.search(
        r"\b"
        r"(?:my\s+|usual\s+|preferred\s+)?"
        r"size\s*"
        r"(?:is\s*)?"
        r"[:\-]?\s*"
        r"(xxl|xl|xs|s|m|l|"
        r"small|medium|large|"
        r"extra small|extra large)"
        r"\b",
        text,
        flags=re.IGNORECASE,
    )

    if size_first_match:
        raw = (
            size_first_match
            .group(1)
            .lower()
        )

        return SIZE_ALIASES.get(raw)

    size_last_match = re.search(
        r"\b"
        r"(xxl|xl|xs|s|m|l|"
        r"small|medium|large|"
        r"extra small|extra large)"
        r"\s+size\b",
        text,
        flags=re.IGNORECASE,
    )

    if size_last_match:
        raw = (
            size_last_match
            .group(1)
            .lower()
        )

        return SIZE_ALIASES.get(raw)

    product_size_match = re.search(
        r"\b"
        r"(?:kurta|kurtas|"
        r"shirt|shirts|"
        r"dress|dresses|"
        r"suit|suits)"
        r"\s+"
        r"(xxl|xl|xs|s|m|l|"
        r"small|medium|large|"
        r"extra small|extra large)"
        r"\b",
        text,
        flags=re.IGNORECASE,
    )

    if product_size_match:
        raw = (
            product_size_match
            .group(1)
            .lower()
        )

        return SIZE_ALIASES.get(raw)

    return None


def _extract_ordinals(
    text: str,
) -> list[int]:
    matches: list[
        tuple[int, int]
    ] = []

    for word, ordinal in (
        ORDINAL_ALIASES.items()
    ):
        pattern = (
            re.escape(word)
            if " " in word
            else (
                rf"\b"
                rf"{re.escape(word)}"
                rf"\b"
            )
        )

        for match in re.finditer(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):
            matches.append(
                (
                    match.start(),
                    ordinal,
                )
            )

    matches.sort(
        key=lambda item: item[0]
    )

    ordinals: list[int] = []

    for _, ordinal in matches:
        if ordinal not in ordinals:
            ordinals.append(ordinal)

    return ordinals


def _extract_ordinal(
    text: str,
) -> int | None:
    ordinals = _extract_ordinals(text)

    if not ordinals:
        return None

    return ordinals[0]


def _extract_quantity(
    text: str,
) -> int | None:
    patterns = [
        (
            r"\b(?:quantity|qty)"
            r"\s*[:\-]?\s*(\d+)\b"
        ),
        (
            r"\b(\d+)\s*"
            r"(?:items?|pieces?|pcs?|units?)\b"
        ),
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
        and
        _contains_any(
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
    text = _normalize(message)

    (
        min_price,
        max_price,
    ) = _extract_price_range(text)

    target_price = None

    if intent == "smart_cart_create":
        target_price = (
            _extract_target_price(text)
        )

        if target_price is not None:
            max_price = None

    return ExtractedEntities(
        product_name=(
            _extract_product_name(text)
        ),
        variant_id=(
            _extract_variant_id(text)
        ),
        category=(
            _extract_category(text)
        ),
        color=(
            _extract_color(text)
        ),
        size=(
            _extract_size(text)
        ),
        material=(
            _extract_material(text)
        ),
        branch_name=(
            _extract_branch(text)
        ),
        min_price=min_price,
        max_price=max_price,
        target_price=target_price,
        min_discount_percentage=(
            _extract_discount(text)
        ),
        quantity=(
            _extract_quantity(text)
        ),
        authorization_mode=(
            _extract_authorization_mode(text)
        ),
        ordinal_reference=(
            _extract_ordinal(text)
        ),
        ordinal_references=(
            _extract_ordinals(text)
        ),
    )


def classify_intent(
    message: str,
) -> str:
    text = _normalize(message)

    if _contains_any(
        text,
        {
            "customer support",
            "customer service",
            "talk to a human",
            "speak to a human",
            "human agent",
            "live agent",
            "file a complaint",
            "make a complaint",
            "i want to complain",
            "complaint",
            "complain",
            "refund",
            "wrong item",
            "damaged item",
            "broken item",
            "order delayed",
            "order late",
            "delivery delayed",
            "late delivery",
            "not received my order",
            "never received",
            "poor service",
            "bad experience",
            "not satisfied",
            "shikayat",
            "complaint karni",
            "masla hal",
            "customer service se baat",
            "insan se baat",
            "insaan se baat",
            "support chahiye",
        },
    ):
        return "support_request"

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

    discount_notify_request = (
        bool(
            re.search(
                r"\b\d+(?:\.\d+)?\s*%",
                text,
                flags=re.IGNORECASE,
            )
        )
        and
        _contains_any(
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
        and
        _contains_any(
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
        or
        bool(
            re.search(
                r"\badd\b.*\bto\s+"
                r"(?:my\s+)?cart\b",
                text,
                flags=re.IGNORECASE,
            )
        )
        or
        bool(
            re.search(
                r"\bput\b.*\bin\s+"
                r"(?:my\s+)?cart\b",
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
        or
        bool(
            re.search(
                r"\badd\b.*\bto\s+"
                r"(?:my\s+)?wishlist\b",
                text,
                flags=re.IGNORECASE,
            )
        )
        or
        bool(
            re.search(
                r"\bput\b.*\bin\s+"
                r"(?:my\s+)?wishlist\b",
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

    preference_statement = (
        _contains_any(
            text,
            {
                "i prefer",
                "i like",
                "my usual size",
                "my size is",
                "i usually wear",
                "i normally wear",
                "mera size",
                "mujhe pasand",
            },
        )
        and not
        _contains_any(
            text,
            {
                "show",
                "find",
                "search",
                "recommend",
                "suggest",
            },
        )
    )

    if preference_statement:
        return "preference_update"

    if (
        re.search(
            r"\bwhich\s+(?:branch|store)\b",
            text,
            flags=re.IGNORECASE,
        )
        or
        re.search(
            r"\bwhere\b.*"
            r"\b(?:available|stock|find|get)\b",
            text,
            flags=re.IGNORECASE,
        )
    ):
        return "store_location_search"

    if _contains_any(
        text,
        {
            "store location",
            "store locations",
            "branch location",
            "branch locations",
            "nearest branch",
            "nearest store",
            "nearby branch",
            "nearby store",
            "store hours",
            "branch hours",
            "opening hours",
            "opening time",
            "closing time",
            "store address",
            "branch address",
            "where is your store",
            "where is the store",
            "where is your branch",
            "gulberg branch",
            "clifton branch",
            "dha branch",
        },
    ):
        return "store_location_search"

    occasion_recommendation = (
        _contains_any(
            text,
            {
                "wedding",
                "mehndi",
                "eid",
                "party",
                "formal event",
                "office wear",
                "casual wear",
                "winter wedding",
            },
        )
        and
        _contains_any(
            text,
            {
                "show",
                "find",
                "recommend",
                "suggest",
                "something",
                "suitable",
                "wear",
            },
        )
    )

    if occasion_recommendation:
        return "recommendation_search"

    if _contains_any(
        text,
        {
            "recommend",
            "recommendation",
            "recommendations",
            "suggest",
            "suggestion",
            "suggestions",
            "recommend for me",
            "what would suit me",
            "what should i buy",
            "mere liye suggest",
            "mere liye recommend",
            "suggest karo",
            "recommend karo",
            "kya loon",
            "kya lu",
        },
    ):
        return "recommendation_search"

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
        or
        entities.ordinal_reference
        or
        _has_context_reference(text)
        or
        entities.category
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
        and not
        _has_item_reference(
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
        and
        entities.target_price is None
        and
        entities.min_discount_percentage
        is None
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
        and
        entities.authorization_mode
        is None
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


def _reliable_memory_value(
    customer_context: dict | None,
    memory_key: str,
    *,
    minimum_confidence: float = 0.70,
):
    if not customer_context:
        return None

    remembered_facts = (
        customer_context.get(
            "remembered_facts"
        )
        or []
    )

    for fact in remembered_facts:
        if (
            fact.get("memory_key")
            != memory_key
        ):
            continue

        try:
            confidence = float(
                (
                    fact.get(
                        "effective_confidence"
                    )
                )
                if (
                    fact.get(
                        "effective_confidence"
                    )
                    is not None
                )
                else (
                    fact.get(
                        "confidence",
                        0.0,
                    )
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            confidence = 0.0

        if (
            confidence
            < minimum_confidence
        ):
            continue

        return fact.get(
            "memory_value"
        )

    return None


class CustomerInteractionAgent:
    """
    Deterministic customer-language layer.

    Detects language, intent and entities and
    composes customer-facing responses.

    It never determines authoritative price,
    stock, reservation or purchase outcomes.
    """

    agent_key = (
        "customer_interaction_agent"
    )

    def parse(
        self,
        message: str,
        *,
        customer_context: (
            dict | None
        ) = None,
    ) -> ParsedCustomerMessage:
        raw_message = (
            message.strip()
        )

        language = (
            detect_language(
                raw_message
            )
        )

        intent = (
            classify_intent(
                raw_message
            )
        )

        entities = (
            extract_entities(
                raw_message,
                intent=intent,
            )
        )

        # IMPORTANT:
        #
        # Do NOT inject remembered size/material/
        # color/category into an ordinary search.
        #
        # "Show me kurtas" must remain:
        #     category = kurta
        #
        # It must NOT silently become:
        #     category = kurta
        #     size = XL
        #
        # Personalization belongs exclusively to
        # RecommendationAgent.
        context_used: dict = {}

        text = _normalize(
            raw_message
        )

        (
            requires_clarification,
            clarification_question,
        ) = _clarification_for(
            intent=intent,
            text=text,
            entities=entities,
        )

        return ParsedCustomerMessage(
            raw_message=(
                raw_message
            ),
            language=language,
            intent=intent,
            entities=entities,
            context_used=(
                context_used
            ),
            requires_clarification=(
                requires_clarification
            ),
            clarification_question=(
                clarification_question
            ),
        )

    def compose_generic_clarification(
        self,
        language: str,
    ) -> str:
        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                "Thora clarify kar dein ke "
                "aap kya karna chahte hain?"
            )

        return (
            "Could you clarify what you mean?"
        )

    def compose_search_response(
        self,
        language: str,
        count: int,
        *,
        remembered_size: (
            str | None
        ) = None,
    ) -> str:
        if count == 0:
            if language in {
                "roman_urdu",
                "mixed",
            }:
                return (
                    "Mujhe koi matching "
                    "product nahi mila."
                )

            return (
                "I couldn't find any "
                "matching products."
            )

        if remembered_size:
            if language in {
                "roman_urdu",
                "mixed",
            }:
                return (
                    f"Mujhe {count} matching "
                    "products aap ke yaad "
                    "rakhe hue size "
                    f"{remembered_size} mein "
                    "milay hain."
                )

            return (
                f"I found {count} matching "
                f"product"
                f"{'s' if count != 1 else ''} "
                "in your remembered size "
                f"{remembered_size}."
            )

        if language == "roman_urdu":
            return (
                f"Mujhe {count} matching "
                "product milay hain."
            )

        if language == "mixed":
            return (
                f"Mujhe {count} matching "
                "products milay hain."
            )

        return (
            f"I found {count} matching "
            f"product"
            f"{'s' if count != 1 else ''}."
        )

    def compose_stock_response(
        self,
        language: str,
        block: StockStatusBlock,
        *,
        requested_branch: (
            str | None
        ) = None,
    ) -> str:
        total = sum(
            row.available_quantity
            for row in block.branches
        )

        if requested_branch:
            if total > 0:
                if language in {
                    "roman_urdu",
                    "mixed",
                }:
                    return (
                        f"Ji, {requested_branch} "
                        f"mein {total} available "
                        "hai."
                    )

                return (
                    f"Yes, {total} unit"
                    f"{'s are' if total != 1 else ' is'} "
                    "available at "
                    f"{requested_branch}."
                )

            if language in {
                "roman_urdu",
                "mixed",
            }:
                return (
                    f"{requested_branch} mein "
                    "abhi stock available "
                    "nahi hai."
                )

            return (
                "It is currently out of stock "
                f"at {requested_branch}."
            )

        if total > 0:
            if language in {
                "roman_urdu",
                "mixed",
            }:
                return (
                    f"Ji, total {total} unit"
                    f"{'s' if total != 1 else ''} "
                    "available hain."
                )

            return (
                f"There "
                f"{'are' if total != 1 else 'is'} "
                f"{total} unit"
                f"{'s' if total != 1 else ''} "
                "available."
            )

        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                "Abhi yeh item out of stock hai."
            )

        return (
            "This item is currently out of stock."
        )

    def compose_multi_stock_response(
        self,
        language: str,
        item_count: int,
    ) -> str:
        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                f"Maine {item_count} items ka "
                "stock parallel check kiya hai. "
                "Neeche har item ki verified "
                "branch availability hai."
            )

        return (
            f"I checked stock for {item_count} "
            "items in parallel. The stock cards "
            "below show verified branch "
            "availability for each item."
        )

    def compose_stock_reference_clarification(
        self,
        language: str,
    ) -> str:
        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                "Kaunsa exact item check karna hai? "
                "Aap first one, second one, "
                "ya koi product select kar sakte hain."
            )

        return (
            "Which exact item do you want me to check? "
            "You can say first one, second one, "
            "or select a product."
        )

    def compose_cart_added_response(
        self,
        language: str,
        quantity: int,
    ) -> str:
        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                f"Ji, {quantity} item "
                "cart mein add kar diya."
            )

        return (
            f"Added {quantity} item"
            f"{'s' if quantity != 1 else ''} "
            "to your cart."
        )

    def compose_wishlist_added_response(
        self,
        language: str,
    ) -> str:
        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                "Ji, item wishlist mein "
                "add kar diya."
            )

        return (
            "Added the item to your wishlist."
        )

    def compose_item_reference_clarification(
        self,
        language: str,
    ) -> str:
        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                "Kaunsa item? Aap first one, "
                "second one, ya koi product "
                "select kar sakte hain."
            )

        return (
            "Which item do you mean? "
            "You can say first one, second one, "
            "or select a product."
        )

    def compose_smart_cart_trigger_clarification(
        self,
        language: str,
    ) -> str:
        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                "Smart Cart rule kis price ya "
                "minimum discount par trigger "
                "hona chahiye?"
            )

        return (
            "What price or minimum discount "
            "should trigger the Smart Cart rule?"
        )

    def compose_smart_cart_authorization_clarification(
        self,
        language: str,
    ) -> str:
        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                "Condition match hone par sirf "
                "notify karun, ya automatic "
                "purchase ki authorization hai?"
            )

        return (
            "Should I only notify you when the "
            "condition matches, or are you "
            "authorizing automatic purchase?"
        )

    def compose_smart_cart_created_response(
        self,
        language: str,
        authorization_mode: str,
    ) -> str:
        if authorization_mode == "auto_buy":
            if language in {
                "roman_urdu",
                "mixed",
            }:
                return (
                    "Smart Cart rule bana diya. "
                    "Condition match hone par "
                    "authorized automatic purchase "
                    "attempt hoga."
                )

            return (
                "Your Smart Cart rule is active. "
                "When the condition matches, the "
                "authorized automatic purchase "
                "workflow can run."
            )

        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                "Smart Cart rule bana diya. "
                "Condition match hone par "
                "aapko notify kiya jayega."
            )

        return (
            "Your Smart Cart rule is active. "
            "You'll be notified when the "
            "condition matches."
        )

    def compose_purchase_response(
        self,
        language: str,
        result: dict,
    ) -> str:
        if result.get("success") is True:
            order_id = result.get(
                "order_id"
            )

            if language in {
                "roman_urdu",
                "mixed",
            }:
                return (
                    "Purchase successfully "
                    "complete ho gaya. "
                    f"Order ID: {order_id}"
                )

            return (
                "Purchase completed successfully. "
                f"Order ID: {order_id}"
            )

        reason = (
            result.get("reason")
            or
            "The purchase could not be completed."
        )

        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                "Purchase complete nahi ho saka. "
                f"{reason}"
            )

        return (
            "The purchase could not be completed. "
            f"{reason}"
        )

    def compose_unhandled_response(
        self,
        language: str,
    ) -> str:
        if language in {
            "roman_urdu",
            "mixed",
        }:
            return (
                "Request samajh aa gaya, lekin "
                "yeh action abhi orchestrator "
                "se connected nahi hai."
            )

        return (
            "I understood the request, "
            "but this action has not been "
            "connected to the orchestrator yet."
        )


customer_interaction_agent = (
    CustomerInteractionAgent()
)