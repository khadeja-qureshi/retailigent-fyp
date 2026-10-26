from __future__ import annotations

from pathlib import Path


ORCHESTRATOR_PATH = Path(
    "app/agents/orchestrator_agent.py"
)


HELPER_CODE = r'''

def _extract_stock_requested_quantity(
    message: str,
    parsed: ParsedCustomerMessage,
) -> int | None:
    """
    Extract the requested quantity specifically for stock-check questions.

    Examples supported:
        Do you have 500 of the second kurta in stock?
        Do you have 25 units of this?
        Is quantity 40 available?
        500 of the first shirt

    Structured parser quantity is preferred when available.

    The fallback patterns deliberately avoid ordinal references such as
    "second", so "500 of the second kurta" resolves quantity=500 rather
    than quantity=2.
    """

    if parsed.entities.quantity is not None:
        try:
            quantity = int(
                parsed.entities.quantity
            )

        except (
            TypeError,
            ValueError,
        ):
            quantity = 0

        if quantity > 0:
            return quantity

    text = re.sub(
        r"\s+",
        " ",
        message
        .strip()
        .casefold(),
    )

    patterns = (
        # "do you have 500 of ..."
        r"\b(?:have|has)\s+(\d+)\b",

        # "500 units / 500 pieces / 500 items"
        r"\b(\d+)\s+"
        r"(?:units?|pieces?|items?|pcs?)\b",

        # "quantity 500" / "qty: 500"
        r"\b(?:quantity|qty)\s*"
        r"(?:is|=|:)?\s*(\d+)\b",

        # "500 of the second kurta"
        r"\b(\d+)\s+of\b",
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        try:
            quantity = int(
                match.group(1)
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        if quantity > 0:
            return quantity

    return None
'''


OLD_QUANTITY_BLOCK = '''                requested_quantity = (
                    int(parsed.entities.quantity)
                    if parsed.entities.quantity is not None
                    else None
                )
'''


NEW_QUANTITY_BLOCK = '''                requested_quantity = (
                    _extract_stock_requested_quantity(
                        message,
                        parsed,
                    )
                )
'''


OLD_ZERO_ONLY_BLOCK = '''                    if (
                        relevant_rows
                        and all(
                            int(row.get("available_quantity") or 0) <= 0
                            for row in relevant_rows
                        )
                    ):
                        record_demand_signal(
                            signal_type="insufficient_stock",
                            customer_id=customer_id,
                            variant_id=variant_id,
                            branch_id=(
                                str(relevant_rows[0].get("branch_id"))
                                if requested_branch
                                and relevant_rows[0].get("branch_id") is not None
                                else None
                            ),
                            metadata={
                                "requested_branch": requested_branch,
                                "checked_branch_count": len(relevant_rows),
                                "source": "stock_check",
                            },
                        )
'''


NEW_STOCK_BLOCK = '''                    if not relevant_rows:
                        continue

                    available_quantity = sum(
                        max(
                            0,
                            int(
                                row.get(
                                    "available_quantity"
                                )
                                or 0
                            ),
                        )
                        for row
                        in relevant_rows
                    )

                    stock_is_insufficient = (
                        available_quantity <= 0
                        or (
                            requested_quantity
                            is not None
                            and
                            requested_quantity
                            > available_quantity
                        )
                    )

                    if stock_is_insufficient:
                        metadata = {
                            "requested_branch":
                                requested_branch,

                            "checked_branch_count":
                                len(
                                    relevant_rows
                                ),

                            "available_quantity":
                                available_quantity,

                            "source":
                                "stock_check",
                        }

                        if (
                            requested_quantity
                            is not None
                        ):
                            metadata[
                                "requested_quantity"
                            ] = (
                                requested_quantity
                            )

                            metadata[
                                "shortfall_quantity"
                            ] = max(
                                0,
                                requested_quantity
                                -
                                available_quantity,
                            )

                        record_demand_signal(
                            signal_type=(
                                "insufficient_stock"
                            ),
                            customer_id=(
                                customer_id
                            ),
                            variant_id=(
                                variant_id
                            ),
                            branch_id=(
                                str(
                                    relevant_rows[
                                        0
                                    ].get(
                                        "branch_id"
                                    )
                                )
                                if (
                                    requested_branch
                                    and
                                    relevant_rows[
                                        0
                                    ].get(
                                        "branch_id"
                                    )
                                    is not None
                                )
                                else None
                            ),
                            metadata=metadata,
                        )
'''


