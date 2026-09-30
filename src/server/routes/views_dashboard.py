from datetime import date
from typing import List, Tuple, Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

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
    WorkShift,
    PayrollPayslip,
    CompanyLocation,
    DesignationMaster,
    SalaryTemplate,
)
from src.database.session import get_db, seed_default_leave_types
from src.server.tenant_middleware import get_current_tenant
from src.server.rbac_middleware import get_current_user_optional
from src.server.routes.views_public import router as public_router
from src.server.routes.views_auth import router as auth_router
from src.server.routes.views_employee import router as employee_router
from src.server.services.view_service import (
    render_template,
    get_branding_dict,
    get_all_active_tenants,
    resolve_scoped_tenant_and_user,
    get_current_employee_session,
    check_employee_portal_redirect,
    get_tenant_roles_list,
)
from src.core.payroll_engine import number_to_words_inr
from src.utils.timezone import get_ist_now

router = APIRouter(include_in_schema=False)

# Re-export and mount public, auth, and employee sub-routers for complete backward compatibility
router.include_router(public_router)
router.include_router(auth_router)
router.include_router(employee_router)


@router.get("/dashboard", response_class=HTMLResponse)
def page_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Main Admin Overview Dashboard.
    Requires authentication. Unauthenticated requests are redirected to /saas.
    """
    emp_redirect = check_employee_portal_redirect(request, db)
    if emp_redirect:
        return emp_redirect

    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)

    # Require authentication: unauthenticated visitors must be redirected to /saas
    if not current_user:
        return RedirectResponse(url="/saas", status_code=303)

    # If logged in as Teacher, redirect to their workspace
    if current_user.role == "TEACHER":
        return RedirectResponse(url="/teacher-portal", status_code=303)
    if current_user.role in ["STUDENT", "EMPLOYEE"]:
        return RedirectResponse(url="/logs", status_code=303)

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

    # Modular SaaS leave metrics
    today_date = get_ist_now().date()
    today_leaves_count = 0
    pending_leaves_count = 0
    if current_tenant.has_leave_module:
        today_leaves_count = (
            db.query(LeaveRequest)
            .filter(
                LeaveRequest.tenant_id == current_tenant.id,
                LeaveRequest.status == "APPROVED",
                LeaveRequest.start_date <= today_date,
                LeaveRequest.end_date >= today_date,
            )
            .count()
        )
        pending_leaves_count = (
            db.query(LeaveRequest)
            .filter(
                LeaveRequest.tenant_id == current_tenant.id,
                LeaveRequest.status == "PENDING",
            )
            .count()
        )

    return render_template(
        request,
        "dashboard.html",
        {
            "page_title": "Dashboard",
            "active_page": "dashboard",
            "total_students": total_students,
            "is_corporate": is_corporate,
            "member_label": member_label,
            "today_leaves_count": today_leaves_count,
            "pending_leaves_count": pending_leaves_count,
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
    emp_redirect = check_employee_portal_redirect(request, db)
    if emp_redirect:
        return emp_redirect

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
        .options(
            joinedload(Student.department_rel),
            joinedload(Student.designation_rel),
            joinedload(Student.location),
            joinedload(Student.shift),
            joinedload(Student.class_obj),
            joinedload(Student.division_obj),
        )
        .order_by(Student.name.asc())
        .all()
    )
    departments = db.query(Department).filter(Department.tenant_id == selected_tenant.id).order_by(Department.name.asc()).all()
    classes = db.query(ClassModel).filter(ClassModel.tenant_id == selected_tenant.id).order_by(ClassModel.name.asc()).all()
    divisions = db.query(Division).filter(Division.tenant_id == selected_tenant.id).order_by(Division.name.asc()).all()
    branding = get_branding_dict(db, selected_tenant.id)
    all_tenants = get_all_active_tenants(db)
    tenant_roles = get_tenant_roles_list(db, selected_tenant)
    work_shifts = db.query(WorkShift).filter(WorkShift.tenant_id == selected_tenant.id).order_by(WorkShift.is_default.desc(), WorkShift.name.asc()).all()
    locations = db.query(CompanyLocation).filter(CompanyLocation.tenant_id == selected_tenant.id, CompanyLocation.is_active == True).order_by(CompanyLocation.name.asc()).all()
    designations = db.query(DesignationMaster).filter(DesignationMaster.tenant_id == selected_tenant.id, DesignationMaster.is_active == True).order_by(DesignationMaster.title.asc()).all()
    salary_templates = db.query(SalaryTemplate).filter(SalaryTemplate.tenant_id == selected_tenant.id, SalaryTemplate.is_active == True).order_by(SalaryTemplate.name.asc()).all()

    active_page_tag = "employees" if (is_corporate or request.url.path.startswith("/employees")) else "students"
    page_title = "Employee Directory" if is_corporate else "Student Directory"

    return render_template(
        request,
        "students.html",
        {
            "page_title": page_title,
            "active_page": active_page_tag,
            "students": [s.to_dict() for s in students],
            "departments": [d.to_dict() for d in departments],
            "classes": [c.to_dict() for c in classes],
            "divisions": [dv.to_dict() for dv in divisions],
            "work_shifts": [ws.to_dict() for ws in work_shifts],
            "company_locations": [l.to_dict() for l in locations],
            "designations": [d.to_dict() for d in designations],
            "salary_templates": [st.to_dict() for st in salary_templates],
            "branding": branding,
            "current_tenant": selected_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
            "is_super_admin": is_super_admin,
            "selected_tenant_id": selected_tenant.id,
            "tenant_roles": tenant_roles,
            "is_corporate": is_corporate,
        },
    )


@router.get("/enroll", response_class=HTMLResponse)
def page_enroll(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Interactive Browser & Guided Face Enrollment."""
    emp_redirect = check_employee_portal_redirect(request, db)
    if emp_redirect:
        return emp_redirect

    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    is_corporate = bool(current_tenant and current_tenant.tenant_type == "corporate")
    departments = db.query(Department).filter(Department.tenant_id == current_tenant.id).order_by(Department.name.asc()).all()
    classes = db.query(ClassModel).filter(ClassModel.tenant_id == current_tenant.id).order_by(ClassModel.name.asc()).all()
    divisions = db.query(Division).filter(Division.tenant_id == current_tenant.id).order_by(Division.name.asc()).all()
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)
    tenant_roles = get_tenant_roles_list(db, current_tenant)
    work_shifts = db.query(WorkShift).filter(WorkShift.tenant_id == current_tenant.id, WorkShift.is_active == True).order_by(WorkShift.is_default.desc(), WorkShift.name.asc()).all()
    locations = db.query(CompanyLocation).filter(CompanyLocation.tenant_id == current_tenant.id, CompanyLocation.is_active == True).order_by(CompanyLocation.name.asc()).all()
    designations = db.query(DesignationMaster).filter(DesignationMaster.tenant_id == current_tenant.id, DesignationMaster.is_active == True).order_by(DesignationMaster.title.asc()).all()
    salary_templates = db.query(SalaryTemplate).filter(SalaryTemplate.tenant_id == current_tenant.id, SalaryTemplate.is_active == True).order_by(SalaryTemplate.name.asc()).all()

    page_title = "Register New Employee" if is_corporate else "Enroll New Student"

    return render_template(
        request,
        "enroll.html",
        {
            "page_title": page_title,
            "active_page": "enroll",
            "departments": [d.to_dict() for d in departments],
            "classes": [c.to_dict() for c in classes],
            "divisions": [dv.to_dict() for dv in divisions],
            "work_shifts": [ws.to_dict() for ws in work_shifts],
            "company_locations": [l.to_dict() for l in locations],
            "designations": [d.to_dict() for d in designations],
            "salary_templates": [st.to_dict() for st in salary_templates],
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
            "tenant_roles": tenant_roles,
            "is_corporate": is_corporate,
        },
    )


