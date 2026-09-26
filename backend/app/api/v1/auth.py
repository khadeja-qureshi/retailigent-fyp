from fastapi import APIRouter, Depends

from app.core.auth import (
    get_current_user,
    get_current_user_id,
    get_current_user_role,
    require_admin,
    require_customer,
    require_staff,
)


router = APIRouter(
    prefix="/api/v1",
    tags=["Authentication"],
)


@router.get("/me")
def get_me(
    user=Depends(get_current_user),
):
    return {
        "id": user.id,
        "email": user.email,
    }


@router.get("/me/role")
def get_my_role(
    role=Depends(get_current_user_role),
):
    return {
        "role": role,
    }
@router.get("/me/id")
def get_my_id(
    user_id=Depends(get_current_user_id),
):
    return {
        "user_id": user_id,
    }


@router.get("/me/customer")
def customer_access(
    role=Depends(require_customer),
):
    return {
        "message": "Customer access granted",
        "role": role,
    }


@router.get("/me/staff")
def staff_access(
    role=Depends(require_staff),
):
    return {
        "message": "Staff access granted",
        "role": role,
    }


@router.get("/me/admin")
def admin_access(
    role=Depends(require_admin),
):
    return {
        "message": "Admin access granted",
        "role": role,
    }