def main() -> None:
    if not ORCHESTRATOR_PATH.exists():
        raise SystemExit(
            "ERROR: Could not find "
            f"{ORCHESTRATOR_PATH}"
        )

    source = ORCHESTRATOR_PATH.read_text(
        encoding="utf-8"
    )

    original = source

    # ---------------------------------------------------------
    # 1. Ensure `re` import exists
    # ---------------------------------------------------------

    if "import re\n" not in source:
        source = source.replace(
            "import logging\n",
            "import logging\nimport re\n",
            1,
        )

    # ---------------------------------------------------------
    # 2. Add stock quantity extraction helper
    # ---------------------------------------------------------

    if (
        "def _extract_stock_requested_quantity("
        not in source
    ):
        marker = (
            "logger = logging.getLogger(\n"
            "    __name__\n"
            ")\n"
        )

        if marker not in source:
            raise SystemExit(
                "ERROR: Could not locate logger "
                "section in orchestrator_agent.py."
            )

        source = source.replace(
            marker,
            marker + HELPER_CODE,
            1,
        )

        print(
            "Added "
            "_extract_stock_requested_quantity()."
        )

    else:
        print(
            "_extract_stock_requested_quantity() "
            "already exists."
        )

    # ---------------------------------------------------------
    # 3. Replace quantity lookup
    # ---------------------------------------------------------

    if OLD_QUANTITY_BLOCK in source:
        source = source.replace(
            OLD_QUANTITY_BLOCK,
            NEW_QUANTITY_BLOCK,
            1,
        )

        print(
            "Updated stock requested quantity "
            "lookup."
        )

    elif NEW_QUANTITY_BLOCK in source:
        print(
            "Stock requested quantity lookup "
            "already updated."
        )

    else:
        print(
            "WARNING: Original requested_quantity "
            "block was not found."
        )

    # ---------------------------------------------------------
    # 4. Replace old zero-only demand logic
    # ---------------------------------------------------------

    if OLD_ZERO_ONLY_BLOCK in source:
        source = source.replace(
            OLD_ZERO_ONLY_BLOCK,
            NEW_STOCK_BLOCK,
            1,
        )

        print(
            "Updated insufficient-stock "
            "comparison logic."
        )

    elif (
        '"shortfall_quantity"'
        in source
        and
        '"available_quantity"'
        in source
    ):
        print(
            "Insufficient-stock comparison "
            "already appears updated."
        )

    else:
        print(
            "WARNING: Could not locate the old "
            "zero-only stock block."
        )

    # ---------------------------------------------------------
    # 5. Ensure the helper call exists
    # ---------------------------------------------------------

    if (
        "_extract_stock_requested_quantity("
        not in source
    ):
        raise SystemExit(
            "ERROR: Quantity helper was not "
            "installed."
        )

    # ---------------------------------------------------------
    # 6. Ensure shortfall logging exists
    # ---------------------------------------------------------

    required = (
        '"requested_quantity"',
        '"available_quantity"',
        '"shortfall_quantity"',
        '"insufficient_stock"',
    )

    missing = [
        item
        for item in required
        if item not in source
    ]

    if missing:
        raise SystemExit(
            "ERROR: Patch verification failed. "
            f"Missing: {missing}"
        )

    # ---------------------------------------------------------
    # 7. Backup current file
    # ---------------------------------------------------------

    backup_path = (
        ORCHESTRATOR_PATH
        .with_suffix(
            ".py.phase15_backup"
        )
    )

    if not backup_path.exists():
        backup_path.write_text(
            original,
            encoding="utf-8",
        )

        print(
            f"Backup created: {backup_path}"
        )

    # ---------------------------------------------------------
    # 8. Save patched orchestrator
    # ---------------------------------------------------------

    ORCHESTRATOR_PATH.write_text(
        source,
        encoding="utf-8",
    )

    print()
    print(
        "SUCCESS: "
        "app/agents/orchestrator_agent.py "
        "has been patched."
    )

    print()
    print(
        "Next run:"
    )

    print(
        "python -m py_compile "
        "app\\agents\\orchestrator_agent.py"
    )


if __name__ == "__main__":
    main()