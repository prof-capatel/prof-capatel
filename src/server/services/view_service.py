import logging
from typing import List, Tuple, Optional, Any, Dict
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.database.models import (
    Tenant,
    User,
    Student,
    SystemBranding,
    Department,
    ClassModel,
    Division,
    AcademicYear,
)
from src.server.rbac_middleware import get_current_user_optional
from src.server.routes.api_employee_portal import decode_employee_token, EMP_COOKIE_NAME

logger = logging.getLogger("view_service")

# Global Jinja2 templates loader
templates = Jinja2Templates(directory="src/server/templates")


def render_template(request: Request, name: str, context: Dict[str, Any], status_code: int = 200) -> HTMLResponse:
    """
    Standardized template response renderer supporting modern Starlette signature:
    TemplateResponse(request=request, name=name, context=context)
    Ensures context['request'] is populated.
    """
    ctx = dict(context)
    ctx["request"] = request
    try:
        # Starlette >= 0.28+ keyword/signature support
        return templates.TemplateResponse(request=request, name=name, context=ctx, status_code=status_code)
    except TypeError:
        # Fallback for older Starlette versions
        return templates.TemplateResponse(name, ctx, status_code=status_code)


def get_branding_dict(db: Session, tenant_id: int) -> dict:
    """Helper to load institutional branding for template injection scoped to tenant."""
    branding = db.query(SystemBranding).filter(SystemBranding.tenant_id == tenant_id).first()
    if branding:
        return branding.to_dict()
    return {
        "id": 1,
        "tenant_id": tenant_id,
        "institution_name": "FaceAttendance Campus",
        "short_code": "FA-HUB",
        "tagline": "Raspberry Pi Zero Edge Nodes & Central Face Recognition",
        "logo_filename": None,
        "logo_url": None,
        "primary_accent_color": "#c2410c",
        "header_badge_text": "Thin-Client Hub",
        "contact_email": None,
        "cooldown_minutes": 60,
        "enable_anti_spoofing": False,
        "liveness_mode": "off",
        "enable_self_attendance": False,
    }


def get_all_active_tenants(db: Session) -> List[dict]:
    """Helper to load all active tenants for Super Admin global switcher."""
    tenants = db.query(Tenant).filter(Tenant.is_active == True).order_by(Tenant.name.asc()).all()
    return [t.to_dict() for t in tenants]


def resolve_scoped_tenant_and_user(request: Request, db: Session, fallback_tenant: Tenant) -> Tuple[Tenant, Optional[User]]:
    """
    Resolves the authenticated user and strictly locks the tenant:
    - If user is TEACHER, TENANT_ADMIN, or STUDENT: tenant is fixed to user.tenant_id.
    - If user is SUPER_ADMIN: tenant can be switched globally across all institutions.
    """
    current_user = get_current_user_optional(request, db)
    if current_user and current_user.role != "SUPER_ADMIN" and current_user.tenant_id:
        user_tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
        if user_tenant:
            return user_tenant, current_user
    return fallback_tenant, current_user


def get_current_employee_session(request: Request, db: Session) -> Optional[Student]:
    """Helper to decode employee session token if present."""
    token = request.cookies.get(EMP_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
    if token:
        payload = decode_employee_token(token)
        if payload and payload.get("student_id"):
            return db.query(Student).filter(
                Student.id == payload.get("student_id"),
                Student.is_active == True,
            ).first()
    return None


def check_employee_portal_redirect(request: Request, db: Session) -> Optional[RedirectResponse]:
    """
    If the current visitor is an employee logged into their self-service portal
    (possesses emp_session_token) but lacks an admin access_token, redirect them
    away from privileged tenant-admin routes to their restricted employee portal.
    """
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    has_admin_token = bool(
        (auth_header and auth_header.startswith("Bearer ")) or 
        ("access_token" in request.cookies and request.cookies.get("access_token"))
    )
    if not has_admin_token:
        emp = get_current_employee_session(request, db)
        if emp and emp.tenant:
            return RedirectResponse(url=f"/employee/{emp.tenant.slug}/dashboard", status_code=303)
    return None


def get_tenant_roles_list(db: Session, tenant: Tenant) -> List[dict]:
    """Helper to retrieve tenant-scoped allowed roles, supporting dynamic custom roles defined by tenant admin."""
    tenant_type = (tenant.tenant_type or "educational").lower() if tenant else "educational"
    is_corp = tenant_type in ["corporate", "company", "enterprise"]

    if is_corp:
        base_roles = [
            {"value": "employee", "label": "Employee / Staff Member", "role_key": "employee", "display_name": "Employee / Staff Member"},
            {"value": "manager", "label": "Manager / Team Lead", "role_key": "manager", "display_name": "Manager / Team Lead"},
            {"value": "admin_staff", "label": "Administrative Staff", "role_key": "admin_staff", "display_name": "Administrative Staff"},
            {"value": "contractor", "label": "Contractor / External", "role_key": "contractor", "display_name": "Contractor / External"},
            {"value": "intern", "label": "Intern / Trainee", "role_key": "intern", "display_name": "Intern / Trainee"},
        ]
    else:
        base_roles = [
            {"value": "student", "label": "Student", "role_key": "student", "display_name": "Student"},
            {"value": "teacher", "label": "Teacher / Faculty", "role_key": "teacher", "display_name": "Teacher / Faculty"},
            {"value": "admin_staff", "label": "Administrative Staff", "role_key": "admin_staff", "display_name": "Administrative Staff"},
            {"value": "other", "label": "Other Institutional Member", "role_key": "other", "display_name": "Other Institutional Member"},
        ]

    # Query distinct user roles stored for this tenant (supports custom tenant-defined roles)
    try:
        from src.database.models import Student
        if tenant and tenant.id:
            db_roles = [
                r[0] for r in db.query(Student.user_role)
                .filter(Student.tenant_id == tenant.id, Student.user_role.isnot(None))
                .distinct().all()
            ]
            known_values = {r["value"] for r in base_roles}
            for dbr in db_roles:
                if dbr and dbr not in known_values:
                    display_label = dbr.replace("_", " ").title()
                    base_roles.append({
                        "value": dbr,
                        "label": display_label,
                        "role_key": dbr,
                        "display_name": display_label,
                    })
    except Exception:
        pass

    return base_roles

