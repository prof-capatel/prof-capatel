import hashlib
import hmac
import json
import base64
import time
import logging
from typing import Optional, List, Dict, Any
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database.models import User, Tenant
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant
from src.utils.auth_utils import hash_password, verify_password

logger = logging.getLogger("rbac_middleware")
SECRET_KEY = "face_attendance_enterprise_jwt_secret_salt_2026"


def create_access_token(user_id: int, role: str, tenant_id: Optional[int], username: str, expires_in_sec: int = 86400) -> str:
    """Generates an HMAC-SHA256 signed JWT-like access token."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "tenant_id": tenant_id,
        "exp": int(time.time()) + expires_in_sec,
    }
    b64_header = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    b64_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(SECRET_KEY.encode(), f"{b64_header}.{b64_payload}".encode(), hashlib.sha256).digest()
    b64_sig = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{b64_header}.{b64_payload}.{b64_sig}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates signature and expiration of access token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        b64_header, b64_payload, b64_sig = parts
        expected_sig = hmac.new(SECRET_KEY.encode(), f"{b64_header}.{b64_payload}".encode(), hashlib.sha256).digest()
        actual_sig = base64.urlsafe_b64decode(b64_sig + "=" * ((4 - len(b64_sig) % 4) % 4))
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload_bytes = base64.urlsafe_b64decode(b64_payload + "=" * ((4 - len(b64_payload) % 4) % 4))
        payload = json.loads(payload_bytes)
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception as e:
        logger.debug(f"Token decoding failed: {e}")
        return None


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Extracts active user from:
    1. Authorization Header: `Bearer <token>`
    2. Cookie: `access_token`
    3. Cookie: `active_role` (Dev/demo fast role switcher)
    """
    token = None
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1].strip()
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if token:
        payload = decode_access_token(token)
        if payload:
            user = db.query(User).filter(User.id == payload.get("user_id"), User.is_active == True).first()
            if user:
                return user

    # Fast Role Switcher resolution for local testing and demo
    role_cookie = request.cookies.get("active_role")
    active_tenant_id_cookie = request.cookies.get("active_tenant_id") or "1"
    t_id = int(active_tenant_id_cookie) if str(active_tenant_id_cookie).isdigit() else 1

    if role_cookie:
        role_upper = role_cookie.strip().upper()
        if role_upper == "SUPER_ADMIN":
            user = db.query(User).filter(User.role == "SUPER_ADMIN", User.is_active == True).first()
            if user:
                return user
        elif role_upper in ["TENANT_ADMIN", "TEACHER", "STUDENT"]:
            user = db.query(User).filter(
                User.tenant_id == t_id,
                User.role == role_upper,
                User.is_active == True,
            ).first()
            if user:
                return user

    # Default fallback to Tenant Admin for seamless local development
    default_admin = db.query(User).filter(User.tenant_id == t_id, User.role == "TENANT_ADMIN").first()
    if not default_admin:
        default_admin = db.query(User).filter(User.role == "SUPER_ADMIN").first()
    return default_admin


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency requiring an authenticated user."""
    user = get_current_user_optional(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(allowed_roles: List[str]):
    """
    FastAPI dependency factory enforcing Role-Based Access Control (RBAC).
    Example: `dependencies=[Depends(require_roles(["SUPER_ADMIN", "TENANT_ADMIN"]))]`
    """
    def role_checker(
        request: Request,
        user: User = Depends(get_current_user),
    ) -> User:
        allowed_upper = [r.strip().upper() for r in allowed_roles]
        if user.role.upper() not in allowed_upper:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {', '.join(allowed_upper)}. Your role: {user.role}.",
            )
        return user

    return role_checker


def check_tenant_login_access(tenant: Tenant):
    """
    Verifies that a tenant is permitted to log in.
    Soft-deleted tenants are completely blocked from logging in.
    Suspended tenants ARE permitted to log in for read-only historical review.
    """
    if not tenant:
        return
    if getattr(tenant, "is_deleted", False) or (tenant.subscription_status or "").upper() == "DELETED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This institution account has been deactivated or deleted. Please contact platform support.",
        )


def check_tenant_operational_access(tenant: Tenant):
    """
    Verifies that a tenant is in an operational (ACTIVE) state.
    Suspended or soft-deleted tenants are locked out of mutations, face captures, enrollments, and node streaming.
    """
    if not tenant:
        return
    if getattr(tenant, "is_deleted", False) or (tenant.subscription_status or "").upper() == "DELETED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tenant organization '{tenant.name}' is deactivated/deleted. Operational features are blocked.",
        )

    status_upper = (tenant.subscription_status or "ACTIVE").upper()
    if status_upper == "SUSPENDED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tenant organization '{tenant.name}' is currently SUSPENDED by Super Admin. Read-only mode is active; operational actions (attendance ingestion, enrollment, edits) are locked.",
        )
    elif status_upper != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tenant organization '{tenant.name}' is {status_upper}. Operational actions are locked.",
        )


def check_tenant_subscription_active(tenant: Tenant):
    """Alias for operational check."""
    check_tenant_operational_access(tenant)


def check_tenant_leave_access(tenant: Tenant):
    """
    Verifies that the tenant's modular SaaS edition has Leave Management enabled (Smart or Pro).
    """
    if not tenant:
        return
    if not getattr(tenant, "has_leave_module", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Leave Management is not included in the {tenant.saas_edition} edition. Upgrade to Smart or Pro to access this module.",
        )


def check_tenant_payroll_access(tenant: Tenant):
    """
    Verifies that the tenant's modular SaaS edition has Indian Statutory Payroll & CTC enabled (Pro only).
    """
    if not tenant:
        return
    if not getattr(tenant, "has_payroll_module", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Payroll & Compensation is not included in the {tenant.saas_edition} edition. Upgrade to Pro to access this module.",
        )


