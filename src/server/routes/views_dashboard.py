from datetime import date
from typing import List, Tuple, Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database.models import (
    Student,
    AttendanceRecord,
    NodeDevice,
    SystemBranding,
    Tenant,
    User,
    Department,
    ClassModel,
    Division,
    AcademicYear,
    StudentBatchUpload,
    AuditLog,
    LeaveType,
    LeaveRequest,
    LeaveBalance,
)
from src.database.session import get_db, seed_default_leave_types
from src.server.tenant_middleware import get_current_tenant, resolve_tenant
from src.server.rbac_middleware import get_current_user_optional, create_access_token, check_tenant_login_access
from src.server.routes.api_employee_portal import decode_employee_token, EMP_COOKIE_NAME
from src.utils.timezone import get_ist_now

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

    tenant_type = (current_tenant.tenant_type or "educational").lower()
    is_corporate = tenant_type in ["corporate", "company", "enterprise"]
    member_label = "Employees" if is_corporate else "Students"

    if is_corporate:
        total_students = (
            db.query(Student)
            .filter(Student.tenant_id == current_tenant.id, Student.is_active == True, Student.user_role != "student")
            .count()
        )
        if total_students == 0:
            total_students = (
                db.query(Student)
                .filter(Student.tenant_id == current_tenant.id, Student.is_active == True)
                .count()
            )
    else:
        total_students = (
            db.query(Student)
            .filter(Student.tenant_id == current_tenant.id, Student.is_active == True, Student.user_role == "student")
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
            "is_corporate": is_corporate,
            "member_label": member_label,
            "recent_logs": [r.to_dict() for r in recent_logs],
            "nodes": [n.to_dict() for n in nodes],
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
        },
    )


