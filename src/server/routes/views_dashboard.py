from datetime import date
from typing import List, Tuple, Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.database.models import Student, AttendanceRecord, NodeDevice, SystemBranding, Tenant, User, ClassModel, AcademicYear
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant
from src.server.rbac_middleware import get_current_user_optional

templates = Jinja2Templates(directory="src/server/templates")

router = APIRouter(include_in_schema=False)


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
        "primary_accent_color": "#6366f1",
        "header_badge_text": "Thin-Client Hub",
        "contact_email": None,
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


@router.get("/", response_class=HTMLResponse)
def page_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Main Admin Overview Dashboard."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)

    # If logged in as Teacher, redirect to their workspace
    if current_user and current_user.role == "TEACHER":
        return RedirectResponse(url="/teacher-portal")

    total_students = (
        db.query(Student)
        .filter(Student.tenant_id == current_tenant.id, Student.is_active == True)
        .count()
    )
    recent_logs = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.tenant_id == current_tenant.id)
        .order_by(AttendanceRecord.timestamp.desc())
        .limit(10)
        .all()
    )
    nodes = db.query(NodeDevice).filter(NodeDevice.tenant_id == current_tenant.id).all()
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "page_title": "Live Overview",
            "active_page": "dashboard",
            "total_students": total_students,
            "recent_logs": [r.to_dict() for r in recent_logs],
            "nodes": [n.to_dict() for n in nodes],
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
        },
    )


@router.get("/students", response_class=HTMLResponse)
def page_students(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Student Directory & Face Profile Management."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    students = (
        db.query(Student)
        .filter(Student.tenant_id == current_tenant.id)
        .order_by(Student.name.asc())
        .all()
    )
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    return templates.TemplateResponse(
        "students.html",
        {
            "request": request,
            "page_title": "Student Directory",
            "active_page": "students",
            "students": [s.to_dict() for s in students],
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
        },
    )


@router.get("/enroll", response_class=HTMLResponse)
def page_enroll(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Interactive Browser & Guided Face Enrollment."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    return templates.TemplateResponse(
        "enroll.html",
        {
            "request": request,
            "page_title": "Enroll New Student",
            "active_page": "enroll",
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
        },
    )


@router.get("/logs", response_class=HTMLResponse)
def page_logs(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Full Attendance Log Audit & Export."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    today_str = date.today().isoformat()
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    return templates.TemplateResponse(
        "logs.html",
        {
            "request": request,
            "page_title": "Attendance Logs",
            "active_page": "logs",
            "today_str": today_str,
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
        },
    )


@router.get("/nodes", response_class=HTMLResponse)
def page_nodes(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Connected Edge Nodes / Pi Zero Monitor."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    nodes = db.query(NodeDevice).filter(NodeDevice.tenant_id == current_tenant.id).all()
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    return templates.TemplateResponse(
        "nodes.html",
        {
            "request": request,
            "page_title": "Edge Nodes Monitor",
            "active_page": "nodes",
            "nodes": [n.to_dict() for n in nodes],
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
        },
    )


@router.get("/analytics", response_class=HTMLResponse)
def page_analytics(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Institutional Attendance Analytics & Defaulter Reports."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "page_title": "Attendance Analytics & Reports",
            "active_page": "analytics",
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
def page_settings(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Visual Theme Engine & System Preferences Settings."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "page_title": "System Settings & Theme",
            "active_page": "settings",
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
        },
    )


@router.get("/mobile-capture", response_class=HTMLResponse)
def page_mobile_capture(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Dedicated Mobile Browser Attendance Node."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    return templates.TemplateResponse(
        "mobile_capture.html",
        {
            "request": request,
            "page_title": "Mobile Capture Node",
            "active_page": "mobile",
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
        },
    )


@router.get("/face-demo", response_class=HTMLResponse)
def page_face_demo(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Dedicated Non-Logging Visual Recognition Demo Page."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    return templates.TemplateResponse(
        "face_demo.html",
        {
            "request": request,
            "page_title": "Visual Recognition Demo (Non-Logging)",
            "active_page": "demo",
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
        },
    )


@router.get("/login", response_class=HTMLResponse)
def page_login(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Modern Multi-Tier RBAC Login Interface."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "page_title": "Sign In - Enterprise SaaS Hub",
            "active_page": "login",
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
        },
    )


@router.get("/super-admin", response_class=HTMLResponse)
def page_super_admin(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Super Admin Control Plane & SaaS Tenant Management."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    return templates.TemplateResponse(
        "super_admin.html",
        {
            "request": request,
            "page_title": "Super Admin Control Plane",
            "active_page": "super-admin",
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
        },
    )


@router.get("/academic-management", response_class=HTMLResponse)
def page_academic_management(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Tenant Admin Academic Structure, Faculty Assignments & Promotion Engine."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)
    classes = db.query(ClassModel).filter(ClassModel.tenant_id == current_tenant.id).all()
    academic_years = db.query(AcademicYear).filter(AcademicYear.tenant_id == current_tenant.id).all()

    return templates.TemplateResponse(
        "academic_management.html",
        {
            "request": request,
            "page_title": "Academic Management & Progression",
            "active_page": "academic",
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "classes": [c.to_dict() for c in classes],
            "academic_years": [y.to_dict() for y in academic_years],
            "current_user": current_user.to_dict() if current_user else None,
        },
    )


@router.get("/teacher-portal", response_class=HTMLResponse)
def page_teacher_portal(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Tenant Teacher Classroom Attendance Workspace."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)
    classes = db.query(ClassModel).filter(ClassModel.tenant_id == current_tenant.id).all()

    return templates.TemplateResponse(
        "teacher_portal.html",
        {
            "request": request,
            "page_title": "Faculty Classroom Workspace",
            "active_page": "teacher-portal",
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "classes": [c.to_dict() for c in classes],
            "current_user": current_user.to_dict() if current_user else None,
        },
    )
