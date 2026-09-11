import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from src.database.models import (
    Tenant,
    Student,
    LeaveType,
    LeaveCadreQuota,
    LeaveBalance,
    LeaveRequest,
    Department,
    User,
    AuditLog,
)
from src.database.session import get_db, seed_default_leave_types
from src.server.tenant_middleware import get_current_tenant
from src.server.rbac_middleware import check_tenant_operational_access, get_current_user_optional
from src.utils.timezone import get_ist_now

logger = logging.getLogger("api_leave")

router = APIRouter(prefix="/api/v1/leave", tags=["Leave Management Master & Approval"])


class LeaveCadreQuotaItem(BaseModel):
    cadre_level: str
    allocated_days: float


class LeaveTypePayload(BaseModel):
    id: Optional[int] = None
    name: str
    code: str
    description: Optional[str] = ""
    is_paid: Optional[bool] = True
    default_days_per_year: Optional[float] = 12.0
    accrual_frequency: Optional[str] = "ANNUAL"
    requires_document: Optional[bool] = False
    is_active: Optional[bool] = True
    cadre_quotas: Optional[List[LeaveCadreQuotaItem]] = []


class LeaveReviewPayload(BaseModel):
    status: str  # APPROVED, REJECTED
    admin_remarks: Optional[str] = ""


def get_or_create_leave_balance(
    db: Session,
    tenant_id: int,
    student: Student,
    leave_type: LeaveType,
    year: int,
) -> LeaveBalance:
    """Retrieves or automatically initializes an employee's annual leave balance from default or cadre quota."""
    balance = (
        db.query(LeaveBalance)
        .filter(
            LeaveBalance.tenant_id == tenant_id,
            LeaveBalance.student_id == student.id,
            LeaveBalance.leave_type_id == leave_type.id,
            LeaveBalance.year == year,
        )
        .first()
    )

    if not balance:
        # Check cadre-specific quota override
        allocated = float(leave_type.default_days_per_year or 0.0)
        if student.cadre_level:
            cadre_q = (
                db.query(LeaveCadreQuota)
                .filter(
                    LeaveCadreQuota.tenant_id == tenant_id,
                    LeaveCadreQuota.leave_type_id == leave_type.id,
                    LeaveCadreQuota.cadre_level == student.cadre_level.strip(),
                )
                .first()
            )
            if cadre_q:
                allocated = float(cadre_q.allocated_days)

        balance = LeaveBalance(
            tenant_id=tenant_id,
            student_id=student.id,
            leave_type_id=leave_type.id,
            year=year,
            total_allocated=allocated,
            used_days=0.0,
            pending_days=0.0,
            remaining_days=allocated,
        )
        db.add(balance)
        db.flush()

    return balance


@router.get("/types")
def list_leave_types(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Lists all configured leave categories and cadre-specific quotas for the tenant."""
    # Ensure default types exist
    seed_default_leave_types(db, current_tenant.id)
    db.commit()

    query = db.query(LeaveType).filter(LeaveType.tenant_id == current_tenant.id)
    if not include_inactive:
        query = query.filter(LeaveType.is_active == True)

    types = query.order_by(LeaveType.id.asc()).all()
    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "leave_types": [lt.to_dict() for lt in types],
        "count": len(types),
    }


@router.post("/types")
def save_leave_type(
    payload: LeaveTypePayload,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Creates or updates a leave type and its role/cadre quota matrix."""
    check_tenant_operational_access(current_tenant)
    clean_code = payload.code.strip().upper()
    clean_name = payload.name.strip()

    if not clean_code or not clean_name:
        raise HTTPException(status_code=400, detail="Leave type name and code are required.")

    if payload.id:
        lt = db.query(LeaveType).filter(LeaveType.id == payload.id, LeaveType.tenant_id == current_tenant.id).first()
        if not lt:
            raise HTTPException(status_code=404, detail="Leave type not found.")
    else:
        # Check uniqueness of code
        existing = db.query(LeaveType).filter(LeaveType.tenant_id == current_tenant.id, LeaveType.code == clean_code).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Leave type with code '{clean_code}' already exists.")
        lt = LeaveType(tenant_id=current_tenant.id)
        db.add(lt)

    lt.name = clean_name
    lt.code = clean_code
    lt.description = payload.description.strip() if payload.description else ""
    lt.is_paid = bool(payload.is_paid)
    lt.default_days_per_year = float(payload.default_days_per_year if payload.default_days_per_year is not None else 12.0)
    lt.accrual_frequency = payload.accrual_frequency or "ANNUAL"
    lt.requires_document = bool(payload.requires_document)
    lt.is_active = bool(payload.is_active if payload.is_active is not None else True)
    db.flush()

    # Update cadre quotas
    if payload.cadre_quotas is not None:
        # Delete old quotas for this leave type
        db.query(LeaveCadreQuota).filter(LeaveCadreQuota.tenant_id == current_tenant.id, LeaveCadreQuota.leave_type_id == lt.id).delete()
        for cq in payload.cadre_quotas:
            if cq.cadre_level and cq.cadre_level.strip():
                new_cq = LeaveCadreQuota(
                    tenant_id=current_tenant.id,
                    leave_type_id=lt.id,
                    cadre_level=cq.cadre_level.strip(),
                    allocated_days=float(cq.allocated_days),
                )
                db.add(new_cq)

    db.commit()
    db.refresh(lt)

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "message": f"Leave category '{lt.name}' ({lt.code}) saved successfully.",
        "leave_type": lt.to_dict(),
    }


