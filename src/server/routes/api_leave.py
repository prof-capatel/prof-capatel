import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from src.database.models import (
    Tenant,
    Student,
    LeaveType,
    LeaveBalance,
    LeaveRequest,
    Department,
    User,
    AuditLog,
)
from src.database.session import get_db, seed_default_leave_types
from src.server.tenant_middleware import get_current_tenant
from src.server.rbac_middleware import check_tenant_operational_access, check_tenant_leave_access, get_current_user_optional
from src.utils.timezone import get_ist_now
from src.services.leave_service import LeaveService
from src.utils.financial_year import (
    get_financial_year_info,
    parse_financial_year_code,
    list_tenant_financial_years,
)

logger = logging.getLogger("api_leave")

router = APIRouter(prefix="/api/v1/leave", tags=["Leave Management Master & Approval"])


class LeaveTypePayload(BaseModel):
    id: Optional[int] = None
    name: str
    code: str
    description: Optional[str] = ""
    is_paid: Optional[bool] = True
    default_days_per_year: Optional[float] = 12.0
    accrual_frequency: Optional[str] = "ANNUAL"
    requires_document: Optional[bool] = False
    allow_carry_forward: Optional[bool] = False
    max_carry_forward_days: Optional[float] = 0.0
    lapse_policy: Optional[str] = "LAPSE_EXCESS"
    is_active: Optional[bool] = True


class LeaveReviewPayload(BaseModel):
    status: str  # APPROVED, REJECTED
    admin_remarks: Optional[str] = ""


class FinancialYearConfigPayload(BaseModel):
    start_month: int  # 1 = Jan, 4 = Apr, 7 = Jul


def get_or_create_leave_balance(
    db: Session,
    tenant_id: int,
    student: Student,
    leave_type: LeaveType,
    year: Optional[int] = None,
    financial_year: Optional[str] = None,
    target_date: Optional[Union[date, datetime, str]] = None,
) -> LeaveBalance:
    """
    Retrieves or automatically initializes an employee's annual leave balance from default quota
    and carry-forward rollover rules per Financial Year.
    """
    service = LeaveService(db)
    return service.get_or_create_leave_balance(
        tenant_id=tenant_id,
        student=student,
        leave_type=leave_type,
        year=year,
        financial_year=financial_year,
        target_date=target_date,
    )


