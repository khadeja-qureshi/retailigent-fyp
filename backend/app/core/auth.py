from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
CUSTOMER_ROLE = "customer"
STAFF_ROLE = "staff"
ADMIN_ROLE = "admin"

from app.core.supabase_client import supabase_admin


bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """
    Verify the Supabase access token and return the authenticated user.
    """

    token = credentials.credentials

    try:
        response = supabase_admin.auth.get_user(token)

        if response.user is None:
            raise ValueError("User not found")

        return response.user

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )


def get_current_user_id(
    user=Depends(get_current_user),
) -> str:
    """
    Return the authenticated user's UUID.
    """

    return user.id


def get_current_user_role(
    user=Depends(get_current_user),
) -> str:
    """
    Return the authenticated user's application role.

    Roles are stored in the public.user_roles table.
    """

    response = (
        supabase_admin
        .table("user_roles")
        .select("role")
        .eq("user_id", user.id)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No application role assigned to this user",
        )

    return response.data[0]["role"]


def require_role(*allowed_roles: str) -> Callable:
    """
    Create a FastAPI dependency that requires one of the given roles.
    """

    def role_dependency(
        role: str = Depends(get_current_user_role),
    ):
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return role

    return role_dependency


require_customer = require_role(CUSTOMER_ROLE)
require_staff = require_role(STAFF_ROLE, ADMIN_ROLE)
require_admin = require_role(ADMIN_ROLE)