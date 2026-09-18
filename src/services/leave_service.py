"""
Leave Service
Handles leave master configuration, quota deduction, balance tracking,
and multi-tier approval/rejection workflows.
"""

import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any
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

logger = logging.getLogger("leave_service")


class LeaveService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_leave_balance(
        self,
        tenant_id: int,
        student: Student,
        leave_type: LeaveType,
        year: int,
    ) -> LeaveBalance:
        balance = (
            self.db.query(LeaveBalance)
            .filter(
                LeaveBalance.tenant_id == tenant_id,
                LeaveBalance.student_id == student.id,
                LeaveBalance.leave_type_id == leave_type.id,
                LeaveBalance.year == year,
            )
            .first()
        )

        if not balance:
            allocated = float(leave_type.default_days_per_year or 0.0)
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
            self.db.add(balance)
            self.db.flush()

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

        current_year = req.start_date.year if req.start_date else get_ist_now().year
        balance = self.get_or_create_leave_balance(tenant_id, student, leave_type, current_year)

        req.status = decision
        req.reviewer_user_id = current_user.id if current_user else None
        req.reviewer_name = current_user.username if current_user else "Admin"
        req.reviewed_at = get_ist_now()
        req.admin_remarks = admin_remarks

        days_count = float(req.total_days or 1.0)
        balance.pending_days = max(0.0, balance.pending_days - days_count)

        if decision == "APPROVED":
            balance.used_days += days_count
            balance.remaining_days = max(0.0, balance.total_allocated - balance.used_days)
        elif decision == "REJECTED":
            balance.remaining_days = max(0.0, balance.total_allocated - balance.used_days)

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
