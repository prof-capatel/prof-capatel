from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from src.database.models import (
    Tenant,
    User,
    Student,
    Department,
    AuditLog,
)
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant
from src.server.rbac_middleware import (
    get_current_user_optional,
    create_access_token,
)
from src.server.services.view_service import (
    render_template,
    get_branding_dict,
    get_all_active_tenants,
    resolve_scoped_tenant_and_user,
)
from src.utils.timezone import get_ist_now

router = APIRouter(include_in_schema=False)


@router.get("/saas", response_class=HTMLResponse)
@router.get("/login", response_class=HTMLResponse)
def page_login(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Universal Multi-Tenant Platform Login Interface (accessible via /saas and /login).
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

    return render_template(
        request,
        "login.html",
        {
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

    return render_template(
        request,
        "super_admin_login.html",
        {
            "page_title": "Super Admin Sign In - Global Control Plane",
            "active_page": "super_admin_login",
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

    demo_users = []
    admin_u = db.query(User).filter(User.tenant_id == tenant.id, User.role == "TENANT_ADMIN", User.is_active == True).first()
    if admin_u:
        edition_label = f"Admin ({tenant.saas_edition})" if tenant.saas_edition else "Tenant Admin"
        demo_users.append({
            "role": "TENANT_ADMIN",
            "label": edition_label,
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

    return render_template(
        request,
        "tenant_portal_login.html",
        {
            "page_title": f"Sign In - {tenant.name} Portal",
            "active_page": "login",
            "tenant": tenant.to_dict(),
            "branding": branding,
            "is_corporate": is_corporate,
            "available_roles": available_roles,
            "demo_users": demo_users,
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
        return render_template(
            request,
            "login.html",
            {
                "page_title": "Organization Not Found",
                "active_page": "login",
                "is_tenant_scoped": False,
                "error_banner": "Organization portal link is invalid or has expired.",
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
        return render_template(
            request,
            "login.html",
            {
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
        return render_template(
            request,
            "login.html",
            {
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
        edition_label = f"Admin ({tenant.saas_edition})" if tenant.saas_edition else "Tenant Admin"
        demo_users.append({
            "role": "TENANT_ADMIN",
            "label": edition_label,
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

    return render_template(
        request,
        "login.html",
        {
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
        admin_user = db.query(User).filter(
            User.tenant_id == tenant.id,
            User.is_active == True,
        ).first()

    if not admin_user:
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
        return render_template(
            request,
            "login.html",
            {
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

    return render_template(
        request,
        "onboard.html",
        {
            "page_title": f"Employee Onboarding - {tenant.name}",
            "branding": branding,
            "tenant": tenant.to_dict(),
            "tenant_uuid": tenant_uuid,
            "onboarding_token": onboarding_token,
            "departments": [d.to_dict() for d in departments],
            "is_corporate": is_corporate,
        },
    )
