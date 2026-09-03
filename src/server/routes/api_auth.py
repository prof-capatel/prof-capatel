import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database.models import User, Tenant, AuditLog
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant
from src.server.rbac_middleware import (
    create_access_token,
    get_current_user,
    get_current_user_optional,
)
from src.utils.auth_utils import verify_password, hash_password
from src.utils.timezone import get_ist_now

logger = logging.getLogger("api_auth")
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & RBAC"])


class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_id: Optional[int] = None


class SwitchRoleRequest(BaseModel):
    role: str  # SUPER_ADMIN, TENANT_ADMIN, TEACHER, STUDENT
    tenant_id: Optional[int] = 1


@router.post("/login")
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Authenticates a user with username & password.
    Supports global SUPER_ADMIN as well as tenant-scoped TENANT_ADMIN, TEACHER, STUDENT.
    """
    username_clean = payload.username.strip().lower()
    
    # Check if Super Admin
    user = db.query(User).filter(User.username == username_clean, User.role == "SUPER_ADMIN", User.is_active == True).first()
    
    if not user:
        # Search by tenant-scoped username
        tenant_id = payload.tenant_id or 1
        user = db.query(User).filter(
            User.username == username_clean,
            User.tenant_id == tenant_id,
            User.is_active == True,
        ).first()

    if not user:
        # Fallback search across any active user if tenant_id wasn't specified
        user = db.query(User).filter(
            User.username == username_clean,
            User.is_active == True,
        ).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    user.last_login_at = get_ist_now()
    db.commit()

    token = create_access_token(
        user_id=user.id,
        role=user.role,
        tenant_id=user.tenant_id,
        username=user.username,
    )

    # Set secure cookies for browser navigation
    response.set_cookie("access_token", token, httponly=True, max_age=86400, path="/")
    response.set_cookie("active_role", user.role, httponly=False, max_age=86400, path="/")
    if user.tenant_id:
        response.set_cookie("active_tenant_id", str(user.tenant_id), httponly=False, max_age=86400, path="/")

    # Record Audit Log
    try:
        audit = AuditLog(
            tenant_id=user.tenant_id,
            user_id=user.id,
            actor_name=user.full_name,
            actor_role=user.role,
            action_type="USER_LOGIN",
            target_type="USER",
            target_id=str(user.id),
            description=f"User '{user.username}' logged in successfully.",
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)
        db.commit()
    except Exception as e:
        logger.warning(f"Audit log recording error: {e}")

    return {
        "status": "success",
        "message": f"Welcome back, {user.full_name}!",
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict(),
    }


@router.post("/logout")
def logout(response: Response):
    """Logs out user by clearing session cookies."""
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("active_role", path="/")
    return {"status": "success", "message": "Logged out successfully."}


@router.get("/me")
def get_current_user_profile(
    user: User = Depends(get_current_user),
):
    """Retrieves profile and permissions of current authenticated user."""
    return {
        "status": "success",
        "user": user.to_dict(),
    }


@router.post("/switch-role")
def switch_dev_role(
    payload: SwitchRoleRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Developer/Demo endpoint for instantly switching active session role
    between SUPER_ADMIN, TENANT_ADMIN, TEACHER, and STUDENT.
    """
    target_role = payload.role.strip().upper()
    tenant_id = payload.tenant_id or 1

    if target_role == "SUPER_ADMIN":
        user = db.query(User).filter(User.role == "SUPER_ADMIN", User.is_active == True).first()
    else:
        user = db.query(User).filter(
            User.tenant_id == tenant_id,
            User.role == target_role,
            User.is_active == True,
        ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"No active user found with role '{target_role}' in Tenant #{tenant_id}.",
        )

    token = create_access_token(
        user_id=user.id,
        role=user.role,
        tenant_id=user.tenant_id,
        username=user.username,
    )

    response.set_cookie("access_token", token, httponly=True, max_age=86400, path="/")
    response.set_cookie("active_role", user.role, httponly=False, max_age=86400, path="/")
    if user.tenant_id:
        response.set_cookie("active_tenant_id", str(user.tenant_id), httponly=False, max_age=86400, path="/")

    return {
        "status": "success",
        "message": f"Switched role to {user.role} ({user.full_name}).",
        "user": user.to_dict(),
        "access_token": token,
    }
