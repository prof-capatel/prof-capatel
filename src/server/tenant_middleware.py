from typing import Optional
from fastapi import Request, Depends, HTTPException
from sqlalchemy.orm import Session

from src.config import DEFAULT_TENANT_ID, DEFAULT_TENANT_SLUG
from src.database.models import Tenant
from src.database.session import get_db


def resolve_tenant(db: Session, identifier: Optional[str]) -> Optional[Tenant]:
    """Resolves Tenant object by integer ID or string slug."""
    if not identifier:
        return None

    identifier_str = str(identifier).strip()
    if identifier_str.isdigit():
        tenant = db.query(Tenant).filter(Tenant.id == int(identifier_str), Tenant.is_active == True).first()
        if tenant:
            return tenant

    return db.query(Tenant).filter(Tenant.slug == identifier_str.lower(), Tenant.is_active == True).first()


def get_current_tenant(
    request: Request,
    db: Session = Depends(get_db),
) -> Tenant:
    """
    FastAPI dependency that extracts and validates the active tenant for the request.
    Resolution priority:
    1. Header `X-Tenant-ID` (ID or slug)
    2. Query parameter `tenant_id` or `tenant` or `tenant_slug`
    3. Cookie `active_tenant_id` or `active_tenant_slug`
    4. Default fallback to Tenant #1 ('default')
    """
    # 1. Header resolution
    header_val = request.headers.get("X-Tenant-ID") or request.headers.get("x-tenant-id")
    if header_val:
        tenant = resolve_tenant(db, header_val)
        if tenant:
            return tenant

    # 2. Query parameter resolution
    query_val = request.query_params.get("tenant_id") or request.query_params.get("tenant") or request.query_params.get("tenant_slug")
    if query_val:
        tenant = resolve_tenant(db, query_val)
        if tenant:
            return tenant

    # 3. Cookie resolution
    cookie_val = request.cookies.get("active_tenant_id") or request.cookies.get("active_tenant_slug")
    if cookie_val:
        tenant = resolve_tenant(db, cookie_val)
        if tenant:
            return tenant

    # 4. Fallback to default tenant
    default_tenant = db.query(Tenant).filter(Tenant.id == DEFAULT_TENANT_ID).first()
    if not default_tenant:
        # Fallback to any active tenant
        default_tenant = db.query(Tenant).filter(Tenant.is_active == True).first()

    if not default_tenant:
        raise HTTPException(status_code=500, detail="No active tenant found in system.")

    return default_tenant
