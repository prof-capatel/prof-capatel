"""
Leave Service
Handles leave master configuration, quota deduction, balance tracking,
financial year cycles, carry-forward rollover rules, and multi-tier approval workflows.
"""

import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

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
from src.database.session import seed_default_leave_types
from src.utils.timezone import get_ist_now
from src.utils.financial_year import (
    get_financial_year_info,
    parse_financial_year_code,
    list_tenant_financial_years,
)

logger = logging.getLogger("leave_service")


class LeaveService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_leave_balance(
        self,
        tenant_id: int,
        student: Student,
        leave_type: LeaveType,
        year: Optional[int] = None,
        financial_year: Optional[str] = None,
        target_date: Optional[Union[date, datetime, str]] = None,
    ) -> LeaveBalance:
        """
        Retrieves or initializes an employee's leave balance for a given Financial Year (FY).
        Automatically computes carry-forward rollover from the previous FY:
          - If carry-forward is enabled: rolls over unutilized days up to max_carry_forward_days (or unlimited if 0).
          - Lapses remaining excess days.
          - Allocates new FY annual quota.
        """
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        start_month = tenant.financial_year_start_month if (tenant and tenant.financial_year_start_month) else 4

        if financial_year:
            fy_info = parse_financial_year_code(financial_year, start_month=start_month)
        elif year:
            fy_info = parse_financial_year_code(year, start_month=start_month)
        elif target_date:
            fy_info = get_financial_year_info(target_date, start_month=start_month)
        else:
            fy_info = get_financial_year_info(get_ist_now(), start_month=start_month)

        fy_start_year = fy_info["start_year"]
        fy_code = fy_info["fy_code"]

        # 1. Lookup existing balance for (tenant, student, leave_type, year)
        balance = (
            self.db.query(LeaveBalance)
            .filter(
                LeaveBalance.tenant_id == tenant_id,
                LeaveBalance.student_id == student.id,
                LeaveBalance.leave_type_id == leave_type.id,
                LeaveBalance.year == fy_start_year,
            )
            .first()
        )

        if balance:
            # Sync financial_year string or annual_quota if legacy row
            changed = False
            if not balance.financial_year or balance.financial_year != fy_code:
                balance.financial_year = fy_code
                changed = True
            if (balance.annual_quota is None or balance.annual_quota == 0.0) and balance.total_allocated > 0.0:
                balance.annual_quota = max(0.0, balance.total_allocated - (balance.carried_forward_days or 0.0))
                changed = True
            if changed:
                self.db.flush()
            return balance

        # 2. Balance does not exist: Initialize with Carry-Forward Rollover from previous FY
        prev_start_year = fy_start_year - 1
        prev_balance = (
            self.db.query(LeaveBalance)
            .filter(
                LeaveBalance.tenant_id == tenant_id,
                LeaveBalance.student_id == student.id,
                LeaveBalance.leave_type_id == leave_type.id,
                LeaveBalance.year == prev_start_year,
            )
            .first()
        )

        annual_quota = float(leave_type.default_days_per_year or 0.0)
        cf_days = 0.0
        lapsed_days = 0.0

        if prev_balance:
            unutilized = max(0.0, float(prev_balance.remaining_days or 0.0))
            if leave_type.allow_carry_forward and unutilized > 0.0:
                max_cf = float(leave_type.max_carry_forward_days or 0.0)
                if max_cf > 0.0:
                    cf_days = min(unutilized, max_cf)
                    lapsed_days = max(0.0, unutilized - cf_days)
                else:
                    # 0 or None means unlimited carry-forward
                    cf_days = unutilized
                    lapsed_days = 0.0
            else:
                cf_days = 0.0
                lapsed_days = unutilized

        total_allocated = round(annual_quota + cf_days, 2)
        remaining_days = total_allocated

        balance = LeaveBalance(
            tenant_id=tenant_id,
            student_id=student.id,
            leave_type_id=leave_type.id,
            year=fy_start_year,
            financial_year=fy_code,
            annual_quota=annual_quota,
            carried_forward_days=round(cf_days, 2),
            carried_forward_used=0.0,
            lapsed_days=round(lapsed_days, 2),
            total_allocated=total_allocated,
            used_days=0.0,
            pending_days=0.0,
            remaining_days=remaining_days,
        )
        self.db.add(balance)
        self.db.flush()

        logger.info(
            f"Initialized LeaveBalance for Student #{student.id} [{leave_type.code}] in {fy_code}: "
            f"Quota={annual_quota}, CarriedForward={cf_days}, Lapsed={lapsed_days}, Total={total_allocated}"
        )
        return balance

    def list_leave_types(self, tenant_id: int, include_inactive: bool = False) -> List[Dict[str, Any]]:
        seed_default_leave_types(self.db, tenant_id)
        self.db.commit()

        query = self.db.query(LeaveType).filter(LeaveType.tenant_id == tenant_id)
        if not include_inactive:
            query = query.filter(LeaveType.is_active == True)

        types = query.order_by(LeaveType.id.asc()).all()
        return [t.to_dict() for t in types]

    def upsert_leave_type(self, tenant_id: int, payload: Any) -> Dict[str, Any]:
        code = payload.code.strip().upper()
        name = payload.name.strip()

        if payload.id:
            leave_type = (
                self.db.query(LeaveType)
                .filter(LeaveType.id == payload.id, LeaveType.tenant_id == tenant_id)
                .first()
            )
            if not leave_type:
                raise HTTPException(status_code=404, detail="Leave type not found.")
        else:
            existing = (
                self.db.query(LeaveType)
                .filter(LeaveType.tenant_id == tenant_id, LeaveType.code == code)
                .first()
            )
            if existing:
                raise HTTPException(status_code=400, detail=f"Leave type code '{code}' already exists.")

            leave_type = LeaveType(tenant_id=tenant_id, code=code)
            self.db.add(leave_type)

        leave_type.name = name
        leave_type.description = payload.description or ""
        leave_type.is_paid = payload.is_paid if payload.is_paid is not None else True
        leave_type.default_days_per_year = float(payload.default_days_per_year or 0.0)
        leave_type.accrual_frequency = payload.accrual_frequency or "ANNUAL"
        leave_type.requires_document = bool(payload.requires_document)
        leave_type.allow_carry_forward = bool(getattr(payload, "allow_carry_forward", False))
        max_cf = getattr(payload, "max_carry_forward_days", 0.0)
        leave_type.max_carry_forward_days = float(max_cf) if max_cf is not None else 0.0
        leave_type.lapse_policy = getattr(payload, "lapse_policy", "LAPSE_EXCESS") or "LAPSE_EXCESS"
        leave_type.is_active = payload.is_active if payload.is_active is not None else True

        self.db.commit()
        self.db.refresh(leave_type)

        return {"status": "success", "data": leave_type.to_dict()}

    def delete_leave_type(self, tenant_id: int, type_id: int) -> Dict[str, Any]:
        leave_type = (
            self.db.query(LeaveType)
            .filter(LeaveType.id == type_id, LeaveType.tenant_id == tenant_id)
            .first()
        )
        if not leave_type:
            raise HTTPException(status_code=404, detail="Leave type not found.")

        # Deactivate rather than delete to preserve historic balances
        leave_type.is_active = False
        self.db.commit()
        return {"status": "success", "message": f"Leave category '{leave_type.name}' archived."}

    def review_leave_request(
        self,
        tenant_id: int,
        request_id: int,
        status_decision: str,
        admin_remarks: Optional[str] = "",
        current_user: Optional[User] = None,
    ) -> Dict[str, Any]:
        req = (
            self.db.query(LeaveRequest)
            .filter(LeaveRequest.id == request_id, LeaveRequest.tenant_id == tenant_id)
            .first()
        )
        if not req:
            raise HTTPException(status_code=404, detail="Leave request application not found.")

        if req.status not in ("PENDING", "SUBMITTED"):
            raise HTTPException(
                status_code=400,
                detail=f"This application has already been decided with status: {req.status}.",
            )

        student = self.db.query(Student).filter(Student.id == req.student_id).first()
        leave_type = self.db.query(LeaveType).filter(LeaveType.id == req.leave_type_id).first()

        decision = status_decision.strip().upper()
        if decision not in ("APPROVED", "REJECTED"):
            raise HTTPException(status_code=400, detail="Invalid decision. Must be APPROVED or REJECTED.")

        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        start_month = tenant.financial_year_start_month if (tenant and tenant.financial_year_start_month) else 4
        req_date = req.start_date if req.start_date else get_ist_now().date()
        fy_info = get_financial_year_info(req_date, start_month=start_month)

        balance = self.get_or_create_leave_balance(
            tenant_id,
            student,
            leave_type,
            year=fy_info["start_year"],
            financial_year=fy_info["fy_code"],
        )

        req.status = decision
        req.financial_year = fy_info["fy_code"]
        req.reviewed_by_user_id = current_user.id if current_user else None
        req.reviewer_name = current_user.username if current_user else "Admin"
        req.reviewed_at = get_ist_now()
        req.admin_remarks = admin_remarks

        days_count = float(req.total_days or 1.0)
        balance.pending_days = max(0.0, round(balance.pending_days - days_count, 2))

        if decision == "APPROVED":
            # FIFO: Deduct carried-forward leaves first before consuming new annual quota
            cf_available = max(0.0, float(balance.carried_forward_days or 0.0) - float(balance.carried_forward_used or 0.0))
            cf_deduction = min(days_count, cf_available)
            balance.carried_forward_used = round(float(balance.carried_forward_used or 0.0) + cf_deduction, 2)
            balance.used_days = round(float(balance.used_days or 0.0) + days_count, 2)
            balance.remaining_days = max(0.0, round(balance.total_allocated - balance.used_days - balance.pending_days, 2))
        elif decision == "REJECTED":
            balance.remaining_days = max(0.0, round(balance.total_allocated - balance.used_days - balance.pending_days, 2))

        log = AuditLog(
            tenant_id=tenant_id,
            user_id=current_user.id if current_user else None,
            event_type="LEAVE_DECISION",
            description=f"Leave application #{req.id} for {student.name} ({days_count} days) {decision}. Remarks: {admin_remarks}",
            created_at=get_ist_now(),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(req)

        return {
            "status": "success",
            "message": f"Leave application #{req.id} {decision} successfully.",
            "data": req.to_dict(),
        }

    def transition_tenant_leave_balances(
        self,
        tenant_id: int,
        target_fy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Transitions or pre-calculates FY leave balances and rollovers for all active employees for the target FY.
        """
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found.")

        start_month = tenant.financial_year_start_month or 4
        if target_fy:
            fy_info = parse_financial_year_code(target_fy, start_month=start_month)
        else:
            fy_info = get_financial_year_info(get_ist_now(), start_month=start_month)

        students = (
            self.db.query(Student)
            .filter(Student.tenant_id == tenant_id, Student.is_active == True)
            .all()
        )
        leave_types = (
            self.db.query(LeaveType)
            .filter(LeaveType.tenant_id == tenant_id, LeaveType.is_active == True)
            .all()
        )

        initialized_count = 0
        total_cf_days = 0.0
        total_lapsed_days = 0.0

        for student in students:
            for lt in leave_types:
                bal = self.get_or_create_leave_balance(
                    tenant_id=tenant_id,
                    student=student,
                    leave_type=lt,
                    year=fy_info["start_year"],
                    financial_year=fy_info["fy_code"],
                )
                initialized_count += 1
                total_cf_days += float(bal.carried_forward_days or 0.0)
                total_lapsed_days += float(bal.lapsed_days or 0.0)

        self.db.commit()
        return {
            "status": "success",
            "financial_year": fy_info["fy_code"],
            "financial_year_label": fy_info["fy_label"],
            "employees_processed": len(students),
            "balances_initialized": initialized_count,
            "total_carried_forward_days": round(total_cf_days, 2),
            "total_lapsed_days": round(total_lapsed_days, 2),
        }