@router.get("/financial-years")
def get_tenant_financial_years(
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Returns available financial years and active financial year for dropdown filters."""
    start_m = current_tenant.financial_year_start_month or 4
    years = list_tenant_financial_years(start_month=start_m, count_past=3, count_future=1)
    curr_fy = get_financial_year_info(get_ist_now(), start_month=start_m)
    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "start_month": start_m,
        "current_financial_year": curr_fy,
        "available_financial_years": years,
    }


@router.put("/settings/financial-year")
def update_financial_year_setting(
    payload: FinancialYearConfigPayload,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Allows tenant admin to customize their organization's Financial Year start month (e.g. 4 for Apr, 1 for Jan)."""
    check_tenant_leave_access(current_tenant)
    check_tenant_operational_access(current_tenant)
    if payload.start_month not in range(1, 13):
        raise HTTPException(status_code=400, detail="Financial Year start month must be between 1 and 12.")

    current_tenant.financial_year_start_month = payload.start_month
    db.commit()
    fy_info = get_financial_year_info(get_ist_now(), start_month=payload.start_month)
    return {
        "status": "success",
        "message": f"Financial year start month updated to month {payload.start_month}.",
        "financial_year_start_month": payload.start_month,
        "current_financial_year": fy_info,
    }


@router.get("/types")
def list_leave_types(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Lists all configured leave categories for the tenant."""
    check_tenant_leave_access(current_tenant)
    service = LeaveService(db)
    types = service.list_leave_types(current_tenant.id, include_inactive)
    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "leave_types": types,
        "count": len(types),
    }


@router.post("/types")
def save_leave_type(
    payload: LeaveTypePayload,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Creates or updates a leave type."""
    check_tenant_leave_access(current_tenant)
    check_tenant_operational_access(current_tenant)
    service = LeaveService(db)
    res = service.upsert_leave_type(current_tenant.id, payload)
    lt_data = res.get("data", {})
    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "message": f"Leave category '{lt_data.get('name')}' ({lt_data.get('code')}) saved successfully.",
        "leave_type": lt_data,
    }


@router.delete("/types/{type_id}")
def delete_leave_type(
    type_id: int,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Soft-deactivates a leave type category."""
    check_tenant_leave_access(current_tenant)
    check_tenant_operational_access(current_tenant)
    service = LeaveService(db)
    return service.delete_leave_type(current_tenant.id, type_id)


@router.get("/requests")
def list_leave_requests(
    status: Optional[str] = None,
    department_id: Optional[int] = None,
    student_id: Optional[int] = None,
    financial_year: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Lists leave applications for administrative review with multi-parameter filtering."""
    check_tenant_leave_access(current_tenant)
    start_m = current_tenant.financial_year_start_month or 4
    if financial_year:
        fy_info = parse_financial_year_code(financial_year, start_month=start_m)
    else:
        fy_info = get_financial_year_info(get_ist_now(), start_month=start_m)

    query = (
        db.query(LeaveRequest)
        .join(Student, LeaveRequest.student_id == Student.id)
        .filter(LeaveRequest.tenant_id == current_tenant.id)
    )

    if status and status.strip().upper() != "ALL":
        query = query.filter(LeaveRequest.status == status.strip().upper())
    if department_id:
        query = query.filter(Student.department_id == department_id)
    if student_id:
        query = query.filter(LeaveRequest.student_id == student_id)
    if financial_year:
        query = query.filter(
            or_(
                LeaveRequest.financial_year == fy_info["fy_code"],
                and_(
                    LeaveRequest.start_date >= fy_info["start_date"],
                    LeaveRequest.start_date <= fy_info["end_date"],
                ),
            )
        )
    if start_date:
        try:
            s_d = datetime.strptime(start_date.strip()[:10], "%Y-%m-%d").date()
            query = query.filter(LeaveRequest.end_date >= s_d)
        except ValueError:
            pass
    if end_date:
        try:
            e_d = datetime.strptime(end_date.strip()[:10], "%Y-%m-%d").date()
            query = query.filter(LeaveRequest.start_date <= e_d)
        except ValueError:
            pass

    requests = query.order_by(LeaveRequest.created_at.desc()).limit(limit).all()

    # Pre-fetch current leave balances for all unique students in results for the active FY
    student_ids = list({r.student_id for r in requests})
    balances_by_student: Dict[int, List[dict]] = {}
    if student_ids:
        b_list = (
            db.query(LeaveBalance)
            .filter(
                LeaveBalance.tenant_id == current_tenant.id,
                LeaveBalance.student_id.in_(student_ids),
                or_(
                    LeaveBalance.financial_year == fy_info["fy_code"],
                    LeaveBalance.year == fy_info["start_year"],
                ),
            )
            .all()
        )
        for b in b_list:
            balances_by_student.setdefault(b.student_id, []).append(b.to_dict())

    results = []
    for req in requests:
        d = req.to_dict()
        d["current_balances"] = balances_by_student.get(req.student_id, [])
        results.append(d)

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "financial_year": fy_info["fy_code"],
        "financial_year_label": fy_info["fy_label"],
        "requests": results,
        "count": len(results),
    }


@router.post("/requests/{request_id}/review")
def review_leave_request(
    request_id: int,
    payload: LeaveReviewPayload,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Approves or rejects a pending employee leave request.
    Automatically updates the employee's LeaveBalance using FIFO deduction:
    Carried-forward leaves are consumed first before newly allocated annual quota.
    """
    check_tenant_leave_access(current_tenant)
    check_tenant_operational_access(current_tenant)
    req = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.id == request_id, LeaveRequest.tenant_id == current_tenant.id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Leave request not found.")

    if req.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot review this request: it is already in '{req.status}' status.",
        )

    action_status = payload.status.strip().upper()
    if action_status not in ["APPROVED", "REJECTED"]:
        raise HTTPException(status_code=400, detail="Status must be 'APPROVED' or 'REJECTED'.")

    now_ist = get_ist_now()
    req_date = req.start_date if req.start_date else now_ist.date()
    start_m = current_tenant.financial_year_start_month or 4
    fy_info = get_financial_year_info(req_date, start_month=start_m)

    # Synchronize balance
    student = db.query(Student).filter(Student.id == req.student_id).first()
    leave_type = db.query(LeaveType).filter(LeaveType.id == req.leave_type_id).first()

    balance = None
    if student and leave_type:
        balance = get_or_create_leave_balance(
            db,
            current_tenant.id,
            student,
            leave_type,
            year=fy_info["start_year"],
            financial_year=fy_info["fy_code"],
        )

        # Release the pending days from balance
        balance.pending_days = max(0.0, round(balance.pending_days - req.total_days, 2))

        if action_status == "APPROVED":
            # FIFO: Deduct carried-forward leaves first before consuming new annual quota
            cf_avail = max(0.0, float(balance.carried_forward_days or 0.0) - float(balance.carried_forward_used or 0.0))
            cf_deduct = min(req.total_days, cf_avail)
            balance.carried_forward_used = round(float(balance.carried_forward_used or 0.0) + cf_deduct, 2)
            balance.used_days = round(float(balance.used_days or 0.0) + req.total_days, 2)
            balance.remaining_days = max(0.0, round(balance.total_allocated - balance.used_days - balance.pending_days, 2))
        else:  # REJECTED
            balance.remaining_days = max(0.0, round(balance.total_allocated - balance.used_days - balance.pending_days, 2))

        balance.updated_at = now_ist

    req.status = action_status
    req.financial_year = fy_info["fy_code"]
    req.reviewed_by_user_id = current_user.id if current_user else None
    req.reviewed_at = now_ist
    req.admin_remarks = payload.admin_remarks.strip() if payload.admin_remarks else ""

    # Log Audit
    audit = AuditLog(
        tenant_id=current_tenant.id,
        user_id=current_user.id if current_user else None,
        actor_name=current_user.full_name if current_user else "Admin",
        actor_role=current_user.role if current_user else "TENANT_ADMIN",
        action_type=f"LEAVE_{action_status}",
        target_type="LEAVE_REQUEST",
        target_id=str(req.id),
        description=f"{action_status.capitalize()} leave for '{student.name if student else 'Employee'}' ({req.total_days} days of {leave_type.name if leave_type else 'Leave'} in {fy_info['fy_label']}). Remarks: {req.admin_remarks}",
    )
    db.add(audit)
    db.commit()
    db.refresh(req)

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "message": f"Leave request for '{student.name if student else 'Employee'}' has been {action_status.lower()}.",
        "request": req.to_dict(),
        "updated_balance": balance.to_dict() if balance else None,
    }


@router.get("/balances")
def list_employee_balances(
    student_id: Optional[int] = None,
    department_id: Optional[int] = None,
    year: Optional[int] = None,
    financial_year: Optional[str] = None,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Lists current leave balances across all employees or a specific employee for a Financial Year."""
    check_tenant_leave_access(current_tenant)
    start_m = current_tenant.financial_year_start_month or 4
    if financial_year:
        fy_info = parse_financial_year_code(financial_year, start_month=start_m)
    elif year:
        fy_info = parse_financial_year_code(year, start_month=start_m)
    else:
        fy_info = get_financial_year_info(get_ist_now(), start_month=start_m)

    target_year = fy_info["start_year"]
    query = (
        db.query(LeaveBalance)
        .join(Student, LeaveBalance.student_id == Student.id)
        .filter(
            LeaveBalance.tenant_id == current_tenant.id,
            or_(
                LeaveBalance.financial_year == fy_info["fy_code"],
                LeaveBalance.year == target_year,
            ),
        )
    )

    if student_id:
        query = query.filter(LeaveBalance.student_id == student_id)
    if department_id:
        query = query.filter(Student.department_id == department_id)

    balances = query.order_by(Student.name.asc()).all()
    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "year": target_year,
        "financial_year": fy_info["fy_code"],
        "financial_year_label": fy_info["fy_label"],
        "balances": [b.to_dict() for b in balances],
        "count": len(balances),
    }


@router.get("/balances/{student_id}")
def get_single_employee_leave_balances(
    student_id: int,
    year: Optional[int] = None,
    financial_year: Optional[str] = None,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Retrieves all active leave balances for a specific employee, auto-initializing balances if not yet created."""
    check_tenant_leave_access(current_tenant)
    start_m = current_tenant.financial_year_start_month or 4
    if financial_year:
        fy_info = parse_financial_year_code(financial_year, start_month=start_m)
    elif year:
        fy_info = parse_financial_year_code(year, start_month=start_m)
    else:
        fy_info = get_financial_year_info(get_ist_now(), start_month=start_m)

    student = db.query(Student).filter(Student.id == student_id, Student.tenant_id == current_tenant.id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Employee record not found.")

    leave_types = db.query(LeaveType).filter(LeaveType.tenant_id == current_tenant.id, LeaveType.is_active == True).all()
    balances = []
    for lt in leave_types:
        bal = get_or_create_leave_balance(
            db,
            current_tenant.id,
            student,
            lt,
            year=fy_info["start_year"],
            financial_year=fy_info["fy_code"],
        )
        balances.append(bal)
    db.commit()

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "student_id": student.id,
        "student_name": student.name,
        "year": fy_info["start_year"],
        "financial_year": fy_info["fy_code"],
        "financial_year_label": fy_info["fy_label"],
        "balances": [b.to_dict() for b in balances],
    }


@router.post("/balances/transition-fy")
def trigger_fy_transition(
    financial_year: Optional[str] = None,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Administrative trigger to initialize or rollover FY balances and carry-forward allocations
    for all active employees in the organization.
    """
    check_tenant_leave_access(current_tenant)
    check_tenant_operational_access(current_tenant)
    service = LeaveService(db)
    result = service.transition_tenant_leave_balances(current_tenant.id, target_fy=financial_year)
    return result


@router.get("/summary-stats")
def get_leave_summary_stats(
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Returns 4 dashboard KPI metrics for the corporate leave management portal per current FY."""
    check_tenant_leave_access(current_tenant)
    today = get_ist_now().date()
    start_month = today.replace(day=1)
    start_m = current_tenant.financial_year_start_month or 4
    curr_fy = get_financial_year_info(today, start_month=start_m)

    pending_count = (
        db.query(func.count(LeaveRequest.id))
        .filter(
            LeaveRequest.tenant_id == current_tenant.id,
            LeaveRequest.status == "PENDING",
        )
        .scalar() or 0
    )

    approved_this_month = (
        db.query(func.count(LeaveRequest.id))
        .filter(
            LeaveRequest.tenant_id == current_tenant.id,
            LeaveRequest.status == "APPROVED",
            LeaveRequest.start_date >= start_month,
        )
        .scalar() or 0
    )

    on_leave_today = (
        db.query(func.count(LeaveRequest.id))
        .filter(
            LeaveRequest.tenant_id == current_tenant.id,
            LeaveRequest.status == "APPROVED",
            LeaveRequest.start_date <= today,
            LeaveRequest.end_date >= today,
        )
        .scalar() or 0
    )

    total_days_used_this_year = (
        db.query(func.sum(LeaveBalance.used_days))
        .filter(
            LeaveBalance.tenant_id == current_tenant.id,
            or_(
                LeaveBalance.financial_year == curr_fy["fy_code"],
                LeaveBalance.year == curr_fy["start_year"],
            ),
        )
        .scalar() or 0.0
    )

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "financial_year": curr_fy["fy_code"],
        "financial_year_label": curr_fy["fy_label"],
        "pending_requests_count": pending_count,
        "approved_this_month_count": approved_this_month,
        "on_leave_today_count": on_leave_today,
        "total_leave_days_taken_year": round(float(total_days_used_this_year), 1),
    }
