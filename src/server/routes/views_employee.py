from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from src.database.models import (
    Tenant,
    Student,
    LeaveType,
)
from src.database.session import get_db, seed_default_leave_types
from src.server.tenant_middleware import get_current_tenant, resolve_tenant
from src.server.routes.api_employee_portal import decode_employee_token, EMP_COOKIE_NAME
from src.server.services.view_service import (
    render_template,
    get_branding_dict,
    get_all_active_tenants,
    resolve_scoped_tenant_and_user,
)

router = APIRouter(include_in_schema=False)


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

    return render_template(
        request,
        "mobile_capture.html",
        {
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

    return render_template(
        request,
        "face_demo.html",
        {
            "page_title": "Visual Recognition Demo (Non-Logging)",
            "active_page": "demo",
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
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

    return render_template(
        request,
        "self_attendance.html",
        {
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

    return render_template(
        request,
        "self_attendance.html",
        {
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
        tenant = resolve_tenant(db, tenant_uuid)

    if not tenant:
        return RedirectResponse(url="/login?error=invalid_checkin_url", status_code=303)

    branding = get_branding_dict(db, tenant.id)
    is_enabled = bool(branding.get("enable_self_attendance", False))
    is_geo_set = branding.get("geo_latitude") is not None and branding.get("geo_longitude") is not None

    return render_template(
        request,
        "self_attendance.html",
        {
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

    emp_token = request.cookies.get(EMP_COOKIE_NAME)
    if emp_token:
        payload = decode_employee_token(emp_token)
        if payload and payload.get("tenant_id") == tenant.id:
            return RedirectResponse(url=f"/employee/{tenant.slug}/dashboard", status_code=303)

    return render_template(
        request,
        "employee_login.html",
        {
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

    return render_template(
        request,
        "employee_portal.html",
        {
            "page_title": f"Employee Portal - {student.name}",
            "branding": branding,
            "tenant": tenant.to_dict(),
            "tenant_slug": tenant.slug,
            "employee": student.to_dict(),
            "leave_types": [lt.to_dict() for lt in leave_types],
        },
    )
