from fastapi import APIRouter, Request, Depends, Response
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from sqlalchemy.orm import Session

from src.database.models import Tenant, User, Student
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant
from src.server.rbac_middleware import get_current_user_optional
from src.server.services.view_service import (
    render_template,
    get_branding_dict,
    get_all_active_tenants,
    check_employee_portal_redirect,
)
from src.server.services import seo_service

router = APIRouter(include_in_schema=False)


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    """Technical SEO robots.txt file with dynamic rules from Super Admin SEO Hub."""
    return PlainTextResponse(content=seo_service.get_robots_txt(), media_type="text/plain")


@router.get("/sitemap.xml")
def sitemap_xml():
    """Technical SEO sitemap.xml file dynamically generated with search priority."""
    return Response(content=seo_service.get_sitemap_xml(), media_type="application/xml")



@router.get("/", response_class=HTMLResponse)
def page_landing(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Public Enterprise Marketing & Product Showcase Landing Page.
    Unauthenticated visitors see the marketing showcase.
    Authenticated users are redirected to their active dashboard/portal,
    unless ?view=landing is explicitly requested.
    """
    view_mode = request.query_params.get("view")
    if view_mode != "landing":
        emp_redirect = check_employee_portal_redirect(request, db)
        if emp_redirect:
            return emp_redirect

    current_user = get_current_user_optional(request, db)

    if current_user and view_mode != "landing":
        if current_user.role == "TEACHER":
            return RedirectResponse(url="/teacher-portal", status_code=303)
        if current_user.role in ["STUDENT", "EMPLOYEE"]:
            return RedirectResponse(url="/logs", status_code=303)
        from src.server.routes.views_dashboard import page_dashboard
        return page_dashboard(request=request, db=db, fallback_tenant=fallback_tenant)

    all_tenants = get_all_active_tenants(db)
    branding = {
        "institution_name": "Curiosity HUB",
        "short_code": "CURIOSITY-HUB",
        "tagline": "AI Biometric Attendance & Employee Management SaaS Platform",
        "primary_accent_color": "#c2410c",
        "header_badge_text": "Enterprise SaaS Platform",
    }

    seo_config = seo_service.get_seo_settings()
    return render_template(
        request,
        "landing.html",
        {
            "page_title": seo_config.get("site_title", "Curiosity HUB — Face Recognition Employee Management SaaS"),
            "active_page": "landing",
            "branding": branding,
            "seo": seo_config,
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
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

    return render_template(
        request,
        "demo_login.html",
        {
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


# =========================================================================
# TARGETED HIGH-INTENT SAAS LANDING & RESOURCE HUB ROUTES
# =========================================================================

def _get_public_page_context(request: Request, db: Session, active_page: str, page_title: str):
    """Helper to assemble shared branding, SEO, tenants and session context."""
    all_tenants = get_all_active_tenants(db)
    branding = {
        "institution_name": "Curiosity HUB",
        "short_code": "CURIOSITY-HUB",
        "tagline": "AI Biometric Attendance & Employee Management SaaS Platform",
        "primary_accent_color": "#c2410c",
        "header_badge_text": "Enterprise SaaS Platform",
    }
    seo_config = seo_service.get_seo_settings()
    current_user = get_current_user_optional(request, db)
    return {
        "page_title": page_title,
        "active_page": active_page,
        "branding": branding,
        "seo": seo_config,
        "all_tenants": all_tenants,
        "current_user": current_user.to_dict() if current_user else None,
    }


@router.get("/cloud-face-recognition-attendance", response_class=HTMLResponse)
def page_cloud_face_attendance(request: Request, db: Session = Depends(get_db)):
    """Dedicated landing page for Cloud Face Recognition Attendance System."""
    ctx = _get_public_page_context(
        request, db,
        active_page="cloud_face_attendance",
        page_title="Cloud Face Recognition Attendance System | Curiosity HUB",
    )
    return render_template(request, "cloud_face_attendance.html", ctx)


@router.get("/tablet-mobile-attendance-kiosk", response_class=HTMLResponse)
def page_tablet_mobile_kiosk(request: Request, db: Session = Depends(get_db)):
    """Dedicated landing page for Tablet & Mobile Attendance Kiosk Software."""
    ctx = _get_public_page_context(
        request, db,
        active_page="tablet_mobile_kiosk",
        page_title="Tablet & Mobile Attendance Kiosk Software | Curiosity HUB",
    )
    return render_template(request, "tablet_mobile_kiosk.html", ctx)


@router.get("/zero-hardware-time-tracking", response_class=HTMLResponse)
def page_zero_hardware_time_tracking(request: Request, db: Session = Depends(get_db)):
    """Dedicated landing page for Zero-Hardware Time Tracking Software."""
    ctx = _get_public_page_context(
        request, db,
        active_page="zero_hardware_time_tracking",
        page_title="Zero-Hardware Time Tracking Software | Curiosity HUB SaaS",
    )
    return render_template(request, "zero_hardware_time_tracking.html", ctx)


@router.get("/leave-management-software", response_class=HTMLResponse)
def page_leave_management_product(request: Request, db: Session = Depends(get_db)):
    """Dedicated product page for Leave Management Software."""
    ctx = _get_public_page_context(
        request, db,
        active_page="leave_management_product",
        page_title="Leave Management Software & Attendance Sync | Curiosity HUB",
    )
    return render_template(request, "leave_management_product.html", ctx)


@router.get("/automated-payroll-software", response_class=HTMLResponse)
def page_automated_payroll_product(request: Request, db: Session = Depends(get_db)):
    """Dedicated product page for Automated Payroll Software."""
    ctx = _get_public_page_context(
        request, db,
        active_page="automated_payroll_product",
        page_title="Automated Payroll Software with Attendance | Curiosity HUB",
    )
    return render_template(request, "automated_payroll_product.html", ctx)


@router.get("/saas-vs-hardware-attendance", response_class=HTMLResponse)
def page_saas_vs_hardware(request: Request, db: Session = Depends(get_db)):
    """Dedicated comparison page: Cloud SaaS vs. Traditional Biometric Machines."""
    ctx = _get_public_page_context(
        request, db,
        active_page="saas_vs_hardware",
        page_title="SaaS vs Biometric Machine: Attendance Cost Comparison Guide",
    )
    return render_template(request, "saas_vs_hardware.html", ctx)


@router.get("/tools/attendance-roi-calculator", response_class=HTMLResponse)
def page_roi_calculator(request: Request, db: Session = Depends(get_db)):
    """Interactive Attendance ROI & Buddy-Punching Cost Savings Calculator."""
    ctx = _get_public_page_context(
        request, db,
        active_page="roi_calculator",
        page_title="Attendance ROI & Buddy Punching Calculator | Curiosity HUB",
    )
    return render_template(request, "roi_calculator.html", ctx)


@router.get("/resources/attendance-policy-template", response_class=HTMLResponse)
def page_attendance_policy_template(request: Request, db: Session = Depends(get_db)):
    """Downloadable Corporate HR Attendance & Punctuality Policy Template."""
    ctx = _get_public_page_context(
        request, db,
        active_page="attendance_policy_template",
        page_title="Employee Attendance Policy Template (2026) | Curiosity HUB",
    )
    return render_template(request, "attendance_policy_template.html", ctx)


@router.get("/resources/holiday-calendar-2026", response_class=HTMLResponse)
def page_holiday_calendar_2026(request: Request, db: Session = Depends(get_db)):
    """2026 Indian Public, Gazetted & Regional Holiday Calendar Resource Hub."""
    ctx = _get_public_page_context(
        request, db,
        active_page="holiday_calendar_2026",
        page_title="Indian Public & Bank Holiday Calendar 2026 | Curiosity HUB",
    )
    return render_template(request, "holiday_calendar_2026.html", ctx)


@router.get("/onboarding-guide", response_class=HTMLResponse)
def page_onboarding_guide(request: Request, db: Session = Depends(get_db)):
    """Crawlable full-length 10-step administrator onboarding and setup guide."""
    ctx = _get_public_page_context(
        request, db,
        active_page="onboarding_guide",
        page_title="Curiosity HUB SaaS Quick Onboarding & Setup Guide (2026)",
    )
    return render_template(request, "onboarding_guide_page.html", ctx)


@router.get("/compare-editions", response_class=HTMLResponse)
def page_compare_editions(request: Request, db: Session = Depends(get_db)):
    """Full architectural specification comparison across Basic, Smart, and Pro editions."""
    ctx = _get_public_page_context(
        request, db,
        active_page="compare_editions",
        page_title="Curiosity HUB Edition Comparison: Basic vs Smart vs Pro",
    )
    return render_template(request, "compare_editions_page.html", ctx)


@router.get("/face-attendance-for-retail", response_class=HTMLResponse)
def page_retail_attendance(request: Request, db: Session = Depends(get_db)):
    """Dedicated retail store & multi-outlet attendance solution page."""
    ctx = _get_public_page_context(
        request, db,
        active_page="retail_attendance",
        page_title="Face Attendance for Retail Shops & Chains | Curiosity HUB",
    )
    return render_template(request, "retail_attendance.html", ctx)


@router.get("/face-attendance-for-factories", response_class=HTMLResponse)
def page_factory_attendance(request: Request, db: Session = Depends(get_db)):
    """Industrial manufacturing plant and factory shift attendance solution page."""
    ctx = _get_public_page_context(
        request, db,
        active_page="factory_attendance",
        page_title="Face Attendance for Factories & Manufacturing | Curiosity HUB",
    )
    return render_template(request, "factory_attendance.html", ctx)


@router.get("/face-attendance-for-corporate-offices", response_class=HTMLResponse)
def page_corporate_attendance(request: Request, db: Session = Depends(get_db)):
    """Corporate office, multi-branch, and tech park attendance solution page."""
    ctx = _get_public_page_context(
        request, db,
        active_page="corporate_attendance",
        page_title="Face Attendance for Corporate Offices | Curiosity HUB",
    )
    return render_template(request, "corporate_attendance.html", ctx)


@router.get("/face-attendance-for-field-teams", response_class=HTMLResponse)
def page_field_attendance(request: Request, db: Session = Depends(get_db)):
    """Field sales, remote workers, and mobile GPS geofenced attendance solution page."""
    ctx = _get_public_page_context(
        request, db,
        active_page="field_attendance",
        page_title="Face Attendance for Field Teams & Remote Staff | Curiosity HUB",
    )
    return render_template(request, "field_attendance.html", ctx)


@router.get("/face-attendance-software-ahmedabad", response_class=HTMLResponse)
def page_ahmedabad_attendance(request: Request, db: Session = Depends(get_db)):
    """Local landing page for Ahmedabad and Gujarat commercial & industrial enterprises."""
    ctx = _get_public_page_context(
        request, db,
        active_page="ahmedabad_attendance",
        page_title="Face Attendance Software in Ahmedabad | Curiosity HUB",
    )
    return render_template(request, "ahmedabad_attendance.html", ctx)


@router.get("/biometric-data-policy", response_class=HTMLResponse)
def page_biometric_data_policy(request: Request, db: Session = Depends(get_db)):
    """Biometric data protection, mathematical vector non-reversibility, and DPDP Act 2023 policy."""
    ctx = _get_public_page_context(
        request, db,
        active_page="biometric_data_policy",
        page_title="Biometric Data & DPDP Compliance Policy | Curiosity HUB",
    )
    return render_template(request, "biometric_data_policy.html", ctx)


@router.get("/privacy-policy", response_class=HTMLResponse)
def page_privacy_policy(request: Request, db: Session = Depends(get_db)):
    """Curiosity HUB platform Privacy Policy."""
    ctx = _get_public_page_context(
        request, db,
        active_page="privacy_policy",
        page_title="Privacy Policy | Curiosity HUB Attendance SaaS",
    )
    return render_template(request, "privacy_policy.html", ctx)


@router.get("/terms", response_class=HTMLResponse)
def page_terms(request: Request, db: Session = Depends(get_db)):
    """Curiosity HUB platform Terms of Service."""
    ctx = _get_public_page_context(
        request, db,
        active_page="terms",
        page_title="Terms of Service | Curiosity HUB Attendance SaaS",
    )
    return render_template(request, "terms_of_service.html", ctx)


