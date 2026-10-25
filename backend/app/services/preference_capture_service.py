from __future__ import annotations

from typing import Any

from app.schemas.chat import (
    ExtractedEntities,
)
from app.services.memory_service import (
    upsert_customer_memory,
)


def capture_explicit_preferences(
    customer_id: str,
    conversation_id: str,
    entities: ExtractedEntities,
) -> list[dict[str, Any]]:
    """
    Immediately persist preferences that the
    customer explicitly states.

    Example:
        "I prefer cotton."
        "My size is M."
        "I like blue."
        "I usually buy kurtas."

    These are stored with confidence=1.0 because
    the customer stated them directly.

    This allows Phase 13 recommendations to use
    the preference during the same active
    conversation instead of waiting until the
    Phase 12 conversation-finalization process.
    """

    candidates: list[
        tuple[
            str,
            str,
            str,
            Any,
        ]
    ] = []

    if entities.material:
        candidates.append(
            (
                "fabric_or_style_note",
                "preferred_material",
                "material",
                entities.material,
            )
        )

    if entities.size:
        candidates.append(
            (
                "other",
                "usual_size",
                "size",
                entities.size,
            )
        )

    if entities.color:
        candidates.append(
            (
                "fabric_or_style_note",
                "preferred_color",
                "color",
                entities.color,
            )
        )

    if entities.category:
        candidates.append(
            (
                "product_interest",
                "preferred_category",
                "category",
                entities.category,
            )
        )

    stored: list[
        dict[str, Any]
    ] = []

    for (
        memory_type,
        memory_key,
        label,
        value,
    ) in candidates:

        memory_id = (
            upsert_customer_memory(
                customer_id,
                memory_type=memory_type,
                memory_key=memory_key,
                memory_value=value,
                confidence=1.0,
                source_conversation_id=(
                    conversation_id
                ),
            )
        )

        stored.append(
            {
                "id": memory_id,
                "memory_key":
                    memory_key,
                "label": label,
                "value": value,
            }
        )

    return stored