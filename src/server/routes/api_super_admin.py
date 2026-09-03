import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database.models import (
    Tenant,
    User,
    Student,
    FaceEncoding,
    NodeDevice,
    AttendanceRecord,
    SystemBranding,
    AuditLog,
)
from src.database.session import get_db
from src.server.rbac_middleware import require_roles, get_current_user
from src.utils.auth_utils import hash_password
from src.utils.timezone import get_ist_now

logger = logging.getLogger("api_super_admin")
router = APIRouter(
    prefix="/api/v1/super-admin",
    tags=["Super Admin Control Plane"],
    dependencies=[Depends(require_roles(["SUPER_ADMIN"]))],
)

# Quota Defaults by Tier
TIER_LIMITS = {
    "FREE": {"max_faces": 50, "max_nodes": 2},
    "STANDARD": {"max_faces": 500, "max_nodes": 10},
    "ENTERPRISE": {"max_faces": 5000, "max_nodes": 50},
}


class CreateTenantRequest(BaseModel):
    name: str
    slug: str
    contact_email: Optional[str] = None
    subscription_plan: str = "STANDARD"  # FREE, STANDARD, ENTERPRISE
    max_face_encodings: Optional[int] = None
    max_nodes: Optional[int] = None
    admin_username: str
    admin_password: str
    admin_full_name: str


class UpdateTenantStatusRequest(BaseModel):
    status: str  # ACTIVE, SUSPENDED, EXPIRED


class UpdateTenantQuotasRequest(BaseModel):
    subscription_plan: Optional[str] = None
    max_face_encodings: Optional[int] = None
    max_nodes: Optional[int] = None


@router.get("/metrics")
def get_platform_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregates SaaS platform-wide KPIs across all tenants."""
    total_tenants = db.query(Tenant).count()
    active_tenants = db.query(Tenant).filter(Tenant.subscription_status == "ACTIVE").count()
    suspended_tenants = db.query(Tenant).filter(Tenant.subscription_status == "SUSPENDED").count()
    total_students = db.query(Student).count()
    total_face_vectors = db.query(FaceEncoding).count()
    total_nodes = db.query(NodeDevice).count()
    online_nodes = db.query(NodeDevice).filter(NodeDevice.is_online == True).count()
    total_attendance_logs = db.query(AttendanceRecord).count()
    today_ist = get_ist_now().date()
    today_attendances = db.query(AttendanceRecord).filter(
        func.date(AttendanceRecord.timestamp) == today_ist
    ).count()

    return {
        "status": "success",
        "metrics": {
            "total_tenants": total_tenants,
            "active_tenants": active_tenants,
            "suspended_tenants": suspended_tenants,
            "total_students": total_students,
            "total_face_vectors": total_face_vectors,
            "total_nodes": total_nodes,
            "online_nodes": online_nodes,
            "total_attendance_logs": total_attendance_logs,
            "today_attendances": today_attendances,
            "platform_status": "HEALTHY",
        }
    }


@router.get("/tenants")
def list_tenants(
    db: Session = Depends(get_db),
):
    """Lists all registered tenants with their subscription tier, quota utilization, and status."""
    tenants = db.query(Tenant).order_by(Tenant.id.asc()).all()
    tenant_list = []

    for t in tenants:
        face_count = db.query(FaceEncoding).filter(FaceEncoding.tenant_id == t.id).count()
        node_count = db.query(NodeDevice).filter(NodeDevice.tenant_id == t.id).count()
        student_count = db.query(Student).filter(Student.tenant_id == t.id).count()
        admin_user = db.query(User).filter(User.tenant_id == t.id, User.role == "TENANT_ADMIN").first()

        t_dict = t.to_dict()
        t_dict["enrolled_faces_count"] = face_count
        t_dict["active_nodes_count"] = node_count
        t_dict["students_count"] = student_count
        t_dict["face_quota_pct"] = round((face_count / (t.max_face_encodings or 500)) * 100, 1)
        t_dict["node_quota_pct"] = round((node_count / (t.max_nodes or 10)) * 100, 1)
        t_dict["admin_username"] = admin_user.username if admin_user else "N/A"
        t_dict["admin_email"] = admin_user.email if admin_user else "N/A"
        tenant_list.append(t_dict)

    return {
        "status": "success",
        "total": len(tenant_list),
        "tenants": tenant_list,
    }


@router.post("/tenants", status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: CreateTenantRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Creates a new SaaS Tenant organization with tier quotas and an initial Tenant Admin account.
    """
    slug_clean = payload.slug.strip().lower()
    name_clean = payload.name.strip()
    plan_clean = payload.subscription_plan.strip().upper()

    if plan_clean not in TIER_LIMITS:
        plan_clean = "STANDARD"

    # Validate slug uniqueness
    existing_tenant = db.query(Tenant).filter(Tenant.slug == slug_clean).first()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant slug '{slug_clean}' already exists. Please choose a unique identifier.",
        )

    tier_cfg = TIER_LIMITS[plan_clean]
    max_faces = payload.max_face_encodings or tier_cfg["max_faces"]
    max_nodes = payload.max_nodes or tier_cfg["max_nodes"]

    # 1. Create Tenant
    new_tenant = Tenant(
        slug=slug_clean,
        name=name_clean,
        contact_email=payload.contact_email.strip() if payload.contact_email else None,
        is_active=True,
        subscription_plan=plan_clean,
        subscription_status="ACTIVE",
        max_face_encodings=max_faces,
        max_nodes=max_nodes,
    )
    db.add(new_tenant)
    db.flush()

    # 2. Create System Branding for Tenant
    branding = SystemBranding(
        tenant_id=new_tenant.id,
        institution_name=name_clean,
        short_code=slug_clean.upper()[:10],
        tagline=f"Face Attendance System - {name_clean}",
        primary_accent_color="#6366f1",
        header_badge_text="Campus Hub",
        cooldown_minutes=60,
        enable_anti_spoofing=True,
    )
    db.add(branding)

    # 3. Create initial Tenant Admin User
    admin_user = User(
        tenant_id=new_tenant.id,
        username=payload.admin_username.strip().lower(),
        email=payload.contact_email.strip() if payload.contact_email else f"admin@{slug_clean}.edu",
        password_hash=hash_password(payload.admin_password),
        role="TENANT_ADMIN",
        full_name=payload.admin_full_name.strip(),
        is_active=True,
    )
    db.add(admin_user)

    # 4. Record Audit Log
    audit = AuditLog(
        tenant_id=new_tenant.id,
        user_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        action_type="TENANT_CREATED",
        target_type="TENANT",
        target_id=str(new_tenant.id),
        description=f"Super Admin created tenant '{name_clean}' ({plan_clean} Tier, max {max_faces} faces, max {max_nodes} nodes).",
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Tenant '{name_clean}' created successfully with {plan_clean} Tier.",
        "tenant": new_tenant.to_dict(),
        "admin_user": admin_user.to_dict(),
    }


