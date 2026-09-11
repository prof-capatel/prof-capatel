import logging
import uuid
import secrets
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
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
    SubscriptionPlan,
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

# Fallback limits if database is initializing
DEFAULT_TIER_LIMITS = {
    "FREE": {"max_faces": 50, "max_nodes": 2, "name": "Starter Free Tier"},
    "STANDARD": {"max_faces": 500, "max_nodes": 10, "name": "Standard Campus Tier"},
    "ENTERPRISE": {"max_faces": 5000, "max_nodes": 50, "name": "Enterprise Multi-Campus"},
}


# --- Request & Response Models ---
class SubscriptionPlanRequest(BaseModel):
    plan_code: str
    name: str
    max_face_encodings: int
    max_nodes: int
    price_monthly: Optional[float] = 0.0
    description: Optional[str] = ""
    is_active: Optional[bool] = True


class UpdateSubscriptionPlanRequest(BaseModel):
    name: Optional[str] = None
    max_face_encodings: Optional[int] = None
    max_nodes: Optional[int] = None
    price_monthly: Optional[float] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CreateTenantRequest(BaseModel):
    name: str
    slug: str
    tenant_type: Optional[str] = "educational"  # educational (school/college) vs corporate (company)
    contact_email: Optional[str] = None
    subscription_plan: str = "STANDARD"  # FREE, STANDARD, ENTERPRISE, or custom
    max_face_encodings: Optional[int] = None
    max_nodes: Optional[int] = None
    admin_username: str
    admin_password: str
    admin_full_name: str


class EditTenantDetailsRequest(BaseModel):
    name: Optional[str] = None
    tenant_type: Optional[str] = None  # educational vs corporate
    contact_email: Optional[str] = None
    subscription_plan: Optional[str] = None
    subscription_status: Optional[str] = None  # ACTIVE, SUSPENDED, EXPIRED, DELETED
    max_face_encodings: Optional[int] = None
    max_nodes: Optional[int] = None


class ResetAdminPasswordRequest(BaseModel):
    new_password: str
    admin_user_id: Optional[int] = None


class UpdateTenantStatusRequest(BaseModel):
    status: str  # ACTIVE, SUSPENDED, EXPIRED


class UpdateTenantQuotasRequest(BaseModel):
    subscription_plan: Optional[str] = None
    max_face_encodings: Optional[int] = None
    max_nodes: Optional[int] = None


# --- 1. Subscription Plans Management ---
@router.get("/plans")
def list_subscription_plans(db: Session = Depends(get_db)):
    """Lists all configured SaaS subscription tiers and quota limits."""
    plans = db.query(SubscriptionPlan).order_by(SubscriptionPlan.id.asc()).all()
    
    # If no plans in DB, ensure defaults
    if not plans:
        for code, cfg in DEFAULT_TIER_LIMITS.items():
            p = SubscriptionPlan(
                plan_code=code,
                name=cfg["name"],
                max_face_encodings=cfg["max_faces"],
                max_nodes=cfg["max_nodes"],
                price_monthly=0.0 if code == "FREE" else (49.0 if code == "STANDARD" else 199.0),
                is_active=True,
            )
            db.add(p)
        db.commit()
        plans = db.query(SubscriptionPlan).order_by(SubscriptionPlan.id.asc()).all()

    return {
        "status": "success",
        "total": len(plans),
        "plans": [p.to_dict() for p in plans],
    }


