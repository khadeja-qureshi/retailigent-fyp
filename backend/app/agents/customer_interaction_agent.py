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
    "teal": "Teal",
    "turquoise": "Turquoise",
    "aqua": "Aqua",
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
    "bag": "bag",
    "bags": "bag",
    "tote bag": "bag",
    "tote bags": "bag",
    "tote": "bag",
    "totes": "bag",
    "handbag": "bag",
    "handbags": "bag",
    "hand bag": "bag",
    "hand bags": "bag",
    "purse": "bag",
    "purses": "bag",

    # Footwear aliases.  These all map to the top-level
    # database category ``Footwear``.  Child categories such
    # as ``footwear-women`` and ``footwear-men`` still match
    # because ProductAgent compares normalized category/slug
    # tokens.
    "footwear": "footwear",
    "shoe": "footwear",
    "shoes": "footwear",
    "sneaker": "footwear-shoes",
    "sneakers": "footwear-shoes",
    "trainer": "footwear-shoes",
    "trainers": "footwear-shoes",
    "sandal": "footwear-heels",
    "sandals": "footwear-heels",
    "slipper": "footwear-slippers",
    "slippers": "footwear-slippers",
    "khussa": "footwear-khussa",
    "khussas": "footwear-khussa",
    "heel": "footwear-heels",
    "heels": "footwear-heels",
}


