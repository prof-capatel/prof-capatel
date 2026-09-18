"""
Attendance Service
Handles punch processing, shift reconciliation, manual overrides,
attendance logging, analytics aggregation, and export generation.
"""

import io
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
import pandas as pd
from sqlalchemy.orm import Session, joinedload
from openpyxl.styles import Font, PatternFill, Alignment
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

from src.database.models import (
    AttendanceRecord,
    Student,
    Tenant,
    SystemBranding,
    WorkShift,
    Department,
)
from src.utils.timezone import get_ist_now, get_ist_date

logger = logging.getLogger("attendance_service")


class AttendanceService:
    def __init__(self, db: Session):
        self.db = db

    def get_employee_punch_status(self, tenant_id: int, student_id: int) -> Dict[str, Any]:
        now = get_ist_now()
        today = now.date()
        start_today = datetime.combine(today, datetime.min.time())
        end_today = datetime.combine(today, datetime.max.time())

        student = (
            self.db.query(Student)
            .filter(Student.id == student_id, Student.tenant_id == tenant_id)
            .first()
        )
        if not student:
            raise HTTPException(status_code=404, detail="Student / Employee profile not found in this institution.")

        latest_rec = (
            self.db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.tenant_id == tenant_id,
                AttendanceRecord.student_id == student.id,
                AttendanceRecord.timestamp.between(start_today, end_today),
            )
            .order_by(AttendanceRecord.timestamp.desc())
            .first()
        )

        if not latest_rec:
            p_status = "NOT_CHECKED_IN"
            next_action = "CHECK_IN"
            check_in_time = None
            check_out_time = None
        elif latest_rec.check_in_time and not latest_rec.check_out_time:
            p_status = "CHECKED_IN"
            next_action = "CHECK_OUT"
            check_in_time = latest_rec.check_in_time.strftime("%I:%M %p")
            check_out_time = None
        else:
            p_status = "CHECKED_OUT"
            next_action = "CHECK_IN"
            check_in_time = latest_rec.check_in_time.strftime("%I:%M %p") if latest_rec.check_in_time else None
            check_out_time = latest_rec.check_out_time.strftime("%I:%M %p") if latest_rec.check_out_time else None

        return {
            "student_id": student.id,
            "name": student.name,
            "roll_number": student.roll_number,
            "department": student.department,
            "status": p_status,
            "next_action": next_action,
            "check_in_time": check_in_time,
            "check_out_time": check_out_time,
            "record": latest_rec.to_dict() if latest_rec else None,
        }

    def process_manual_override(self, tenant: Tenant, payload: Any) -> Dict[str, Any]:
        student = (
            self.db.query(Student)
            .filter(Student.id == payload.student_id, Student.tenant_id == tenant.id)
            .first()
        )
        if not student:
            raise HTTPException(status_code=404, detail="Student profile not found in this institution.")

        if not payload.reason or not payload.reason.strip():
            raise HTTPException(status_code=400, detail="An override justification reason is required.")

        log_time = get_ist_now()
        if payload.timestamp:
            try:
                clean_ts = payload.timestamp.replace("T", " ")
                if len(clean_ts) == 16:
                    clean_ts += ":00"
                log_time = datetime.strptime(clean_ts, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid timestamp format. Use YYYY-MM-DD HH:MM:SS.")

        is_corporate = (getattr(tenant, "tenant_type", "educational") == "corporate")
        branding = self.db.query(SystemBranding).filter(SystemBranding.tenant_id == tenant.id).first()

        today = log_time.date()
        start_today = datetime.combine(today, datetime.min.time())
        end_today = datetime.combine(today, datetime.max.time())

        requested_punch = (payload.punch_type or "AUTO").upper().strip()

        latest_today_rec = (
            self.db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.tenant_id == tenant.id,
                AttendanceRecord.student_id == student.id,
                AttendanceRecord.timestamp.between(start_today, end_today),
            )
            .order_by(AttendanceRecord.timestamp.desc())
            .first()
        )

        should_checkout = False
        if requested_punch == "CHECK_OUT":
            should_checkout = True
        elif requested_punch == "AUTO":
            if is_corporate and latest_today_rec and latest_today_rec.check_in_time and not latest_today_rec.check_out_time:
                should_checkout = True

        if should_checkout and is_corporate:
            if latest_today_rec and not latest_today_rec.check_out_time:
                record = latest_today_rec
                record.check_out_time = log_time
                record.punch_type = "CHECK_OUT"
                record.is_manual_override = True
                record.override_reason = payload.reason.strip()
                record.override_by = payload.override_by.strip() if payload.override_by else "Admin"

                if record.check_in_time:
                    duration_mins = max(0.0, round((log_time - record.check_in_time).total_seconds() / 60.0, 1))
                    record.work_duration_minutes = duration_mins

                emp_shift = student.shift
                if not emp_shift and student.shift_id:
                    emp_shift = self.db.query(WorkShift).filter(WorkShift.tenant_id == tenant.id, WorkShift.id == student.shift_id).first()
                if not emp_shift:
                    emp_shift = self.db.query(WorkShift).filter(WorkShift.tenant_id == tenant.id, WorkShift.is_default == True).first()

                shift_out_str = emp_shift.end_time if emp_shift else (branding.shift_check_out_time if branding and branding.shift_check_out_time else "18:00")
                grace_mins = emp_shift.grace_period_minutes if emp_shift else (branding.shift_grace_minutes if branding and branding.shift_grace_minutes is not None else 15)
                is_night_shift = emp_shift.is_night_shift if emp_shift else False
                try:
                    out_h, out_m = map(int, shift_out_str.split(":"))
                    check_in_dt = record.check_in_time or record.timestamp
                    target_out_date = check_in_dt.date() + timedelta(days=1) if is_night_shift else check_in_dt.date()
                    target_out = datetime.combine(target_out_date, datetime.min.time()).replace(hour=out_h, minute=out_m)
                    early_threshold = target_out - timedelta(minutes=grace_mins)
                    record.shift_status = "EARLY_DEPARTURE" if log_time < early_threshold else "COMPLETED"
                except Exception:
                    record.shift_status = "COMPLETED"

                self.db.commit()
                self.db.refresh(record)
                msg = f"Manual Check-Out recorded for '{student.name}' ({student.roll_number}). Duration: {record.work_duration_formatted}."
            else:
                record = AttendanceRecord(
                    tenant_id=tenant.id,
                    student_id=student.id,
                    node_id=payload.node_id or "MANUAL-OVERRIDE",
                    timestamp=log_time,
                    confidence_distance=0.0,
                    status="PRESENT",
                    punch_type="CHECK_OUT",
                    check_in_time=None,
                    check_out_time=log_time,
                    shift_status="COMPLETED",
                    is_manual_override=True,
                    override_reason=payload.reason.strip(),
                    override_by=payload.override_by.strip() if payload.override_by else "Admin",
                )
                self.db.add(record)
                self.db.commit()
                self.db.refresh(record)
                msg = f"Manual Check-Out recorded for '{student.name}' ({student.roll_number})."
        else:
            shift_status = "ON_TIME"
            if is_corporate:
                emp_shift = student.shift
                if not emp_shift and student.shift_id:
                    emp_shift = self.db.query(WorkShift).filter(WorkShift.tenant_id == tenant.id, WorkShift.id == student.shift_id).first()
                if not emp_shift:
                    emp_shift = self.db.query(WorkShift).filter(WorkShift.tenant_id == tenant.id, WorkShift.is_default == True).first()

                shift_in_str = emp_shift.start_time if emp_shift else (branding.shift_check_in_time if branding and branding.shift_check_in_time else "10:30")
                grace_mins = emp_shift.grace_period_minutes if emp_shift else (branding.shift_grace_minutes if branding and branding.shift_grace_minutes is not None else 15)
                try:
                    in_h, in_m = map(int, shift_in_str.split(":"))
                    target_in = datetime.combine(today, datetime.min.time()).replace(hour=in_h, minute=in_m)
                    late_threshold = target_in + timedelta(minutes=grace_mins)
                    shift_status = "LATE_CHECKIN" if log_time > late_threshold else "ON_TIME"
                except Exception:
                    shift_status = "ON_TIME"

            record = AttendanceRecord(
                tenant_id=tenant.id,
                student_id=student.id,
                node_id=payload.node_id or "MANUAL-OVERRIDE",
                timestamp=log_time,
                confidence_distance=0.0,
                status="PRESENT",
                punch_type="CHECK_IN" if is_corporate else "ATTENDANCE",
                check_in_time=log_time if is_corporate else None,
                check_out_time=None,
                shift_status=shift_status,
                is_manual_override=True,
                override_reason=payload.reason.strip(),
                override_by=payload.override_by.strip() if payload.override_by else "Admin",
            )
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
            msg = f"Manual Check-In recorded for '{student.name}' ({student.roll_number}) with status: {shift_status}."

        return {
            "status": "success",
            "message": msg,
            "record": record.to_dict(),
            "data": record.to_dict(),
            "tenant_id": tenant.id,
            "punch_type": record.punch_type or "CHECK_IN",
        }