@router.post("/plans", status_code=status.HTTP_201_CREATED)
def create_subscription_plan(
    payload: SubscriptionPlanRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creates a new SaaS Subscription Plan with defined face vector and node quotas."""
    code_clean = payload.plan_code.strip().upper()
    existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == code_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subscription plan code '{code_clean}' already exists.",
        )

    plan = SubscriptionPlan(
        plan_code=code_clean,
        name=payload.name.strip(),
        max_face_encodings=max(10, int(payload.max_face_encodings)),
        max_nodes=max(1, int(payload.max_nodes)),
        price_monthly=max(0.0, float(payload.price_monthly or 0.0)),
        description=payload.description.strip() if payload.description else "",
        is_active=bool(payload.is_active if payload.is_active is not None else True),
    )
    db.add(plan)
    db.flush()

    audit = AuditLog(
        tenant_id=None,
        user_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        action_type="PLAN_CREATED",
        target_type="PLAN",
        target_id=str(plan.id),
        description=f"Created subscription plan '{plan.name}' ({code_clean}: {plan.max_face_encodings} faces, {plan.max_nodes} nodes).",
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Subscription plan '{plan.name}' created successfully.",
        "plan": plan.to_dict(),
    }


@router.put("/plans/{plan_id}")
def update_subscription_plan(
    plan_id: int,
    payload: UpdateSubscriptionPlanRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Modifies quotas, pricing, or details for an existing subscription plan."""
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"Subscription plan #{plan_id} not found.")

    if payload.name is not None:
        plan.name = payload.name.strip()
    if payload.max_face_encodings is not None:
        plan.max_face_encodings = max(10, int(payload.max_face_encodings))
    if payload.max_nodes is not None:
        plan.max_nodes = max(1, int(payload.max_nodes))
    if payload.price_monthly is not None:
        plan.price_monthly = max(0.0, float(payload.price_monthly))
    if payload.description is not None:
        plan.description = payload.description.strip()
    if payload.is_active is not None:
        plan.is_active = bool(payload.is_active)

    audit = AuditLog(
        tenant_id=None,
        user_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        action_type="PLAN_UPDATED",
        target_type="PLAN",
        target_id=str(plan.id),
        description=f"Updated plan '{plan.name}' ({plan.plan_code}): {plan.max_face_encodings} faces, {plan.max_nodes} nodes.",
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Subscription plan '{plan.name}' updated successfully.",
        "plan": plan.to_dict(),
    }


# --- 2. Platform Metrics & Tenant Lifecycle Management ---
@router.get("/metrics")
def get_platform_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregates SaaS platform-wide KPIs across all active and suspended tenants."""
    total_tenants = db.query(Tenant).count()
    active_tenants = db.query(Tenant).filter(Tenant.subscription_status == "ACTIVE", Tenant.is_deleted == False).count()
    suspended_tenants = db.query(Tenant).filter(Tenant.subscription_status == "SUSPENDED", Tenant.is_deleted == False).count()
    deleted_tenants = db.query(Tenant).filter(Tenant.is_deleted == True).count()

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
            "deleted_tenants": deleted_tenants,
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
    include_deleted: bool = Query(True, description="Whether to include soft-deleted tenants"),
    db: Session = Depends(get_db),
):
    """Lists all registered tenants with tier, quota utilization, soft delete status, and admin details."""
    query = db.query(Tenant)
    if not include_deleted:
        query = query.filter(Tenant.is_deleted == False)

    tenants = query.order_by(Tenant.is_deleted.asc(), Tenant.id.asc()).all()
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
        max_faces = t.max_face_encodings or 500
        max_nds = t.max_nodes or 10
        t_dict["face_quota_pct"] = round((face_count / max_faces) * 100, 1) if max_faces > 0 else 0
        t_dict["node_quota_pct"] = round((node_count / max_nds) * 100, 1) if max_nds > 0 else 0
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
    Creates a new SaaS Tenant organization with tier-derived quotas and initial Tenant Admin.
    Quota values are automatically derived from the selected Subscription Plan.
    """
    slug_clean = payload.slug.strip().lower()
    name_clean = payload.name.strip()
    plan_clean = payload.subscription_plan.strip().upper()

    # Validate slug uniqueness
    existing_tenant = db.query(Tenant).filter(Tenant.slug == slug_clean).first()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant slug '{slug_clean}' already exists. Please choose a unique identifier.",
        )

    # 1. Resolve quotas from SubscriptionPlan table or default fallback
    plan_record = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == plan_clean, SubscriptionPlan.is_active == True).first()
    if plan_record:
        max_faces = plan_record.max_face_encodings
        max_nodes = plan_record.max_nodes
    else:
        fallback = DEFAULT_TIER_LIMITS.get(plan_clean, DEFAULT_TIER_LIMITS["STANDARD"])
        max_faces = fallback["max_faces"]
        max_nodes = fallback["max_nodes"]

    # 2. Create Tenant with unique UUID and access tokens
    t_type = (payload.tenant_type or "educational").strip().lower()
    if t_type not in ["educational", "corporate"]:
        t_type = "educational"

    tenant_uuid = str(uuid.uuid4())
    admin_token = secrets.token_urlsafe(32)
    onboarding_token = secrets.token_urlsafe(32)
    attendance_slug = secrets.token_urlsafe(24)

    new_tenant = Tenant(
        uuid=tenant_uuid,
        slug=slug_clean,
        name=name_clean,
        tenant_type=t_type,
        contact_email=payload.contact_email.strip() if payload.contact_email else None,
        is_active=True,
        is_deleted=False,
        subscription_plan=plan_clean,
        subscription_status="ACTIVE",
        max_face_encodings=max_faces,
        max_nodes=max_nodes,
        admin_token=admin_token,
        onboarding_token=onboarding_token,
        attendance_slug=attendance_slug,
    )
    db.add(new_tenant)
    db.flush()

    # 3. Create System Branding for Tenant (Default: Warm Academic #c2410c, Anti-Spoofing OFF, Self-Attendance OFF)
    is_corporate = (t_type == "corporate")
    branding = SystemBranding(
        tenant_id=new_tenant.id,
        institution_name=name_clean,
        short_code=slug_clean.upper()[:10],
        tagline=f"Face Attendance System - {name_clean}",
        primary_accent_color="#c2410c",
        header_badge_text="Enterprise Hub" if is_corporate else "Campus Hub",
        cooldown_minutes=60,
        enable_anti_spoofing=False,
        liveness_mode="off",
        enable_self_attendance=False,
    )
    db.add(branding)

    # 4. Create initial Tenant Admin User
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

    # 5. Record Audit Log
    audit = AuditLog(
        tenant_id=new_tenant.id,
        user_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        action_type="TENANT_CREATED",
        target_type="TENANT",
        target_id=str(new_tenant.id),
        description=f"Super Admin created {t_type.upper()} tenant '{name_clean}' ({plan_clean} Tier: {max_faces} faces, {max_nodes} nodes).",
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Tenant '{name_clean}' ({t_type.capitalize()}) created successfully with {plan_clean} Tier quotas.",
        "tenant": new_tenant.to_dict(),
        "admin_user": admin_user.to_dict(),
        "links": {
            "portal_url": f"/portal/{new_tenant.slug}",
            "tenant_login_url": f"/portal/{new_tenant.slug}",
            "tokenized_portal_url": f"/portal/{tenant_uuid}/{admin_token}",
            "admin_login_url": f"/auth/token-login/{tenant_uuid}/{admin_token}",
            "onboarding_url": f"/onboard/{tenant_uuid}/{onboarding_token}",
            "checkin_url": f"/check-in/{tenant_uuid}/{attendance_slug}",
        },
    }


