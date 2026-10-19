from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
)

from app.core.auth import (
    get_current_user_id,
    require_customer,
)
from app.services.memory_service import (
    delete_customer_memory,
    list_customer_memory,
)


router = APIRouter(
    prefix="/api/v1/memory",
    tags=["memory"],
)


@router.get("")
def get_memories(
    customer_id: str = Depends(
        get_current_user_id
    ),
    _customer_role: str = Depends(
        require_customer
    ),
) -> dict:
    """
    Show what Retailigent currently remembers
    about the authenticated customer.
    """

    memories = (
        list_customer_memory(
            customer_id
        )
    )

    return {
        "memories":
            memories,
        "count":
            len(memories),
    }


@router.delete(
    "/{memory_id}"
)
def delete_memory(
    memory_id: UUID,
    customer_id: str = Depends(
        get_current_user_id
    ),
    _customer_role: str = Depends(
        require_customer
    ),
) -> dict:
    """
    Delete one remembered fact owned by the
    authenticated customer.
    """

    return (
        delete_customer_memory(
            customer_id,
            str(memory_id),
        )
    )