@router.get("/students", response_class=HTMLResponse)
@router.get("/employees", response_class=HTMLResponse)
def page_students(
    request: Request,
    tenant_id: Optional[int] = None,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Student & Employee Directory & Profile Management."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    is_super_admin = bool(current_user and current_user.role == "SUPER_ADMIN")

    selected_tenant = current_tenant
    if is_super_admin and tenant_id:
        custom_t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if custom_t:
            selected_tenant = custom_t

    is_corporate = bool(selected_tenant.tenant_type == "corporate")
    students = (
        db.query(Student)
        .filter(Student.tenant_id == selected_tenant.id)
        .order_by(Student.name.asc())
        .all()
    )
    departments = db.query(Department).filter(Department.tenant_id == selected_tenant.id).order_by(Department.name.asc()).all()
    classes = db.query(ClassModel).filter(ClassModel.tenant_id == selected_tenant.id).order_by(ClassModel.name.asc()).all()
    divisions = db.query(Division).filter(Division.tenant_id == selected_tenant.id).order_by(Division.name.asc()).all()
    branding = get_branding_dict(db, selected_tenant.id)
    all_tenants = get_all_active_tenants(db)

    active_page_tag = "employees" if (is_corporate or request.url.path.startswith("/employees")) else "students"
    page_title = "Employee Directory" if is_corporate else "Student Directory"

    return templates.TemplateResponse(
        "students.html",
        {
            "request": request,
            "page_title": page_title,
            "active_page": active_page_tag,
            "students": [s.to_dict() for s in students],
            "departments": [d.to_dict() for d in departments],
            "classes": [c.to_dict() for c in classes],
            "divisions": [dv.to_dict() for dv in divisions],
            "branding": branding,
            "current_tenant": selected_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
            "is_super_admin": is_super_admin,
            "selected_tenant_id": selected_tenant.id,
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
    departments = db.query(Department).filter(Department.tenant_id == current_tenant.id).order_by(Department.name.asc()).all()
    classes = db.query(ClassModel).filter(ClassModel.tenant_id == current_tenant.id).order_by(ClassModel.name.asc()).all()
    divisions = db.query(Division).filter(Division.tenant_id == current_tenant.id).order_by(Division.name.asc()).all()
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    return templates.TemplateResponse(
        "enroll.html",
        {
            "request": request,
            "page_title": "Enroll New Student",
            "active_page": "enroll",
            "departments": [d.to_dict() for d in departments],
            "classes": [c.to_dict() for c in classes],
            "divisions": [dv.to_dict() for dv in divisions],
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

    # 1. Fetch tenant-scoped departments
    dept_objs = (
        db.query(Department)
        .filter(Department.tenant_id == current_tenant.id)
        .order_by(Department.name.asc())
        .all()
    )
    dept_names = [d.name for d in dept_objs if d.name]

    # Also grab any distinct student departments in this tenant
    student_depts = [
        s[0] for s in db.query(Student.department)
        .filter(Student.tenant_id == current_tenant.id, Student.department.isnot(None), Student.department != "")
        .distinct()
        .all()
        if s[0]
    ]
    seen_depts = set(dept_names)
    for s_dept in student_depts:
        if s_dept not in seen_depts:
            dept_names.append(s_dept)
            seen_depts.add(s_dept)

    # 2. Determine tenant type & base roles
    tenant_type = (current_tenant.tenant_type or "education").lower()
    is_corporate = tenant_type in ["corporate", "company", "enterprise"]

    if is_corporate:
        base_roles = ["employee", "manager", "admin_staff", "contractor", "intern", "other"]
    else:
        base_roles = ["student", "teacher", "admin_staff", "other"]

    # 3. Query distinct user roles stored for this tenant (supports custom tenant roles)
    db_roles = [
        r[0] for r in db.query(Student.user_role)
        .filter(Student.tenant_id == current_tenant.id, Student.user_role.isnot(None), Student.user_role != "")
        .distinct()
        .all()
        if r[0]
    ]

    seen_roles = set(base_roles)
    combined_roles = list(base_roles)
    for role in db_roles:
        if role not in seen_roles:
            combined_roles.append(role)
            seen_roles.add(role)

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
            "departments": dept_names,
            "tenant_roles": combined_roles,
            "is_corporate": is_corporate,
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
    """Institutional / Corporate Attendance Analytics & Defaulter Reports."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    tenant_type = (current_tenant.tenant_type or "educational").lower()
    is_corporate = tenant_type in ["corporate", "company", "enterprise"]
    member_label = "Employees" if is_corporate else "Students"

    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "page_title": "Workforce Analytics & Reports" if is_corporate else "Attendance Analytics & Reports",
            "active_page": "analytics",
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
            "is_corporate": is_corporate,
            "member_label": member_label,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
def page_settings(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Visual Theme Engine & System Preferences Settings with Consolidated Departments."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)
    
    tenant_type = (current_tenant.tenant_type or "educational").lower()
    is_corporate = tenant_type in ["corporate", "company", "enterprise"]

    # Fetch departments and calculate employee/member counts for the consolidated settings tab
    departments = (
        db.query(Department)
        .filter(Department.tenant_id == current_tenant.id)
        .order_by(Department.name.asc())
        .all()
    )
    dept_list = []
    for d in departments:
        d_dict = d.to_dict()
        emp_count = (
            db.query(func.count(Student.id))
            .filter(
                Student.tenant_id == current_tenant.id,
                (Student.department_id == d.id) | (Student.department == d.name),
            )
            .scalar()
            or 0
        )
        d_dict["employee_count"] = emp_count
        dept_list.append(d_dict)

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
            "departments": dept_list,
            "is_corporate": is_corporate,
        },
    )


@router.get("/payroll", response_class=HTMLResponse)
def page_payroll(
    request: Request,
    tenant_id: Optional[int] = None,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Corporate Payroll & Wage Management Dashboard."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    is_super_admin = bool(current_user and current_user.role == "SUPER_ADMIN")

    selected_tenant = current_tenant
    if is_super_admin and tenant_id:
        custom_t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if custom_t:
            selected_tenant = custom_t

    departments = db.query(Department).filter(Department.tenant_id == selected_tenant.id).order_by(Department.name.asc()).all()
    branding = get_branding_dict(db, selected_tenant.id)
    all_tenants = get_all_active_tenants(db)

    now_ist = get_ist_now()
    today_str = now_ist.strftime("%Y-%m-%d")
    first_of_month_str = now_ist.strftime("%Y-%m-01")

    tenant_type = (selected_tenant.tenant_type or "educational").lower()
    is_corporate = tenant_type in ["corporate", "company", "enterprise"]

    return templates.TemplateResponse(
        "payroll.html",
        {
            "request": request,
            "page_title": "Corporate Payroll & Wage Engine",
            "active_page": "payroll",
            "branding": branding,
            "current_tenant": selected_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
            "is_super_admin": is_super_admin,
            "selected_tenant_id": selected_tenant.id,
            "departments": [d.to_dict() for d in departments],
            "today_str": today_str,
            "first_of_month_str": first_of_month_str,
            "is_corporate": is_corporate,
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
    """
    Universal Multi-Tenant Platform Login Interface.
    Default header: 'Face Recognition - Attendance System'.
    """
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    all_tenants = get_all_active_tenants(db)

    # Universal Platform Branding
    branding = {
        "institution_name": "Face Recognition - Attendance System",
        "short_code": "FRAS-HUB",
        "tagline": "Enterprise Multi-Tenant Biometric Attendance Platform",
        "primary_accent_color": "#c2410c",
        "header_badge_text": "Platform Gateway",
    }

    available_roles = [
        {"key": "SUPER_ADMIN", "label": "Super Administrator", "icon": "fa-crown", "badge": "Platform Owner"},
        {"key": "TENANT_ADMIN", "label": "Tenant Administrator", "icon": "fa-user-shield", "badge": "Organization Admin"},
        {"key": "TEACHER", "label": "Teacher / Faculty", "icon": "fa-chalkboard-user", "badge": "Academic Staff"},
        {"key": "STUDENT", "label": "Student / Employee", "icon": "fa-user-graduate", "badge": "End User"},
    ]

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "page_title": "Sign In - Face Recognition Attendance System",
            "active_page": "login",
            "is_tenant_scoped": False,
            "branding": branding,
            "current_tenant": None,
            "tenant": None,
            "all_tenants": all_tenants,
            "available_roles": available_roles,
            "current_user": current_user.to_dict() if current_user else None,
        },
    )


@router.get("/super-admin/login", response_class=HTMLResponse)
def page_super_admin_login(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Dedicated, isolated Super Admin login page.
    Completely decoupled from multi-tenant contexts and tenant-level dropdowns.
    """
    current_user = get_current_user_optional(request, db)
    if current_user and current_user.role == "SUPER_ADMIN":
        return RedirectResponse("/super-admin", status_code=303)

    return templates.TemplateResponse(
        "super_admin_login.html",
        {
            "request": request,
            "page_title": "Super Admin Sign In - Global Control Plane",
            "active_page": "super_admin_login",
        },
    )


@router.get("/portal/{tenant_uuid}/{login_token}", response_class=HTMLResponse)
def page_tokenized_tenant_portal(
    tenant_uuid: str,
    login_token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Secure tokenized Organization Portal Login URL.
    Validates tenant UUID and token, then renders the dedicated tenant portal.
    """
    clean_uuid = tenant_uuid.strip().lower()
    tenant = db.query(Tenant).filter(
        (Tenant.uuid == tenant_uuid.strip()) | (Tenant.slug == clean_uuid),
        (Tenant.admin_token == login_token) | (Tenant.onboarding_token == login_token) | (Tenant.attendance_slug == login_token) | (Tenant.slug == login_token),
        Tenant.is_deleted == False,
    ).first()

    if not tenant:
        # Fallback check by UUID only if token was rotated
        tenant = db.query(Tenant).filter(
            (Tenant.uuid == tenant_uuid.strip()) | (Tenant.slug == clean_uuid),
            Tenant.is_deleted == False,
        ).first()

    if not tenant:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "page_title": "Organization Not Found",
                "active_page": "login",
                "is_tenant_scoped": False,
                "error_banner": f"Organization portal link is invalid or has expired.",
                "branding": {
                    "institution_name": "Face Recognition - Attendance System",
                    "tagline": "Enterprise Multi-Tenant Biometric Attendance Platform",
                    "primary_accent_color": "#c2410c",
                },
                "current_tenant": None,
                "tenant": None,
                "all_tenants": get_all_active_tenants(db),
                "available_roles": [],
            },
            status_code=404,
        )

    return render_tenant_portal_response(request, db, tenant)


@router.get("/portal/{tenant_identifier}", response_class=HTMLResponse)
def page_tenant_portal(
    tenant_identifier: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Tenant-Specific Biometric Face-Authentication Portal (by Vanity Slug or UUID).
    """
    clean_id = tenant_identifier.strip().lower()
    tenant = db.query(Tenant).filter(
        (Tenant.slug == clean_id) | (Tenant.uuid == tenant_identifier.strip()),
        Tenant.is_deleted == False,
    ).first()

    all_tenants = get_all_active_tenants(db)

    if not tenant:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "page_title": "Organization Not Found - Face Recognition Attendance System",
                "active_page": "login",
                "is_tenant_scoped": False,
                "error_banner": f"Organization '{tenant_identifier}' was not found or is currently deactivated.",
                "branding": {
                    "institution_name": "Face Recognition - Attendance System",
                    "tagline": "Enterprise Multi-Tenant Biometric Attendance Platform",
                    "primary_accent_color": "#c2410c",
                    "header_badge_text": "Platform Gateway",
                },
                "current_tenant": None,
                "tenant": None,
                "all_tenants": all_tenants,
                "available_roles": [],
            },
            status_code=404,
        )

    return render_tenant_portal_response(request, db, tenant)


@router.get("/login/{tenant_identifier}", response_class=HTMLResponse)
def page_tenant_credential_login(
    tenant_identifier: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Tenant-Specific Clean Text/Credential Sign In Page (No Auto-Starting Camera).
    Scoped exclusively to the organization with isolated branding, quick profiles, and role selector.
    """
    clean_id = tenant_identifier.strip().lower()
    tenant = db.query(Tenant).filter(
        (Tenant.slug == clean_id) | (Tenant.uuid == tenant_identifier.strip()),
        Tenant.is_deleted == False,
    ).first()

    all_tenants = get_all_active_tenants(db)

    if not tenant:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "page_title": "Organization Not Found - Face Recognition Attendance System",
                "active_page": "login",
                "is_tenant_scoped": False,
                "error_banner": f"Organization '{tenant_identifier}' was not found or is currently deactivated.",
                "branding": {
                    "institution_name": "Face Recognition - Attendance System",
                    "tagline": "Enterprise Multi-Tenant Biometric Attendance Platform",
                    "primary_accent_color": "#c2410c",
                    "header_badge_text": "Platform Gateway",
                },
                "current_tenant": None,
                "tenant": None,
                "all_tenants": all_tenants,
                "available_roles": [],
            },
            status_code=404,
        )

    t_type = (tenant.tenant_type or "educational").lower()
    is_corporate = bool(t_type in ["corporate", "company", "enterprise"])
    branding = get_branding_dict(db, tenant.id)

    if is_corporate:
        available_roles = [
            {"key": "TENANT_ADMIN", "label": "Tenant Administrator", "icon": "fa-user-shield", "badge": "Admin"},
            {"key": "EMPLOYEE", "label": "Employee", "icon": "fa-id-badge", "badge": "Staff"},
        ]
    else:
        available_roles = [
            {"key": "TENANT_ADMIN", "label": "Tenant Administrator", "icon": "fa-user-shield", "badge": "Admin"},
            {"key": "TEACHER", "label": "Teacher / Faculty", "icon": "fa-chalkboard-user", "badge": "Faculty"},
            {"key": "STUDENT", "label": "Student", "icon": "fa-user-graduate", "badge": "Student"},
        ]

    demo_users = []
    admin_u = db.query(User).filter(User.tenant_id == tenant.id, User.role == "TENANT_ADMIN", User.is_active == True).first()
    if admin_u:
        demo_users.append({
            "role": "TENANT_ADMIN",
            "label": "Tenant Admin",
            "username": admin_u.username,
            "icon": "fa-user-shield",
            "color": "var(--accent-primary)",
        })

    if is_corporate:
        first_emp = db.query(Student).filter(Student.tenant_id == tenant.id, Student.is_active == True).first()
        if first_emp:
            demo_users.append({
                "role": "EMPLOYEE",
                "label": "Employee",
                "username": first_emp.roll_number or str(first_emp.id),
                "icon": "fa-id-badge",
                "color": "var(--accent-emerald)",
            })
    else:
        teacher_u = db.query(User).filter(User.tenant_id == tenant.id, User.role == "TEACHER", User.is_active == True).first()
        if teacher_u:
            demo_users.append({
                "role": "TEACHER",
                "label": "Teacher",
                "username": teacher_u.username,
                "icon": "fa-chalkboard-user",
                "color": "var(--accent-emerald)",
            })
        student_u = db.query(User).filter(User.tenant_id == tenant.id, User.role == "STUDENT", User.is_active == True).first()
        if student_u:
            demo_users.append({
                "role": "STUDENT",
                "label": "Student",
                "username": student_u.username,
                "icon": "fa-user-graduate",
                "color": "var(--accent-cyan)",
            })

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "page_title": f"Sign In - {tenant.name}",
            "active_page": "login",
            "is_tenant_scoped": True,
            "is_corporate": is_corporate,
            "tenant": tenant.to_dict(),
            "branding": branding,
            "all_tenants": all_tenants,
            "available_roles": available_roles,
            "demo_users": demo_users,
        },
    )


def render_tenant_portal_response(request: Request, db: Session, tenant: Tenant) -> HTMLResponse:
    """Helper to render dedicated tenant_portal_login.html template."""
    t_type = (tenant.tenant_type or "educational").lower()
    is_corporate = t_type in ["corporate", "company", "enterprise"]
    branding = get_branding_dict(db, tenant.id)

    if is_corporate:
        available_roles = [
            {"key": "TENANT_ADMIN", "label": "Tenant Administrator", "icon": "fa-user-shield", "badge": "Admin"},
            {"key": "EMPLOYEE", "label": "Employee", "icon": "fa-id-badge", "badge": "Staff"},
        ]
    else:
        available_roles = [
            {"key": "TENANT_ADMIN", "label": "Tenant Administrator", "icon": "fa-user-shield", "badge": "Admin"},
            {"key": "TEACHER", "label": "Teacher / Faculty", "icon": "fa-chalkboard-user", "badge": "Faculty"},
            {"key": "STUDENT", "label": "Student", "icon": "fa-user-graduate", "badge": "Student"},
        ]

    # Gather quick-fill demo users for this tenant
    demo_users = []
    admin_u = db.query(User).filter(User.tenant_id == tenant.id, User.role == "TENANT_ADMIN", User.is_active == True).first()
    if admin_u:
        demo_users.append({
            "role": "TENANT_ADMIN",
            "label": "Tenant Admin",
            "username": admin_u.username,
            "icon": "fa-user-shield",
            "color": "var(--accent-primary)",
        })

    if is_corporate:
        first_emp = db.query(Student).filter(Student.tenant_id == tenant.id, Student.is_active == True).first()
        if first_emp:
            demo_users.append({
                "role": "EMPLOYEE",
                "label": "Employee",
                "username": first_emp.roll_number or str(first_emp.id),
                "icon": "fa-id-badge",
                "color": "var(--accent-emerald)",
            })
    else:
        teacher_u = db.query(User).filter(User.tenant_id == tenant.id, User.role == "TEACHER", User.is_active == True).first()
        if teacher_u:
            demo_users.append({
                "role": "TEACHER",
                "label": "Teacher",
                "username": teacher_u.username,
                "icon": "fa-chalkboard-user",
                "color": "var(--accent-emerald)",
            })
        student_u = db.query(User).filter(User.tenant_id == tenant.id, User.role == "STUDENT", User.is_active == True).first()
        if student_u:
            demo_users.append({
                "role": "STUDENT",
                "label": "Student",
                "username": student_u.username,
                "icon": "fa-user-graduate",
                "color": "var(--accent-cyan)",
            })

    return templates.TemplateResponse(
        "tenant_portal_login.html",
        {
            "request": request,
            "page_title": f"Sign In - {tenant.name} Portal",
            "active_page": "login",
            "tenant": tenant.to_dict(),
            "branding": branding,
            "is_corporate": is_corporate,
            "available_roles": available_roles,
            "demo_users": demo_users,
        },
    )


@router.get("/demo-login", response_class=HTMLResponse)
@router.get("/demo", response_class=HTMLResponse)
def page_demo_login(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Super Admin Demo Role-Switching Portal & Sandbox.
    Provides standard system layout with 1-click test login into any system role and tenant.
    """
    tenants = db.query(Tenant).filter(Tenant.is_deleted == False).order_by(Tenant.id.asc()).all()
    tenant_cards = []

    for t in tenants:
        t_type = (t.tenant_type or "educational").lower()
        is_corp = t_type in ["corporate", "company", "enterprise"]
        t_branding = get_branding_dict(db, t.id)
        
        users_list = []
        # Admin user
        t_admin = db.query(User).filter(User.tenant_id == t.id, User.role == "TENANT_ADMIN", User.is_active == True).first()
        if t_admin:
            users_list.append({
                "role": "TENANT_ADMIN",
                "role_name": "Tenant Administrator",
                "username": t_admin.username,
                "full_name": t_admin.full_name,
                "icon": "fa-user-shield",
                "badge_class": "badge-primary",
            })

        if is_corp:
            emp = db.query(Student).filter(Student.tenant_id == t.id, Student.is_active == True).first()
            if emp:
                users_list.append({
                    "role": "EMPLOYEE",
                    "role_name": "Employee Demo",
                    "username": emp.roll_number or str(emp.id),
                    "full_name": emp.name,
                    "icon": "fa-id-badge",
                    "badge_class": "badge-emerald",
                })
        else:
            teach = db.query(User).filter(User.tenant_id == t.id, User.role == "TEACHER", User.is_active == True).first()
            if teach:
                users_list.append({
                    "role": "TEACHER",
                    "role_name": "Teacher / Faculty",
                    "username": teach.username,
                    "full_name": teach.full_name,
                    "icon": "fa-chalkboard-user",
                    "badge_class": "badge-emerald",
                })
            stud = db.query(User).filter(User.tenant_id == t.id, User.role == "STUDENT", User.is_active == True).first()
            if stud:
                users_list.append({
                    "role": "STUDENT",
                    "role_name": "Student",
                    "username": stud.username,
                    "full_name": stud.full_name,
                    "icon": "fa-user-graduate",
                    "badge_class": "badge-cyan",
                })

        tenant_cards.append({
            "tenant": t.to_dict(),
            "branding": t_branding,
            "is_corporate": is_corp,
            "users": users_list,
            "login_url": f"/portal/{t.slug}",
        })

    super_admin_user = db.query(User).filter(User.role == "SUPER_ADMIN", User.is_active == True).first()

    return templates.TemplateResponse(
        "demo_login.html",
        {
            "request": request,
            "page_title": "Demo Sandbox & Role Switcher - Face Recognition Attendance System",
            "active_page": "demo",
            "super_admin": super_admin_user.to_dict() if super_admin_user else None,
            "tenant_cards": tenant_cards,
            "branding": {
                "institution_name": "Face Recognition - Attendance System",
                "tagline": "Super Admin Sandbox & Multi-Role Testing Portal",
                "primary_accent_color": "#c2410c",
            },
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
    
    # Strictly enforce SUPER_ADMIN role; redirect to dedicated super admin login otherwise
    if not current_user or current_user.role != "SUPER_ADMIN":
        return RedirectResponse("/super-admin/login?next=/super-admin", status_code=303)

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
@router.get("/departments", response_class=HTMLResponse)
@router.get("/teams", response_class=HTMLResponse)
def page_academic_management(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Tenant Admin Academic Structure / Corporate Departments & Teams Engine."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    
    # Super Admin scope cleanup: redirect Super Admin away from tenant-only academic management
    if current_user and current_user.role == "SUPER_ADMIN":
        return RedirectResponse("/super-admin", status_code=303)

    is_corporate = bool(current_tenant.tenant_type == "corporate")
    
    # For corporate tenants, consolidate departments & teams under settings
    if is_corporate:
        return RedirectResponse("/settings#departmentsSection", status_code=303)

    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)
    departments = db.query(Department).filter(Department.tenant_id == current_tenant.id).order_by(Department.name.asc()).all()
    classes = db.query(ClassModel).filter(ClassModel.tenant_id == current_tenant.id).order_by(ClassModel.name.asc()).all()
    divisions = db.query(Division).filter(Division.tenant_id == current_tenant.id).order_by(Division.name.asc()).all()
    academic_years = db.query(AcademicYear).filter(AcademicYear.tenant_id == current_tenant.id).order_by(AcademicYear.id.desc()).all()
    batches = db.query(StudentBatchUpload).filter(StudentBatchUpload.tenant_id == current_tenant.id).order_by(StudentBatchUpload.id.desc()).all()

    active_page_tag = "departments" if (is_corporate or any(request.url.path.startswith(p) for p in ["/departments", "/teams"])) else "academic"
    page_title = "Departments & Teams" if is_corporate else "Academic Management & Progression"

    return templates.TemplateResponse(
        "academic_management.html",
        {
            "request": request,
            "page_title": page_title,
            "active_page": active_page_tag,
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "departments": [d.to_dict() for d in departments],
            "classes": [c.to_dict() for c in classes],
            "divisions": [dv.to_dict() for dv in divisions],
            "academic_years": [y.to_dict() for y in academic_years],
            "batches": [b.to_dict() for b in batches],
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


@router.get("/self-attendance", response_class=HTMLResponse)
def page_self_attendance_default(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Public login-free self-attendance camera page for current/default tenant."""
    branding = get_branding_dict(db, fallback_tenant.id)
    is_enabled = bool(branding.get("enable_self_attendance", False))
    is_geo_set = branding.get("geo_latitude") is not None and branding.get("geo_longitude") is not None

    return templates.TemplateResponse(
        "self_attendance.html",
        {
            "request": request,
            "page_title": f"Self Attendance - {branding.get('institution_name', 'Campus')}",
            "branding": branding,
            "current_tenant": fallback_tenant.to_dict(),
            "tenant_slug": fallback_tenant.slug,
            "is_self_attendance_enabled": is_enabled,
            "is_geofence_configured": is_geo_set,
        },
    )


@router.get("/self-attendance/{tenant_slug}", response_class=HTMLResponse)
def page_self_attendance_tenant(
    tenant_slug: str,
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Public login-free self-attendance camera page for specific institution slug."""
    target_tenant = resolve_tenant(db, tenant_slug) or fallback_tenant
    branding = get_branding_dict(db, target_tenant.id)
    is_enabled = bool(branding.get("enable_self_attendance", False))
    is_geo_set = branding.get("geo_latitude") is not None and branding.get("geo_longitude") is not None

    return templates.TemplateResponse(
        "self_attendance.html",
        {
            "request": request,
            "page_title": f"Self Attendance - {branding.get('institution_name', 'Campus')}",
            "branding": branding,
            "current_tenant": target_tenant.to_dict(),
            "tenant_slug": target_tenant.slug,
            "tenant_uuid": target_tenant.uuid or target_tenant.slug,
            "attendance_slug": target_tenant.attendance_slug,
            "is_self_attendance_enabled": is_enabled,
            "is_geofence_configured": is_geo_set,
        },
    )


# ==============================================================================
# --- Tokenized Permanent Gateways (Passwordless Admin, Onboarding, Check-In) --
# ==============================================================================

@router.get("/auth/token-login/{tenant_uuid}/{admin_token}")
def handle_passwordless_admin_login(
    tenant_uuid: str,
    admin_token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Passwordless Instant Tenant Admin Login via unique tokenized URL.
    Validates tenant UUID and admin token, issues session cookies, and redirects to Dashboard.
    """
    tenant = db.query(Tenant).filter(
        (Tenant.uuid == tenant_uuid) | (Tenant.slug == tenant_uuid),
        Tenant.admin_token == admin_token,
    ).first()

    if not tenant:
        return RedirectResponse(url="/login?error=invalid_admin_token", status_code=303)

    if tenant.is_deleted or (tenant.subscription_status or "").upper() == "DELETED":
        return RedirectResponse(url="/login?error=tenant_deactivated", status_code=303)

    # Find or resolve primary TENANT_ADMIN user for this tenant
    admin_user = db.query(User).filter(
        User.tenant_id == tenant.id,
        User.role == "TENANT_ADMIN",
        User.is_active == True,
    ).first()

    if not admin_user:
        # Fallback: search any active admin user in tenant
        admin_user = db.query(User).filter(
            User.tenant_id == tenant.id,
            User.is_active == True,
        ).first()

    if not admin_user:
        # Create default tenant admin if missing
        admin_user = User(
            tenant_id=tenant.id,
            username=f"admin_{tenant.slug}",
            email=tenant.contact_email or f"admin@{tenant.slug}.local",
            password_hash=create_access_token(1, "TENANT_ADMIN", tenant.id, "temp"),
            role="TENANT_ADMIN",
            full_name=f"{tenant.name} Administrator",
            is_active=True,
        )
        db.add(admin_user)
        db.flush()

    admin_user.last_login_at = get_ist_now()

    token = create_access_token(
        user_id=admin_user.id,
        role="TENANT_ADMIN",
        tenant_id=tenant.id,
        username=admin_user.username,
    )

    # Record Audit Log
    try:
        audit = AuditLog(
            tenant_id=tenant.id,
            user_id=admin_user.id,
            actor_name=admin_user.full_name,
            actor_role="TENANT_ADMIN",
            action_type="TOKEN_LOGIN",
            target_type="USER",
            target_id=str(admin_user.id),
            description=f"Tenant Administrator '{admin_user.username}' logged in via perpetual tokenized link.",
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)
        db.commit()
    except Exception:
        db.rollback()

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("access_token", token, httponly=True, max_age=86400 * 30, path="/")
    response.set_cookie("active_role", "TENANT_ADMIN", httponly=False, max_age=86400 * 30, path="/")
    response.set_cookie("active_tenant_id", str(tenant.id), httponly=False, max_age=86400 * 30, path="/")
    return response


@router.get("/onboard/{tenant_uuid}/{onboarding_token}", response_class=HTMLResponse)
def page_employee_onboarding(
    tenant_uuid: str,
    onboarding_token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Public tokenized Employee Self-Onboarding Portal.
    Allows new hires/students to register their profile and capture biometric face samples.
    """
    tenant = db.query(Tenant).filter(
        (Tenant.uuid == tenant_uuid) | (Tenant.slug == tenant_uuid),
        Tenant.onboarding_token == onboarding_token,
        Tenant.is_deleted == False,
    ).first()

    if not tenant:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "page_title": "Invalid Onboarding Link",
                "error_message": "This employee onboarding link is invalid or has expired. Please contact your company administrator.",
                "branding": get_branding_dict(db, 1),
                "current_tenant": None,
                "all_tenants": [],
            },
            status_code=403,
        )

    branding = get_branding_dict(db, tenant.id)
    departments = db.query(Department).filter(Department.tenant_id == tenant.id).order_by(Department.name.asc()).all()
    is_corporate = (tenant.tenant_type == "corporate")

    return templates.TemplateResponse(
        "onboard.html",
        {
            "request": request,
            "page_title": f"Employee Onboarding - {tenant.name}",
            "branding": branding,
            "tenant": tenant.to_dict(),
            "tenant_uuid": tenant_uuid,
            "onboarding_token": onboarding_token,
            "departments": [d.to_dict() for d in departments],
            "is_corporate": is_corporate,
        },
    )


@router.get("/check-in/{tenant_uuid}/{attendance_slug}", response_class=HTMLResponse)
def page_permanent_self_attendance(
    tenant_uuid: str,
    attendance_slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Permanent tenant-specific self-attendance URL for daily employee check-ins.
    Enforces GPS geofencing and frictionless face biometric recognition.
    """
    tenant = db.query(Tenant).filter(
        (Tenant.uuid == tenant_uuid) | (Tenant.slug == tenant_uuid),
        Tenant.attendance_slug == attendance_slug,
        Tenant.is_deleted == False,
    ).first()

    if not tenant:
        # Fallback check slug
        tenant = resolve_tenant(db, tenant_uuid)

    if not tenant:
        return RedirectResponse(url="/login?error=invalid_checkin_url", status_code=303)

    branding = get_branding_dict(db, tenant.id)
    is_enabled = bool(branding.get("enable_self_attendance", False))
    is_geo_set = branding.get("geo_latitude") is not None and branding.get("geo_longitude") is not None

    return templates.TemplateResponse(
        "self_attendance.html",
        {
            "request": request,
            "page_title": f"Check-In - {branding.get('institution_name', tenant.name)}",
            "branding": branding,
            "current_tenant": tenant.to_dict(),
            "tenant_slug": tenant.slug,
            "tenant_uuid": tenant.uuid or tenant.slug,
            "attendance_slug": tenant.attendance_slug,
            "is_self_attendance_enabled": is_enabled,
            "is_geofence_configured": is_geo_set,
        },
    )


@router.get("/leave-management", response_class=HTMLResponse)
def page_leave_management(
    request: Request,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Tenant Admin Leave Review, Quotas Master, and Approval Dashboard.
    """
    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url=f"/portal/{current_tenant.slug}", status_code=303)

    if current_user.role not in ["SUPER_ADMIN", "TENANT_ADMIN"]:
        return RedirectResponse(url="/", status_code=303)

    seed_default_leave_types(db, current_tenant.id)
    db.commit()

    branding = get_branding_dict(db, current_tenant.id)
    departments = db.query(Department).filter(Department.tenant_id == current_tenant.id).order_by(Department.name.asc()).all()
    leave_types = db.query(LeaveType).filter(LeaveType.tenant_id == current_tenant.id, LeaveType.is_active == True).order_by(LeaveType.id.asc()).all()

    return templates.TemplateResponse(
        "leave_management.html",
        {
            "request": request,
            "page_title": "Leave Management & Approvals",
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": get_all_active_tenants(db) if current_user.role == "SUPER_ADMIN" else [],
            "current_user": current_user.to_dict(),
            "departments": [d.to_dict() for d in departments],
            "leave_types": [lt.to_dict() for lt in leave_types],
        },
    )


@router.get("/employee/{tenant_slug}", response_class=HTMLResponse)
@router.get("/portal/{tenant_slug}/employee", response_class=HTMLResponse)
def page_employee_face_login(
    tenant_slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Public landing page for dedicated employee face-recognition passwordless login.
    """
    tenant = resolve_tenant(db, tenant_slug)
    if not tenant:
        return RedirectResponse(url="/login?error=invalid_tenant", status_code=303)

    branding = get_branding_dict(db, tenant.id)

    # Check if already logged in via valid employee session cookie
    emp_token = request.cookies.get(EMP_COOKIE_NAME)
    if emp_token:
        payload = decode_employee_token(emp_token)
        if payload and payload.get("tenant_id") == tenant.id:
            return RedirectResponse(url=f"/employee/{tenant.slug}/dashboard", status_code=303)

    return templates.TemplateResponse(
        "employee_login.html",
        {
            "request": request,
            "page_title": f"Employee Face Login - {branding.get('institution_name', tenant.name)}",
            "branding": branding,
            "tenant": tenant.to_dict(),
            "tenant_slug": tenant.slug,
        },
    )


@router.get("/employee/{tenant_slug}/dashboard", response_class=HTMLResponse)
@router.get("/portal/{tenant_slug}/employee/dashboard", response_class=HTMLResponse)
def page_employee_self_service_dashboard(
    tenant_slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Authenticated Employee Self-Service Mobile Portal.
    Displays shift logs, transparent wages, leave balances, and leave application.
    """
    tenant = resolve_tenant(db, tenant_slug)
    if not tenant:
        return RedirectResponse(url="/login?error=invalid_tenant", status_code=303)

    emp_token = request.cookies.get(EMP_COOKIE_NAME)
    if not emp_token:
        return RedirectResponse(url=f"/employee/{tenant.slug}?error=auth_required", status_code=303)

    payload = decode_employee_token(emp_token)
    if not payload or payload.get("tenant_id") != tenant.id:
        return RedirectResponse(url=f"/employee/{tenant.slug}?error=session_expired", status_code=303)

    student = (
        db.query(Student)
        .filter(
            Student.id == payload.get("student_id"),
            Student.tenant_id == tenant.id,
            Student.is_active == True,
        )
        .first()
    )

    if not student:
        return RedirectResponse(url=f"/employee/{tenant.slug}?error=inactive_account", status_code=303)

    seed_default_leave_types(db, tenant.id)
    db.commit()

    branding = get_branding_dict(db, tenant.id)
    leave_types = db.query(LeaveType).filter(LeaveType.tenant_id == tenant.id, LeaveType.is_active == True).order_by(LeaveType.id.asc()).all()

    return templates.TemplateResponse(
        "employee_portal.html",
        {
            "request": request,
            "page_title": f"Employee Portal - {student.name}",
            "branding": branding,
            "tenant": tenant.to_dict(),
            "tenant_slug": tenant.slug,
            "employee": student.to_dict(),
            "leave_types": [lt.to_dict() for lt in leave_types],
        },
    )