@router.get("/logs", response_class=HTMLResponse)
def page_logs(
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Full Attendance Log Audit & Export."""
    emp_redirect = check_employee_portal_redirect(request, db)
    if emp_redirect:
        return emp_redirect

    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    today_str = date.today().isoformat()
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    # Fetch tenant-scoped departments
    dept_objs = (
        db.query(Department)
        .filter(Department.tenant_id == current_tenant.id)
        .order_by(Department.name.asc())
        .all()
    )
    dept_names = [d.name for d in dept_objs if d.name]

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

    tenant_type = (current_tenant.tenant_type or "education").lower()
    is_corporate = tenant_type in ["corporate", "company", "enterprise"]

    if is_corporate:
        base_roles = ["employee", "manager", "admin_staff", "contractor", "intern", "other"]
    else:
        base_roles = ["student", "teacher", "admin_staff", "other"]

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

    return render_template(
        request,
        "logs.html",
        {
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
    emp_redirect = check_employee_portal_redirect(request, db)
    if emp_redirect:
        return emp_redirect

    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    nodes = db.query(NodeDevice).filter(NodeDevice.tenant_id == current_tenant.id).all()
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    return render_template(
        request,
        "nodes.html",
        {
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
    emp_redirect = check_employee_portal_redirect(request, db)
    if emp_redirect:
        return emp_redirect

    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    tenant_type = (current_tenant.tenant_type or "educational").lower()
    is_corporate = tenant_type in ["corporate", "company", "enterprise"]
    member_label = "Employees" if is_corporate else "Students"

    return render_template(
        request,
        "analytics.html",
        {
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
    emp_redirect = check_employee_portal_redirect(request, db)
    if emp_redirect:
        return emp_redirect

    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)
    
    tenant_type = (current_tenant.tenant_type or "educational").lower()
    is_corporate = tenant_type in ["corporate", "company", "enterprise"]

    # Fetch departments and calculate employee counts
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
    work_shifts = db.query(WorkShift).filter(WorkShift.tenant_id == current_tenant.id).order_by(WorkShift.is_default.desc(), WorkShift.name.asc()).all()

    # Fetch designations and calculate employee counts
    designations = (
        db.query(DesignationMaster)
        .filter(DesignationMaster.tenant_id == current_tenant.id)
        .order_by(DesignationMaster.title.asc())
        .all()
    )
    desig_list = []
    for des in designations:
        des_dict = des.to_dict()
        emp_count = (
            db.query(func.count(Student.id))
            .filter(
                Student.tenant_id == current_tenant.id,
                (Student.designation_id == des.id) | (Student.designation == des.title),
                Student.is_active == True,
            )
            .scalar()
            or 0
        )
        des_dict["employee_count"] = emp_count
        desig_list.append(des_dict)

    # Fetch locations
    locations = (
        db.query(CompanyLocation)
        .filter(CompanyLocation.tenant_id == current_tenant.id)
        .order_by(CompanyLocation.name.asc())
        .all()
    )
    loc_list = []
    for loc in locations:
        loc_dict = loc.to_dict()
        emp_count = (
            db.query(func.count(Student.id))
            .filter(
                Student.tenant_id == current_tenant.id,
                Student.location_id == loc.id,
                Student.is_active == True,
            )
            .scalar()
            or 0
        )
        loc_dict["employee_count"] = emp_count
        loc_list.append(loc_dict)

    return render_template(
        request,
        "settings.html",
        {
            "page_title": "System Settings & Theme",
            "active_page": "settings",
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
            "departments": dept_list,
            "designations": desig_list,
            "company_locations": loc_list,
            "work_shifts": [ws.to_dict() for ws in work_shifts],
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
    emp_redirect = check_employee_portal_redirect(request, db)
    if emp_redirect:
        return emp_redirect

    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    is_super_admin = bool(current_user and current_user.role == "SUPER_ADMIN")

    selected_tenant = current_tenant
    if is_super_admin and tenant_id:
        custom_t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if custom_t:
            selected_tenant = custom_t

    # Modular SaaS Edition Protection (Pro only)
    if not selected_tenant.has_payroll_module and not is_super_admin:
        return RedirectResponse(
            url="/?notice=The+Payroll+module+is+available+on+the+Pro+edition.+Please+contact+your+Super+Admin+to+upgrade.",
            status_code=303,
        )

    departments = db.query(Department).filter(Department.tenant_id == selected_tenant.id).order_by(Department.name.asc()).all()
    locations = db.query(CompanyLocation).filter(CompanyLocation.tenant_id == selected_tenant.id).order_by(CompanyLocation.name.asc()).all()
    designations = db.query(DesignationMaster).filter(DesignationMaster.tenant_id == selected_tenant.id).order_by(DesignationMaster.title.asc()).all()
    salary_templates = db.query(SalaryTemplate).filter(SalaryTemplate.tenant_id == selected_tenant.id).order_by(SalaryTemplate.name.asc()).all()
    branding = get_branding_dict(db, selected_tenant.id)
    all_tenants = get_all_active_tenants(db)

    now_ist = get_ist_now()
    today_str = now_ist.strftime("%Y-%m-%d")
    first_of_month_str = now_ist.strftime("%Y-%m-01")

    tenant_type = (selected_tenant.tenant_type or "educational").lower()
    is_corporate = tenant_type in ["corporate", "company", "enterprise"]

    return render_template(
        request,
        "payroll.html",
        {
            "page_title": "Payroll management",
            "active_page": "payroll",
            "branding": branding,
            "current_tenant": selected_tenant.to_dict(),
            "all_tenants": all_tenants,
            "current_user": current_user.to_dict() if current_user else None,
            "is_super_admin": is_super_admin,
            "selected_tenant_id": selected_tenant.id,
            "departments": [d.to_dict() for d in departments],
            "company_locations": [l.to_dict() for l in locations],
            "designations": [d.to_dict() for d in designations],
            "salary_templates": [st.to_dict() for st in salary_templates],
            "today_str": today_str,
            "first_of_month_str": first_of_month_str,
            "is_corporate": is_corporate,
        },
    )


@router.get("/payroll/payslip/{payslip_id}", response_class=HTMLResponse)
def page_payslip_view(
    payslip_id: int,
    request: Request,
    db: Session = Depends(get_db),
    fallback_tenant: Tenant = Depends(get_current_tenant),
):
    """Printable & Downloadable Indian Salary Payslip View."""
    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    current_employee = get_current_employee_session(request, db)

    payslip = db.query(PayrollPayslip).filter(PayrollPayslip.id == payslip_id).first()
    if not payslip:
        return HTMLResponse("<h2>Payslip not found</h2>", status_code=404)

    target_tenant = payslip.tenant or current_tenant

    if current_employee:
        if current_employee.id != payslip.student_id or current_employee.tenant_id != payslip.tenant_id:
            return HTMLResponse("<div style='padding:40px;font-family:sans-serif;text-align:center;'><h2>403 Forbidden</h2><p>You do not have permission to view this employee payslip.</p></div>", status_code=403)
        is_employee_portal = True
        employee_dashboard_url = f"/employee/{target_tenant.slug}/dashboard#wages"
    else:
        if current_user and current_user.role != "SUPER_ADMIN" and current_user.tenant_id != payslip.tenant_id:
            return HTMLResponse("<div style='padding:40px;font-family:sans-serif;text-align:center;'><h2>403 Forbidden</h2><p>You do not have permission to view payslips from another organization.</p></div>", status_code=403)
        is_employee_portal = False
        employee_dashboard_url = None

    branding = get_branding_dict(db, target_tenant.id)
    payslip_data = payslip.to_dict()
    net_in_words = number_to_words_inr(payslip.net_salary)

    breakdown = payslip_data.get("breakdown") or {}
    params = breakdown.get("parameters")
    if not params:
        emp = payslip.student
        active_st = None
        if emp and emp.salary_structures:
            active_st = next((s for s in emp.salary_structures if s.is_current), emp.salary_structures[0])
        tpl = (active_st.template if active_st else None) or payslip.template or (emp.designation_rel.salary_template if emp and emp.designation_rel else None)
        
        cal_days = max(1, payslip.calendar_days or 30)
        work_days = max(1.0, float(payslip.working_days or 26.0))
        comp_model = (active_st.compensation_model if active_st else None) or (tpl.compensation_model if tpl else "STRUCTURED_SALARY")
        tpl_name = tpl.name if tpl else "Standard Structure"
        tpl_code = tpl.code if tpl else comp_model

        is_hourly_model = (comp_model == "HOURLY" or "HOURLY" in str(tpl_code).upper() or "HOURLY" in str(tpl_name).upper())
        is_daily_model = (comp_model == "DAILY_WAGE" or "DAILY" in str(tpl_code).upper() or "DAILY" in str(tpl_name).upper())

        if is_hourly_model or is_daily_model:
            m_basic = float(active_st.monthly_basic) if (active_st and active_st.monthly_basic) else 0.0
        else:
            m_basic = float(active_st.monthly_basic if active_st and active_st.monthly_basic else (payslip.basic_earned if payslip.basic_earned > 0 else (emp.monthly_base_salary or 0.0) if emp else 0.0))

        m_gross = float(active_st.monthly_gross if active_st and active_st.monthly_gross else (0.0 if (is_hourly_model or is_daily_model) else (payslip.gross_earnings or (m_basic * 1.5 if m_basic else 0.0))))

        m_da = float(active_st.monthly_da if active_st else (payslip.da_earned or 0.0))
        m_hra = float(active_st.monthly_hra if active_st else (payslip.hra_earned or 0.0))

        da_pct = float(tpl.da_percentage) if tpl and tpl.da_percentage is not None else (
            round((m_da / m_basic * 100.0), 1) if m_basic > 0 and m_da > 0 else 0.0
        )
        hra_pct = float(tpl.hra_percentage) if tpl and tpl.hra_percentage is not None else (
            round((m_hra / m_basic * 100.0), 1) if m_basic > 0 and m_hra > 0 else 0.0
        )

        if is_hourly_model:
            daily_salary = 0.0
        elif is_daily_model:
            daily_salary = float(active_st.daily_rate if active_st and active_st.daily_rate else ((emp.daily_rate or 0.0) if emp else 0.0))
        else:
            daily_salary = round(float(active_st.daily_rate if active_st and active_st.daily_rate else (m_gross / (cal_days if comp_model == 'STRUCTURED_SALARY' else work_days))), 2)

        params = {
            "compensation_model": comp_model,
            "template_name": tpl.name if tpl else "Standard Structure",
            "template_code": tpl.code if tpl else comp_model,
            "monthly_basic": m_basic,
            "monthly_da": m_da,
            "monthly_hra": m_hra,
            "da_percentage": da_pct,
            "hra_percentage": hra_pct,
            "daily_salary_rate": daily_salary,
            "hourly_rate": float(active_st.hourly_rate if active_st else (emp.hourly_rate or 0.0) if emp else 0.0),
            "monthly_gross": m_gross,
            "annual_ctc": float(active_st.annual_ctc if active_st else (m_gross * 12.0)),
            "conveyance_allowance": float(active_st.conveyance_allowance if active_st else (tpl.conveyance_fixed if tpl else payslip.conveyance_earned or 0.0)),
            "medical_allowance": float(active_st.medical_allowance if active_st else (tpl.medical_fixed if tpl else payslip.medical_earned or 0.0)),
            "special_allowance": float(active_st.special_allowance if active_st else (payslip.special_allowance_earned or 0.0)),
            "other_allowances": float(active_st.other_allowances if active_st else (payslip.other_earnings or 0.0)),
            "enable_pf": bool(active_st.enable_pf if active_st else (payslip.epf_employee > 0 or (tpl.enable_pf if tpl else True))),
            "enable_esi": bool(active_st.enable_esi if active_st else (payslip.esic_employee > 0 or (tpl.enable_esi if tpl else True))),
            "enable_pt": bool(active_st.enable_pt if active_st else (payslip.professional_tax > 0 or (tpl.enable_pt if tpl else True))),
        }
    payslip_data["parameters"] = params

    return render_template(
        request,
        "payslip_view.html",
        {
            "page_title": f"Payslip - {payslip.student.name if payslip.student else 'Employee'} ({payslip_data.get('period_label')})",
            "branding": branding,
            "current_tenant": target_tenant.to_dict(),
            "target_tenant": target_tenant.to_dict(),
            "payslip": payslip_data,
            "employee": payslip.student.to_dict() if payslip.student else {},
            "net_in_words": net_in_words,
            "current_user": current_user.to_dict() if current_user else None,
            "current_employee": current_employee.to_dict() if current_employee else None,
            "is_employee_portal": is_employee_portal,
            "employee_dashboard_url": employee_dashboard_url,
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
    
    if not current_user or current_user.role != "SUPER_ADMIN":
        return RedirectResponse("/super-admin/login?next=/super-admin", status_code=303)

    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)

    return render_template(
        request,
        "super_admin.html",
        {
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
    emp_redirect = check_employee_portal_redirect(request, db)
    if emp_redirect:
        return emp_redirect

    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    
    if current_user and current_user.role == "SUPER_ADMIN":
        return RedirectResponse("/super-admin", status_code=303)

    is_corporate = bool(current_tenant.tenant_type == "corporate")
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
    page_title = "Departments" if is_corporate else "Academic Management & Progression"

    return render_template(
        request,
        "academic_management.html",
        {
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
    emp_redirect = check_employee_portal_redirect(request, db)
    if emp_redirect:
        return emp_redirect

    current_tenant, current_user = resolve_scoped_tenant_and_user(request, db, fallback_tenant)
    branding = get_branding_dict(db, current_tenant.id)
    all_tenants = get_all_active_tenants(db)
    classes = db.query(ClassModel).filter(ClassModel.tenant_id == current_tenant.id).all()

    return render_template(
        request,
        "teacher_portal.html",
        {
            "page_title": "Faculty Classroom Workspace",
            "active_page": "teacher-portal",
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": all_tenants,
            "classes": [c.to_dict() for c in classes],
            "current_user": current_user.to_dict() if current_user else None,
        },
    )


@router.get("/leave-management", response_class=HTMLResponse)
def page_leave_management(
    request: Request,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Tenant Admin Leave Review, Quotas Master, and Approval Dashboard."""
    emp_redirect = check_employee_portal_redirect(request, db)
    if emp_redirect:
        return emp_redirect

    current_user = get_current_user_optional(request, db)
    if not current_user:
        return RedirectResponse(url=f"/portal/{current_tenant.slug}", status_code=303)

    if current_user.role not in ["SUPER_ADMIN", "TENANT_ADMIN"]:
        return RedirectResponse(url="/", status_code=303)

    # Modular SaaS Edition Protection (Smart and Pro)
    if not current_tenant.has_leave_module and current_user.role != "SUPER_ADMIN":
        return RedirectResponse(
            url="/?notice=The+Leave+Management+module+is+available+on+Smart+and+Pro+editions.+Please+contact+your+Super+Admin+to+upgrade.",
            status_code=303,
        )

    seed_default_leave_types(db, current_tenant.id)
    db.commit()

    branding = get_branding_dict(db, current_tenant.id)
    departments = db.query(Department).filter(Department.tenant_id == current_tenant.id).order_by(Department.name.asc()).all()
    leave_types = db.query(LeaveType).filter(LeaveType.tenant_id == current_tenant.id, LeaveType.is_active == True).order_by(LeaveType.id.asc()).all()

    return render_template(
        request,
        "leave_management.html",
        {
            "page_title": "Leave Management & Approvals",
            "active_page": "leave-management",
            "branding": branding,
            "current_tenant": current_tenant.to_dict(),
            "all_tenants": get_all_active_tenants(db) if current_user.role == "SUPER_ADMIN" else [],
            "current_user": current_user.to_dict(),
            "departments": [d.to_dict() for d in departments],
            "leave_types": [lt.to_dict() for lt in leave_types],
        },
    )