@router.put("/tenants/{tenant_id}/status")
def update_tenant_status(
    tenant_id: int,
    payload: UpdateTenantStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Toggles a tenant's subscription status between ACTIVE, SUSPENDED, and EXPIRED.
    Suspended tenants immediately lock out edge nodes and portal access.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant #{tenant_id} not found.")

    new_status = payload.status.strip().upper()
    if new_status not in ["ACTIVE", "SUSPENDED", "EXPIRED"]:
        raise HTTPException(status_code=400, detail="Status must be ACTIVE, SUSPENDED, or EXPIRED.")

    old_status = tenant.subscription_status
    tenant.subscription_status = new_status
    tenant.is_active = (new_status == "ACTIVE")

    # Record Audit Log
    audit = AuditLog(
        tenant_id=tenant.id,
        user_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        action_type="TENANT_STATUS_CHANGED",
        target_type="TENANT",
        target_id=str(tenant.id),
        description=f"Tenant status changed from {old_status} to {new_status}.",
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Tenant #{tenant_id} status updated to {new_status}.",
        "tenant": tenant.to_dict(),
    }


@router.put("/tenants/{tenant_id}/quotas")
def update_tenant_quotas(
    tenant_id: int,
    payload: UpdateTenantQuotasRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Updates custom subscription tier and resource quotas (max faces, max nodes) for a tenant.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant #{tenant_id} not found.")

    if payload.subscription_plan:
        plan_upper = payload.subscription_plan.strip().upper()
        if plan_upper in TIER_LIMITS:
            tenant.subscription_plan = plan_upper
            # If explicit limits were not passed, apply default tier limits
            if payload.max_face_encodings is None:
                tenant.max_face_encodings = TIER_LIMITS[plan_upper]["max_faces"]
            if payload.max_nodes is None:
                tenant.max_nodes = TIER_LIMITS[plan_upper]["max_nodes"]

    if payload.max_face_encodings is not None:
        tenant.max_face_encodings = max(10, int(payload.max_face_encodings))

    if payload.max_nodes is not None:
        tenant.max_nodes = max(1, int(payload.max_nodes))

    audit = AuditLog(
        tenant_id=tenant.id,
        user_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        action_type="TENANT_QUOTA_UPDATED",
        target_type="TENANT",
        target_id=str(tenant.id),
        description=f"Quotas adjusted: Plan={tenant.subscription_plan}, MaxFaces={tenant.max_face_encodings}, MaxNodes={tenant.max_nodes}.",
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Tenant #{tenant_id} quotas updated successfully.",
        "tenant": tenant.to_dict(),
    }


@router.get("/audit-logs")
def get_global_audit_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Streams global platform audit trail across all administrative activities."""
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return {
        "status": "success",
        "total": len(logs),
        "logs": [l.to_dict() for l in logs],
    }
