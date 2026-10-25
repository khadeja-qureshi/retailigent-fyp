from typing import Callable

from fastapi import (
    Depends,
    HTTPException,
    status,
)

from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.core.supabase_client import (
    supabase_admin,
)


CUSTOMER_ROLE = "customer"
STAFF_ROLE = "staff"
MANAGER_ROLE = "manager"
ADMIN_ROLE = "admin"


bearer_scheme = HTTPBearer()


ROLE_PRIORITY = {
    CUSTOMER_ROLE: 10,
    STAFF_ROLE: 20,
    MANAGER_ROLE: 30,
    ADMIN_ROLE: 40,
}


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        bearer_scheme
    ),
):
    """
    Verify the Supabase access token and return
    the authenticated Supabase user.
    """

    token = credentials.credentials

    try:
        response = (
            supabase_admin.auth.get_user(
                token
            )
        )

        if response.user is None:
            raise ValueError(
                "User not found"
            )

        return response.user

    except Exception:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Invalid or expired access token"
            ),
        )


def get_current_user_id(
    user=Depends(
        get_current_user
    ),
) -> str:
    return str(
        user.id
    )


def get_current_user_roles(
    user=Depends(
        get_current_user
    ),
) -> list[str]:
    """
    Return every role assigned to the user.

    A user may temporarily have more than one
    role row, so authorization must check the
    whole role set rather than one arbitrary row.
    """

    response = (
        supabase_admin
        .table(
            "user_roles"
        )
        .select(
            "role"
        )
        .eq(
            "user_id",
            user.id,
        )
        .execute()
    )

    roles = list(
        dict.fromkeys(
            str(
                row["role"]
            )
            for row in (
                response.data
                or []
            )
            if row.get(
                "role"
            )
        )
    )

    if not roles:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "No application role assigned "
                "to this user"
            ),
        )

    return roles


def get_current_user_role(
    roles: list[str] = Depends(
        get_current_user_roles
    ),
) -> str:
    """
    Return the user's highest-priority role.

    Priority:
        admin
        manager
        staff
        customer

    This prevents /me/role from returning an
    arbitrary role when multiple role rows exist.
    """

    supported_roles = [
        role
        for role in roles
        if role in ROLE_PRIORITY
    ]

    if not supported_roles:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "No supported application role "
                "assigned to this user"
            ),
        )

    return max(
        supported_roles,
        key=lambda role: (
            ROLE_PRIORITY[
                role
            ]
        ),
    )


def require_role(
    *allowed_roles: str,
) -> Callable:
    """
    Require at least one allowed application
    role.
    """

    def role_dependency(
        roles: list[str] = Depends(
            get_current_user_roles
        ),
    ) -> str:

        for role in allowed_roles:
            if role in roles:
                return role

        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Insufficient permissions"
            ),
        )

    return role_dependency


require_customer = require_role(
    CUSTOMER_ROLE
)

# For this FYP, staff/admin are operationally
# equivalent privileged users. Manager is also
# accepted because PostgreSQL is_staff() already
# considers it a staff role.
require_staff = require_role(
    STAFF_ROLE,
    MANAGER_ROLE,
    ADMIN_ROLE,
)

require_admin = require_role(
    ADMIN_ROLE,
    STAFF_ROLE,
    MANAGER_ROLE,
)