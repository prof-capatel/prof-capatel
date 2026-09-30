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
