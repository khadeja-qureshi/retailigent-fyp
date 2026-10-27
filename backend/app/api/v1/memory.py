from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
)
from pydantic import BaseModel

from app.core.auth import (
    get_current_user_id,
    require_customer,
)
from app.services.memory_service import (
    delete_customer_memory,
    list_customer_memory,
)
from app.services.recommendation_service import (
    get_personalization_preference,
    set_personalization_preference,
)


router = APIRouter(
    prefix="/api/v1/memory",
    tags=["memory"],
)


class PersonalizationPreferenceRequest(BaseModel):
    enabled: bool


@router.get("/personalization")
def get_personalization(
    customer_id: str = Depends(get_current_user_id),
    _customer_role: str = Depends(require_customer),
) -> dict:
    return get_personalization_preference(customer_id)


@router.patch("/personalization")
def update_personalization(
    payload: PersonalizationPreferenceRequest,
    customer_id: str = Depends(get_current_user_id),
    _customer_role: str = Depends(require_customer),
) -> dict:
    return set_personalization_preference(
        customer_id,
        payload.enabled,
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