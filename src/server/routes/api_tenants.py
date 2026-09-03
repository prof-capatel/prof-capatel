from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database.models import Tenant, SystemBranding, Student, AttendanceRecord, NodeDevice
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant

router = APIRouter(prefix="/api/v1/tenants", tags=["Tenant & SaaS Management"])


class TenantCreate(BaseModel):
    name: str
    slug: str
    contact_email: Optional[str] = None
    tagline: Optional[str] = None
    short_code: Optional[str] = None
    primary_accent_color: Optional[str] = "#6366f1"


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    contact_email: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("")
def list_tenants(db: Session = Depends(get_db)):
    """Lists all active organizations / tenants for the SaaS switcher."""
    tenants = db.query(Tenant).filter(Tenant.is_active == True).order_by(Tenant.name.asc()).all()
    results = []
    for t in tenants:
        branding = t.branding
        results.append({
            "id": t.id,
            "slug": t.slug,
            "name": t.name,
            "contact_email": t.contact_email,
            "is_active": t.is_active,
            "short_code": branding.short_code if branding else t.slug.upper(),
            "logo_url": branding.to_dict().get("logo_url") if branding else None,
            "primary_accent_color": branding.primary_accent_color if branding else "#6366f1",
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })
    return {"status": "success", "tenants": results}


@router.get("/current")
def get_active_tenant(current_tenant: Tenant = Depends(get_current_tenant)):
    """Returns the currently active tenant resolved by headers/cookies."""
    branding = current_tenant.branding
    return {
        "status": "success",
        "tenant": current_tenant.to_dict(),
        "branding": branding.to_dict() if branding else None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    """Registers a new institution / organization in the multi-tenant SaaS system."""
    clean_slug = payload.slug.strip().lower().replace(" ", "-")
    if not clean_slug:
        raise HTTPException(status_code=400, detail="Slug cannot be empty.")
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Tenant name cannot be empty.")

    existing = db.query(Tenant).filter(Tenant.slug == clean_slug).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Tenant with slug '{clean_slug}' already exists.")

    tenant = Tenant(
        slug=clean_slug,
        name=payload.name.strip(),
        contact_email=payload.contact_email.strip() if payload.contact_email else None,
        is_active=True,
    )
    db.add(tenant)
    db.flush()

    short_code = payload.short_code.strip().upper() if payload.short_code else clean_slug[:6].upper()
    branding = SystemBranding(
        tenant_id=tenant.id,
        institution_name=tenant.name,
        short_code=short_code,
        tagline=payload.tagline.strip() if payload.tagline else f"Smart Edge Attendance Hub for {tenant.name}",
        primary_accent_color=payload.primary_accent_color or "#6366f1",
        header_badge_text="Campus Hub",
        contact_email=tenant.contact_email,
    )
    db.add(branding)
    db.commit()
    db.refresh(tenant)

    return {
        "status": "success",
        "message": f"Tenant '{tenant.name}' registered successfully.",
        "tenant": tenant.to_dict(),
        "branding": branding.to_dict(),
    }


@router.get("/{tenant_id}")
def get_tenant_details(tenant_id: int, db: Session = Depends(get_db)):
    """Fetches details, user count, and node count for a specific tenant."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    students_count = db.query(Student).filter(Student.tenant_id == tenant_id, Student.is_active == True).count()
    nodes_count = db.query(NodeDevice).filter(NodeDevice.tenant_id == tenant_id).count()
    logs_count = db.query(AttendanceRecord).filter(AttendanceRecord.tenant_id == tenant_id).count()

    return {
        "status": "success",
        "tenant": tenant.to_dict(),
        "branding": tenant.branding.to_dict() if tenant.branding else None,
        "stats": {
            "students_count": students_count,
            "nodes_count": nodes_count,
            "logs_count": logs_count,
        }
    }