@router.delete("/types/{type_id}")
def delete_leave_type(
    type_id: int,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Soft-deactivates a leave type category."""
    check_tenant_operational_access(current_tenant)
    lt = db.query(LeaveType).filter(LeaveType.id == type_id, LeaveType.tenant_id == current_tenant.id).first()
    if not lt:
        raise HTTPException(status_code=404, detail="Leave type not found.")

    lt.is_active = False
    db.commit()
    return {
        "status": "success",
        "message": f"Leave type '{lt.name}' ({lt.code}) deactivated successfully.",
    }


@router.get("/requests")
def list_leave_requests(
    status: Optional[str] = None,
    department_id: Optional[int] = None,
    student_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Lists leave applications for administrative review with multi-parameter filtering."""
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

    # Pre-fetch current leave balances for all unique students in results
    student_ids = list({r.student_id for r in requests})
    current_year = get_ist_now().year
    balances_by_student: Dict[int, List[dict]] = {}
    if student_ids:
        b_list = (
            db.query(LeaveBalance)
            .filter(
                LeaveBalance.tenant_id == current_tenant.id,
                LeaveBalance.student_id.in_(student_ids),
                LeaveBalance.year == current_year,
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
    Automatically updates the employee's LeaveBalance (deducting used_days on approval, releasing pending_days).
    """
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
    req_year = req.start_date.year if req.start_date else now_ist.year

    # Synchronize balance
    student = db.query(Student).filter(Student.id == req.student_id).first()
    leave_type = db.query(LeaveType).filter(LeaveType.id == req.leave_type_id).first()

    balance = None
    if student and leave_type:
        balance = get_or_create_leave_balance(db, current_tenant.id, student, leave_type, req_year)

        # Release the pending days from balance
        balance.pending_days = max(0.0, balance.pending_days - req.total_days)

        if action_status == "APPROVED":
            balance.used_days += req.total_days
            balance.remaining_days = max(0.0, balance.total_allocated - balance.used_days - balance.pending_days)
        else:  # REJECTED
            balance.remaining_days = max(0.0, balance.total_allocated - balance.used_days - balance.pending_days)

        balance.updated_at = now_ist

    req.status = action_status
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
        description=f"{action_status.capitalize()} leave for '{student.name if student else 'Employee'}' ({req.total_days} days of {leave_type.name if leave_type else 'Leave'}). Remarks: {req.admin_remarks}",
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
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Lists current leave balances across all employees or a specific employee."""
    target_year = year or get_ist_now().year
    query = (
        db.query(LeaveBalance)
        .join(Student, LeaveBalance.student_id == Student.id)
        .filter(LeaveBalance.tenant_id == current_tenant.id, LeaveBalance.year == target_year)
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
        "balances": [b.to_dict() for b in balances],
        "count": len(balances),
    }


@router.get("/balances/{student_id}")
def get_single_employee_leave_balances(
    student_id: int,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Retrieves all active leave balances for a specific employee, auto-initializing balances if not yet created."""
    target_year = year or get_ist_now().year
    student = db.query(Student).filter(Student.id == student_id, Student.tenant_id == current_tenant.id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Employee record not found.")

    leave_types = db.query(LeaveType).filter(LeaveType.tenant_id == current_tenant.id, LeaveType.is_active == True).all()
    balances = []
    for lt in leave_types:
        bal = get_or_create_leave_balance(db, current_tenant.id, student, lt, target_year)
        balances.append(bal)
    db.commit()

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "student_id": student.id,
        "student_name": student.name,
        "year": target_year,
        "balances": [b.to_dict() for b in balances],
    }


@router.get("/summary-stats")
def get_leave_summary_stats(
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Returns 4 dashboard KPI metrics for the corporate leave management portal."""
    today = get_ist_now().date()
    start_month = today.replace(day=1)

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
            LeaveBalance.year == today.year,
        )
        .scalar() or 0.0
    )

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "pending_requests_count": pending_count,
        "approved_this_month_count": approved_this_month,
        "on_leave_today_count": on_leave_today,
        "total_leave_days_taken_year": round(float(total_days_used_this_year), 1),
    }