@router.put("/tenants/{tenant_id}")
def edit_tenant_details(
    tenant_id: int,
    payload: EditTenantDetailsRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Edits comprehensive tenant parameters: name, tenant_type, contact email, plan, status, and quotas.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant #{tenant_id} not found.")

    changes = []

    if payload.name is not None and payload.name.strip():
        old_name = tenant.name
        tenant.name = payload.name.strip()
        changes.append(f"Name: '{old_name}' -> '{tenant.name}'")

    if payload.tenant_type is not None and payload.tenant_type.strip():
        t_type_clean = payload.tenant_type.strip().lower()
        if t_type_clean in ["educational", "corporate"] and t_type_clean != tenant.tenant_type:
            old_type = tenant.tenant_type or "educational"
            tenant.tenant_type = t_type_clean
            changes.append(f"Type: {old_type} -> {t_type_clean}")

    if payload.contact_email is not None:
        tenant.contact_email = payload.contact_email.strip() if payload.contact_email.strip() else None
        changes.append(f"Email: {tenant.contact_email}")

    if payload.subscription_plan is not None:
        plan_clean = payload.subscription_plan.strip().upper()
        if plan_clean != tenant.subscription_plan:
            old_plan = tenant.subscription_plan
            tenant.subscription_plan = plan_clean
            changes.append(f"Plan: {old_plan} -> {plan_clean}")

    if payload.subscription_status is not None:
        new_status = payload.subscription_status.strip().upper()
        if new_status in ["ACTIVE", "SUSPENDED", "EXPIRED", "DELETED"]:
            if new_status != tenant.subscription_status:
                old_status = tenant.subscription_status
                tenant.subscription_status = new_status
                tenant.is_active = (new_status == "ACTIVE")
                if new_status == "DELETED":
                    tenant.is_deleted = True
                    tenant.deleted_at = get_ist_now()
                else:
                    tenant.is_deleted = False
                    tenant.deleted_at = None
                changes.append(f"Status: {old_status} -> {new_status}")

    if payload.max_face_encodings is not None:
        tenant.max_face_encodings = max(10, int(payload.max_face_encodings))
        changes.append(f"MaxFaces: {tenant.max_face_encodings}")

    if payload.max_nodes is not None:
        tenant.max_nodes = max(1, int(payload.max_nodes))
        changes.append(f"MaxNodes: {tenant.max_nodes}")

    audit = AuditLog(
        tenant_id=tenant.id,
        user_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        action_type="TENANT_DETAILS_UPDATED",
        target_type="TENANT",
        target_id=str(tenant.id),
        description=f"Updated Tenant #{tenant.id}: " + (", ".join(changes) if changes else "No fields changed."),
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Tenant #{tenant_id} ('{tenant.name}') details updated successfully.",
        "tenant": tenant.to_dict(),
    }


@router.post("/tenants/{tenant_id}/admin-password")
def reset_tenant_admin_password(
    tenant_id: int,
    payload: ResetAdminPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Super Admin Password Reset / Set:
    Manually resets or sets a new password for the Tenant Admin user of any tenant.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant #{tenant_id} not found.")

    new_pass = payload.new_password.strip()
    if not new_pass or len(new_pass) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    # Find target tenant admin user
    admin_query = db.query(User).filter(User.tenant_id == tenant_id, User.role == "TENANT_ADMIN")
    if payload.admin_user_id:
        admin_user = admin_query.filter(User.id == payload.admin_user_id).first()
    else:
        admin_user = admin_query.first()

    if not admin_user:
        # Fallback: check any user belonging to tenant
        admin_user = db.query(User).filter(User.tenant_id == tenant_id).first()

    if not admin_user:
        raise HTTPException(status_code=404, detail=f"No administrative user found for Tenant '{tenant.name}'.")

    admin_user.password_hash = hash_password(new_pass)

    audit = AuditLog(
        tenant_id=tenant.id,
        user_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        action_type="TENANT_ADMIN_PASSWORD_RESET",
        target_type="USER",
        target_id=str(admin_user.id),
        description=f"Super Admin manually reset password for Tenant Admin '{admin_user.username}' (Tenant: '{tenant.name}').",
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Password for Tenant Admin '{admin_user.username}' ({admin_user.full_name}) has been reset successfully.",
        "admin_username": admin_user.username,
        "tenant_id": tenant.id,
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
    Suspended tenants immediately lock out operational features while maintaining read-only access.
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
    if tenant.is_deleted:
        tenant.is_deleted = False
        tenant.deleted_at = None

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
        plan_rec = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == plan_upper).first()
        tenant.subscription_plan = plan_upper
        if plan_rec:
            if payload.max_face_encodings is None:
                tenant.max_face_encodings = plan_rec.max_face_encodings
            if payload.max_nodes is None:
                tenant.max_nodes = plan_rec.max_nodes

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


@router.delete("/tenants/{tenant_id}")
def soft_delete_tenant(
    tenant_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Soft-deletes a tenant without dropping database tables or historical data.
    Sets is_deleted=True, subscription_status='DELETED', and records deletion timestamp.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant #{tenant_id} not found.")

    if tenant.is_deleted:
        raise HTTPException(status_code=400, detail=f"Tenant #{tenant_id} is already soft-deleted.")

    tenant.is_deleted = True
    tenant.deleted_at = get_ist_now()
    tenant.subscription_status = "DELETED"
    tenant.is_active = False

    audit = AuditLog(
        tenant_id=tenant.id,
        user_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        action_type="TENANT_SOFT_DELETED",
        target_type="TENANT",
        target_id=str(tenant.id),
        description=f"Tenant '{tenant.name}' (#{tenant.id}) was soft-deleted by Super Admin.",
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Tenant '{tenant.name}' (#{tenant.id}) has been soft-deleted.",
        "tenant": tenant.to_dict(),
    }


@router.post("/tenants/{tenant_id}/restore")
def restore_tenant(
    tenant_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Restores a previously soft-deleted tenant back to ACTIVE state.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant #{tenant_id} not found.")

    if not tenant.is_deleted:
        raise HTTPException(status_code=400, detail=f"Tenant #{tenant_id} is not deleted.")

    tenant.is_deleted = False
    tenant.deleted_at = None
    tenant.subscription_status = "ACTIVE"
    tenant.is_active = True

    audit = AuditLog(
        tenant_id=tenant.id,
        user_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        action_type="TENANT_RESTORED",
        target_type="TENANT",
        target_id=str(tenant.id),
        description=f"Tenant '{tenant.name}' (#{tenant.id}) was restored to ACTIVE by Super Admin.",
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Tenant '{tenant.name}' (#{tenant.id}) has been successfully restored to ACTIVE.",
        "tenant": tenant.to_dict(),
    }


# --- 3. Super Admin Tenant-Scoped Student Directory ---
@router.get("/tenants/{tenant_id}/students")
def get_tenant_students(
    tenant_id: int,
    db: Session = Depends(get_db),
):
    """Fetches student directory partitioned strictly to the specified tenant."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant #{tenant_id} not found.")

    students = db.query(Student).filter(Student.tenant_id == tenant_id).order_by(Student.name.asc()).all()
    return {
        "status": "success",
        "tenant_id": tenant.id,
        "tenant_name": tenant.name,
        "total": len(students),
        "students": [s.to_dict() for s in students],
    }


@router.get("/students")
def get_scoped_students(
    tenant_id: int = Query(..., description="Mandatory tenant ID filter for student directory"),
    db: Session = Depends(get_db),
):
    """Enforces mandatory tenant selection for Super Admin viewing student directories."""
    return get_tenant_students(tenant_id=tenant_id, db=db)


# --- 4. Global Administrative Audit Trail ---
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


# --- 5. Tokenized Links & Access Keys Management ---
@router.get("/tenants/{tenant_id}/links")
def get_tenant_access_links(
    tenant_id: int,
    db: Session = Depends(get_db),
):
    """Retrieves tokenized URLs for Passwordless Admin Login, Employee Onboarding, and Check-In."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant #{tenant_id} not found.")

    # Ensure tokens exist
    updated = False
    if not tenant.uuid:
        tenant.uuid = str(uuid.uuid4())
        updated = True
    if not tenant.admin_token:
        tenant.admin_token = secrets.token_urlsafe(32)
        updated = True
    if not tenant.onboarding_token:
        tenant.onboarding_token = secrets.token_urlsafe(32)
        updated = True
    if not tenant.attendance_slug:
        tenant.attendance_slug = secrets.token_urlsafe(24)
        updated = True
    if updated:
        db.commit()
        db.refresh(tenant)

    t_uuid = tenant.uuid or tenant.slug
    return {
        "status": "success",
        "tenant_id": tenant.id,
        "tenant_name": tenant.name,
        "tenant_type": tenant.tenant_type,
        "uuid": tenant.uuid,
        "links": {
            "portal_url": f"/portal/{tenant.slug}",
            "tenant_login_url": f"/portal/{tenant.slug}",
            "tokenized_portal_url": f"/portal/{t_uuid}/{tenant.admin_token}",
            "admin_login_url": f"/auth/token-login/{t_uuid}/{tenant.admin_token}",
            "onboarding_url": f"/onboard/{t_uuid}/{tenant.onboarding_token}",
            "checkin_url": f"/check-in/{t_uuid}/{tenant.attendance_slug}",
        },
        "tokens": {
            "admin_token": tenant.admin_token,
            "onboarding_token": tenant.onboarding_token,
            "attendance_slug": tenant.attendance_slug,
        }
    }


@router.post("/tenants/{tenant_id}/regenerate-tokens")
def regenerate_tenant_tokens(
    tenant_id: int,
    request: Request,
    rotate_admin: bool = Query(True, description="Rotate admin login token"),
    rotate_onboarding: bool = Query(True, description="Rotate employee onboarding token"),
    rotate_checkin: bool = Query(False, description="Rotate attendance checkin slug"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Regenerates/rotates secure token keys for a tenant."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant #{tenant_id} not found.")

    rotated_items = []
    if rotate_admin:
        tenant.admin_token = secrets.token_urlsafe(32)
        rotated_items.append("Admin Login Token")
    if rotate_onboarding:
        tenant.onboarding_token = secrets.token_urlsafe(32)
        rotated_items.append("Onboarding Token")
    if rotate_checkin:
        tenant.attendance_slug = secrets.token_urlsafe(24)
        rotated_items.append("Attendance Check-In Slug")

    if not tenant.uuid:
        tenant.uuid = str(uuid.uuid4())

    audit = AuditLog(
        tenant_id=tenant.id,
        user_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        action_type="TOKENS_ROTATED",
        target_type="TENANT",
        target_id=str(tenant.id),
        description=f"Rotated tokens ({', '.join(rotated_items)}) for tenant '{tenant.name}'.",
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()
    db.refresh(tenant)

    t_uuid = tenant.uuid or tenant.slug
    return {
        "status": "success",
        "message": f"Successfully regenerated {', '.join(rotated_items)} for '{tenant.name}'.",
        "tenant_id": tenant.id,
        "links": {
            "portal_url": f"/portal/{tenant.slug}",
            "tenant_login_url": f"/portal/{tenant.slug}",
            "tokenized_portal_url": f"/portal/{t_uuid}/{tenant.admin_token}",
            "admin_login_url": f"/auth/token-login/{t_uuid}/{tenant.admin_token}",
            "onboarding_url": f"/onboard/{t_uuid}/{tenant.onboarding_token}",
            "checkin_url": f"/check-in/{t_uuid}/{tenant.attendance_slug}",
        },
    }