BRANCH_ALIASES = {
    "gulberg": "Gulberg",
    "clifton": "Clifton",
    "dha": "DHA",
    "f-10": "F-10",
    "f 10": "F-10",
    "karachi": "Karachi",
    "lahore": "Lahore",
    "islamabad": "Islamabad",
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


NUMBER = r"([0-9][0-9,]*(?:\.[0-9]+)?)"


def _normalize(text: str) -> str:
    text = (
        text.strip()
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
    )
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
    Extract an explicitly named product from common customer actions.

    Examples:
      "Do you have Classic Cotton Casual Shirt in size M?"
        -> "Classic Cotton Casual Shirt"

      "Add Classic Cotton Casual Shirt to cart"
        -> "Classic Cotton Casual Shirt"

      "Add Classic Cotton Casual Shirt to cart and wishlist"
        -> "Classic Cotton Casual Shirt"

      "Which branch has Classic Cotton Casual Shirt?"
        -> "Classic Cotton Casual Shirt"
    """

    patterns = [
        (
            r"^\s*(?:let\s+me\s+know\s+if|notify\s+me\s+when|"
            r"alert\s+me\s+when|tell\s+me\s+when)\s+"
            r"(.+?)"
            r"(?=,\s*(?:size|color|colour|material)\b|"
            r"\s+(?:drops?|falls?|reaches?|goes?\s+on\s+sale|"
            r"go\s+on\s+sale|is\s+back\s+in\s+stock|"
            r"comes?\s+back\s+in\s+stock)\b)"
        ),
        (
            r"^\s*(?:do\s+you\s+have|have\s+you\s+got|"
            r"do\s+you\s+sell|is\s+there\s+any)\s+"
            r"(.+?)"
            r"(?:[?.!]|$)"
        ),
        (
            r"^\s*(?:add|put|save)\s+"
            r"(.+?)\s+"
            r"(?:to|in|into)\s+"
            r"(?:my\s+|the\s+)?"
            r"(?:cart|wishlist|shopping\s+cart)"
            r"(?:\s+and\s+(?:cart|wishlist))?"
            r"(?:[?.!]|$)"
        ),
        (
            r"^\s*(?:add|put|save)\s+"
            r"(.+?)\s+"
            r"(?:to|in|into)\s+"
            r"(?:my\s+|the\s+)?"
            r"smart\s+cart"
            r"(?:\s+and\b.*)?"
            r"(?:[?.!]|$)"
        ),
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

        value = match.group(1).strip()

        normalized_reference = " ".join(
            value.casefold().split()
        )

        if normalized_reference in {
            "this",
            "this one",
            "this product",
            "this item",
            "that",
            "that one",
            "that product",
            "that item",
            "it",
        }:
            return None

        # Action quantities belong to the quantity entity, not the
        # catalog product name.
        #
        #   "Add 3 Classic Cotton Casual Shirts to Cart"
        #       -> "Classic Cotton Casual Shirts"
        value = re.sub(
            r"^\s*\d+\s+(?:x\s+)?",
            "",
            value,
            count=1,
            flags=re.IGNORECASE,
        ).strip()

        # Ordinal/context stock questions must resolve against the
        # previous result set. They are not literal product titles.
        #
        #   "Do you have 500 of the second kurta in stock?"
        #       product_name = None
        #       ordinal_reference = 2
        ordinal_words = "|".join(
            sorted(
                (re.escape(word) for word in ORDINAL_ALIASES),
                key=len,
                reverse=True,
            )
        )

        if re.search(
            rf"\b(?:{ordinal_words})\b",
            value,
            flags=re.IGNORECASE,
        ):
            return None

        value = re.sub(
            r"\s+\b(?:in\s+)?size\s+"
            r"(?:xxl|xl|xs|s|m|l|small|medium|large|"
            r"extra\s+small|extra\s+large|\d{2})\b.*$",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()

        value = re.sub(
            r"\s+\b(?:at|in)\s+"
            r"[a-z0-9\-\s']+\s+"
            r"(?:branch|store|shop|location)\b.*$",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()

        value = re.sub(
            r"\s+\b(?:in\s+stock|available|availability)\b\s*$",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()

        if re.match(
            r"^(?:size|stock|availability)\b",
            value,
            flags=re.IGNORECASE,
        ):
            return None

        if value.casefold() in {
            "",
            "it",
            "this",
            "this item",
            "that",
            "that item",
            "the item",
            "first one",
            "second one",
            "third one",
            "the first one",
            "the second one",
            "the third one",
        }:
            return None

        # A phrase made only of structured attributes is not an exact
        # product name. Example: "blue khaddar shirt" should remain
        # color=Blue, material=Khaddar, category=shirt instead of being
        # treated as a literal product title.
        generic_tokens = {
            *COLOR_ALIASES.keys(),
            *MATERIAL_ALIASES.keys(),
            *CATEGORY_ALIASES.keys(),
            "the",
            "a",
            "an",
            "product",
            "item",
        }
        residual_tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", value.casefold())
            if token not in generic_tokens
        ]

        if not residual_tokens:
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
    # Explicit "size X" form. Supports both clothing sizes
    # (S/M/L/XL) and numeric footwear sizes such as 38, 39, 40, 41.
    size_first_match = re.search(
        r"\b"
        r"(?:my\s+|usual\s+|preferred\s+)?"
        r"size\s*"
        r"(?:is\s*)?"
        r"[:\-]?\s*"
        r"(xxl|xl|xs|s|m|l|"
        r"small|medium|large|"
        r"extra small|extra large|"
        r"\d{2})"
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

        if raw.isdigit():
            return raw

        return SIZE_ALIASES.get(raw)

    # "40 size" / "M size" form.
    size_last_match = re.search(
        r"\b"
        r"(xxl|xl|xs|s|m|l|"
        r"small|medium|large|"
        r"extra small|extra large|"
        r"\d{2})"
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

        if raw.isdigit():
            return raw

        return SIZE_ALIASES.get(raw)

    # Product immediately followed by a size.
    # Examples:
    #   "shirt M"
    #   "sneakers 40"
    product_size_match = re.search(
        r"\b"
        r"(?:kurta|kurtas|"
        r"shirt|shirts|"
        r"dress|dresses|"
        r"suit|suits|"
        r"shoe|shoes|"
        r"sneaker|sneakers|"
        r"trainer|trainers|"
        r"sandal|sandals|"
        r"slipper|slippers|"
        r"khussa|khussas|"
        r"heel|heels)"
        r"\s+"
        r"(xxl|xl|xs|s|m|l|"
        r"small|medium|large|"
        r"extra small|extra large|"
        r"\d{2})"
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

        if raw.isdigit():
            return raw

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
        # "Add 3 Classic Cotton Casual Shirts to Cart"
        (
            r"^\s*(?:add|put|save|buy|purchase|reserve)\s+"
            r"(\d+)\b"
        ),
        # "Do you have 500 of the second kurta in stock?"
        (
            r"\b(?:do\s+you\s+have|have)\s+"
            r"(\d+)\s+(?:of\b|\b)"
        ),
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
            + r"\s*(?:rs\.?|pkr|rupay|rupees?)?\s*"
            r"(?:se neeche|se kam)\b"
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
            + r"\s*(?:rs\.?|pkr|rupay|rupees?)?\s*"
            r"(?:se neeche|se kam)\b"
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
        "let me know",
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

    if intent in {
        "smart_cart_create",
        "alert_create",
    }:
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
    text = _normalize(
        message
    )

    support_phrase_match = (
        _contains_any(
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
                "wrong order",
                "doesn't match what i ordered",
                "doesnt match what i ordered",
                "does not match what i ordered",
                "item doesn't match",
                "item doesnt match",
                "item does not match",
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

                "help with my order",
                "help me with my order",
                "need help with my order",

                "shikayat",
                "complaint karni",
                "masla hal",

                "customer service se baat",
                "insan se baat",
                "insaan se baat",

                "support chahiye",
                "help chahiye",

                "damaged mila",
                "damaged item mila",
                "item damaged hai",

                "order nahi aya",
                "order nahi aaya",
                "order abhi tak nahi aya",
                "order abhi tak nahi aaya",

                "delivery nahi ayi",
                "delivery nahi aayi",

                "koi help nahi kar raha",
                "koi madad nahi kar raha",
                "my issue",
"my complaint",
"my ticket",
"support ticket",
"ticket status",
"ticket update",
"complaint status",
"complaint update",
"issue status",
"issue update",

"looked at my issue",
"looked at my complaint",
"looked at my ticket",

"any update on my issue",
"any update on my complaint",
"any update on my ticket",

"what happened to my issue",
"what happened to my complaint",
"what happened to my ticket",

"what is happening with my issue",
"what is happening with my complaint",
"what is happening with my ticket",

"has support replied",
"has anyone replied",
"has anyone looked",

"meri complaint",
"mera ticket",
"mere ticket",
"meri shikayat",

"complaint ka kya hua",
"ticket ka kya hua",
"issue ka kya hua",

"complaint ka update",
"ticket ka update",
"issue ka update",
            },
        )
    )

    support_pattern_match = any(
        re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
        for pattern in (
            # ------------------------------------------------------
            # Natural English late/delayed order wording:
            #
            # "my order is extremely late"
            # "the order is very late"
            # "my order has been delayed"
            # ------------------------------------------------------
            (
                r"\b"
                r"(?:my\s+|the\s+)?"
                r"order\b"
                r".{0,80}?"
                r"\b"
                r"(?:late|delayed|delay)"
                r"\b"
            ),

            # ------------------------------------------------------
            # Delivery variants:
            #
            # "my delivery is very late"
            # "delivery has been delayed"
            # ------------------------------------------------------
            (
                r"\b"
                r"(?:my\s+|the\s+)?"
                r"delivery\b"
                r".{0,80}?"
                r"\b"
                r"(?:late|delayed|delay)"
                r"\b"
            ),

            # ------------------------------------------------------
            # Roman Urdu:
            #
            # "mera order bohat late hai"
            # "mera order late ho gaya"
            # ------------------------------------------------------
            (
                r"\b"
                r"(?:mera|meri)\s+"
                r"order\b"
                r".{0,80}?"
                r"\b"
                r"(?:late|delay|delayed)"
                r"\b"
            ),

            # ------------------------------------------------------
            # Roman Urdu missing-order variants:
            #
            # "mera order nahi aya"
            # "mera order abhi tak nahi aaya"
            # ------------------------------------------------------
            (
                r"\b"
                r"(?:mera|meri)\s+"
                r"order\b"
                r".{0,80}?"
                r"\b"
                r"nahi\s+"
                r"(?:aya|aaya|pohncha|pohcha)"
                r"\b"
            ),

            # ------------------------------------------------------
            # Help + order:
            #
            # "I need help with my order"
            # "help me regarding my order"
            # ------------------------------------------------------
            (
                r"\b"
                r"(?:help|support)"
                r"\b"
                r".{0,60}?"
                r"\border\b"
            ),

            # ------------------------------------------------------
            # Order + help:
            #
            # "my order has a problem, please help"
            # ------------------------------------------------------
            (
                r"\border\b"
                r".{0,80}?"
                r"\b"
                r"(?:help|support)"
                r"\b"
            ),

            # ------------------------------------------------------
            # Roman Urdu lack-of-help complaint:
            #
            # "koi help nahi kar raha"
            # "koi madad nahi kar raha"
            # ------------------------------------------------------
            (
                r"\b"
                r"(?:help|madad)"
                r"\b"
                r".{0,40}?"
                r"\bnahi\b"
            ),

            (
    r"\b"
    r"(?:my\s+)?"
    r"(?:issue|complaint|ticket)"
    r"\b"
    r".{0,80}?"
    r"\b"
    r"(?:update|status|looked|reviewed|replied)"
    r"\b"
),

(
    r"\b"
    r"(?:update|status)"
    r"\b"
    r".{0,60}?"
    r"\b"
    r"(?:issue|complaint|ticket)"
    r"\b"
),

(
    r"\b"
    r"(?:complaint|ticket|issue)"
    r"\s+ka\s+"
    r"(?:kya\s+hua|update|status)"
    r"\b"
),
        )
    )

    if (
        support_phrase_match
        or
        support_pattern_match
    ):
        return "support_request"

    # Location-information questions must be classified before generic
    # availability wording such as "do you have".  Otherwise a request
    # like "Which branches do you have in Karachi?" becomes stock_check.
    location_information_request = (
        bool(re.search(
            r"\bwhich\s+(?:branches|stores)\b",
            text,
            flags=re.IGNORECASE,
        ))
        or bool(re.search(
            r"\b(?:branches|stores)\s+in\s+",
            text,
            flags=re.IGNORECASE,
        ))
        or bool(re.search(
            r"\b(?:what\s+time|when)\b.*"
            r"\b(?:branch|store)\b.*"
            r"\b(?:open|opens|close|closes|closing)\b",
            text,
            flags=re.IGNORECASE,
        ))
        or bool(re.search(
            r"\bwhere\s+is\b.*\b(?:branch|store)\b",
            text,
            flags=re.IGNORECASE,
        ))
        or _contains_any(
            text,
            {
                "nearest branch",
                "nearest store",
                "closest branch",
                "closest store",
                "near me",
                "nearby branch",
                "nearby store",
                "mere qareeb",
                "mere kareeb",
                "mere nazdeek",
                "mere nazdiq",
                "qareeb store",
                "qareeb branch",
                "kareeb store",
                "kareeb branch",
            },
        )
    )

    if location_information_request:
        return "store_location_search"

    # --------------------------------------------------------------
    # KEEP THE REST OF YOUR EXISTING classify_intent()
    # CODE BELOW THIS POINT EXACTLY AS IT IS.
    # --------------------------------------------------------------

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
            "let me know",
            "mujhe batana",
            "price alert",
            "restock alert",
            "sale alert",
            "back in stock",
            "goes on sale",
            "go on sale",
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

    availability_question = (
        _contains_any(
            text,
            {
                "in stock",
                "stock mein",
                "stock me",
                "available",
                "availability",
                "stock available",
                "stock check",
                "do you have",
                "does this come in",
                "does it come in",
                "have you got",
                "have you got any",
                "got any",
                "do you sell",
                "is there any",
                "is this available",
                "is it available",
                "is this in stock",
                "is it in stock",
                "hai kya",
                "milta hai",
                "milti hai",
                "mil jayega",
                "mil jaega",
                "mil sakta hai",
                "maujood hai",
                "rakhte ho",
                "stock mein hai",
                "stock me hai",
            },
        )
    )

    if availability_question:
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
                "i usually prefer",
                "i normally prefer",
                "i like",
                "my usual size",
                "my size is",
                "i usually wear",
                "i normally wear",
                "i usually shop",
                "i normally shop",
                "my preferred branch",
                "my preferred store",
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

        "branches",
        "stores",

        "which branch",
        "which branches",
        "which store",
        "which stores",

        "our branches",
        "your branches",
        "your stores",

        "branches in",
        "stores in",
        "branch in",
        "store in",

        "where are your branches",
        "where are your stores",
        "where are the branches",
        "where are the stores",

        "nearest branch",
        "nearest store",
        "closest branch",
        "closest store",

        "nearby branch",
        "nearby store",

        "near me",
        "close to me",

        "qareeb branch",
        "qareeb store",
        "kareeb branch",
        "kareeb store",
        "nazdeek branch",
        "nazdeek store",
        "nazdik branch",
        "nazdik store",

        "mere qareeb",
        "mere kareeb",
        "mere nazdeek",
        "mere nazdiq",

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
        "where is the branch",

        "gulberg branch",
        "clifton branch",
        "dha branch",

        "karachi branch",
        "karachi branches",
        "branches in karachi",
        "stores in karachi",

        "lahore branch",
        "lahore branches",
        "branches in lahore",
        "stores in lahore",

        "islamabad branch",
        "islamabad branches",
        "branches in islamabad",
        "stores in islamabad",
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
        or
        entities.product_name
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