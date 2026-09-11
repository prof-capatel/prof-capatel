import asyncio
from datetime import datetime, date, timedelta, time as dt_time
import io
import json
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, case
from openpyxl.styles import Font, PatternFill, Alignment

from src.config import EXPORTS_DIR
from src.core.attendance_manager import attendance_manager
from src.core.camera_utils import decode_image_bytes
from src.core.face_engine import face_engine
from src.database.models import AttendanceRecord, Student, NodeDevice, SystemBranding, Tenant
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant, resolve_tenant
from src.server.rbac_middleware import check_tenant_operational_access, create_access_token
from src.utils.geo_utils import validate_geofence, haversine_distance
from src.utils.timezone import get_ist_now, get_ist_date

router = APIRouter(prefix="/api/v1/attendance", tags=["Attendance Management"])


class ManualOverrideRequest(BaseModel):
    student_id: int
    timestamp: Optional[str] = None  # Format: "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DDTHH:MM"
    reason: str = "Admin Manual Verification"
    override_by: Optional[str] = "Admin"
    node_id: Optional[str] = "MANUAL-OVERRIDE"


@router.post("/manual-override")
def mark_manual_override(
    payload: ManualOverrideRequest,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Biometric Fallback / Manual Override:
    Force-marks a student present with an explicit audit tag, timestamp, and justification reason scoped to tenant.
    """
    check_tenant_operational_access(current_tenant)
    student = db.query(Student).filter(
        Student.id == payload.student_id,
        Student.tenant_id == current_tenant.id,
    ).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found in this institution.")

    if not payload.reason or not payload.reason.strip():
        raise HTTPException(status_code=400, detail="An override justification reason is required.")

    # Parse custom timestamp if provided, else use current IST time
    log_time = get_ist_now()
    if payload.timestamp:
        try:
            clean_ts = payload.timestamp.replace("T", " ")
            if len(clean_ts) == 16:  # YYYY-MM-DD HH:MM
                clean_ts += ":00"
            log_time = datetime.strptime(clean_ts, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid timestamp format. Use YYYY-MM-DD HH:MM:SS.")

    record = AttendanceRecord(
        tenant_id=current_tenant.id,
        student_id=student.id,
        node_id=payload.node_id or "MANUAL-OVERRIDE",
        timestamp=log_time,
        confidence_distance=0.0,
        status="PRESENT",
        is_manual_override=True,
        override_reason=payload.reason.strip(),
        override_by=payload.override_by.strip() if payload.override_by else "Admin",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # Broadcast event via SSE to live dashboard feeds
    attendance_manager.publish({
        "type": "MANUAL_OVERRIDE_LOGGED",
        "tenant_id": current_tenant.id,
        "data": record.to_dict(),
        "student_id": student.id,
        "name": student.name,
        "roll_number": student.roll_number,
        "department": student.department,
        "node_id": record.node_id,
        "timestamp": record.timestamp.strftime("%Y-%m-%d %H:%M:%S") if record.timestamp else "",
        "status": "PRESENT",
        "is_manual_override": True,
        "override_reason": record.override_reason,
        "override_by": record.override_by,
        "snapshot_path": None,
    })

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "message": f"Manual override recorded for '{student.name}' ({student.roll_number}).",
        "record": record.to_dict(),
    }


def serialize_evaluated_record(rec: AttendanceRecord, is_corporate: bool, branding: Optional[SystemBranding], now: datetime) -> dict:
    """Serializes attendance record with dynamic corporate shift evaluation and missed checkout detection."""
    d = rec.to_dict()
    if is_corporate:
        # Dynamic missed checkout evaluation
        if rec.check_in_time and not rec.check_out_time:
            rec_date = rec.timestamp.date() if rec.timestamp else now.date()
            shift_out_str = branding.shift_check_out_time if branding and branding.shift_check_out_time else "18:00"
            try:
                out_parts = shift_out_str.split(":")
                out_h, out_m = int(out_parts[0]), int(out_parts[1])
                target_out = datetime.combine(rec_date, dt_time(hour=out_h, minute=out_m))
                end_window = target_out + timedelta(minutes=30)
            except Exception:
                end_window = datetime.combine(rec_date, dt_time(hour=18, minute=30))

            if rec_date < now.date() or now > end_window:
                d["shift_status"] = "MISSED_CHECKOUT"
                d["status_badge_label"] = "Missed Checkout"
            else:
                d["status_badge_label"] = "Active (Checked In)"
        elif rec.check_out_time:
            if d.get("shift_status") == "EARLY_DEPARTURE":
                d["status_badge_label"] = "Early Departure"
            else:
                d["status_badge_label"] = "Completed Shift"
        else:
            d["status_badge_label"] = d.get("shift_status", "On Time")
    else:
        d["status_badge_label"] = "Present"
    return d


@router.get("/records")
@router.get("/history")
def get_attendance_records(
    date_str: Optional[str] = Query(None, description="Date filter YYYY-MM-DD"),
    start_date: Optional[str] = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date filter YYYY-MM-DD"),
    roll_number: Optional[str] = Query(None, description="Filter by student roll number"),
    department: Optional[str] = Query(None, description="Filter by department"),
    user_role: Optional[str] = Query(None, description="Filter by user role"),
    is_override: Optional[bool] = Query(None, description="Filter only manual overrides"),
    node_id: Optional[str] = Query(None, description="Filter by node ID"),
    limit: int = Query(300, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Retrieves paginated and filtered attendance records strictly scoped to active tenant."""
    query = (
        db.query(AttendanceRecord)
        .join(Student, AttendanceRecord.student_id == Student.id, isouter=True)
        .filter(AttendanceRecord.tenant_id == current_tenant.id)
    )

    if start_date and end_date:
        try:
            s_date = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()
            e_date = datetime.strptime(end_date.strip(), "%Y-%m-%d").date()
            start_dt = datetime.combine(s_date, dt_time.min)
            end_dt = datetime.combine(e_date, dt_time.max)
            query = query.filter(AttendanceRecord.timestamp.between(start_dt, end_dt))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date or end_date format. Use YYYY-MM-DD.")
    elif start_date:
        try:
            s_date = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()
            start_dt = datetime.combine(s_date, dt_time.min)
            query = query.filter(AttendanceRecord.timestamp >= start_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD.")
    elif date_str:
        try:
            target_date = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
            start_dt = datetime.combine(target_date, dt_time.min)
            end_dt = datetime.combine(target_date, dt_time.max)
            query = query.filter(AttendanceRecord.timestamp.between(start_dt, end_dt))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    if roll_number:
        query = query.filter(Student.roll_number.ilike(f"%{roll_number.strip()}%"))

    if department:
        query = query.filter(Student.department == department.strip())

    if user_role:
        query = query.filter(Student.user_role == user_role.strip().lower())

    if is_override is not None:
        query = query.filter(AttendanceRecord.is_manual_override == is_override)

    if node_id:
        query = query.filter(AttendanceRecord.node_id == node_id.strip())

    records = query.order_by(AttendanceRecord.timestamp.desc()).limit(limit).all()

    tenant_type = (current_tenant.tenant_type or "educational").lower()
    is_corporate = tenant_type in ["corporate", "company", "enterprise"]
    branding = current_tenant.branding
    now = get_ist_now()

    serialized = [serialize_evaluated_record(r, is_corporate, branding, now) for r in records]

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "is_corporate": is_corporate,
        "records": serialized,
    }


@router.get("/stats")
def get_attendance_stats(
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Computes summary statistics for the dashboard cards strictly for current tenant."""
    today = get_ist_date()
    start_today = datetime.combine(today, dt_time.min)
    end_today = datetime.combine(today, dt_time.max)
    now = get_ist_now()

    tenant_type = (current_tenant.tenant_type or "educational").lower()
    is_corporate = tenant_type in ["corporate", "company", "enterprise"]
    branding = current_tenant.branding

    shift_in_str = branding.shift_check_in_time if branding and branding.shift_check_in_time else "10:30"
    shift_out_str = branding.shift_check_out_time if branding and branding.shift_check_out_time else "18:00"

    # For corporate tenants, track active corporate workforce (role != 'student' or all active)
    # For educational tenants, track active students (role == 'student')
    if is_corporate:
        target_role_filter = Student.user_role != "student"
        total_members = (
            db.query(Student)
            .filter(
                Student.tenant_id == current_tenant.id,
                Student.is_active == True,
                target_role_filter,
            )
            .count()
        )
        if total_members == 0:
            total_members = (
                db.query(Student)
                .filter(
                    Student.tenant_id == current_tenant.id,
                    Student.is_active == True,
                )
                .count()
            )
            target_role_filter = True

        today_records = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.tenant_id == current_tenant.id,
                AttendanceRecord.timestamp.between(start_today, end_today),
            )
            .all()
        )

        checked_in_today = len(set(r.student_id for r in today_records if r.student_id))
        checked_out_today = len(set(r.student_id for r in today_records if r.student_id and r.check_out_time))
        
        # Missed checkout calculation
        try:
            out_parts = shift_out_str.split(":")
            out_h, out_m = int(out_parts[0]), int(out_parts[1])
            target_out = datetime.combine(today, dt_time(hour=out_h, minute=out_m))
            is_past_shift = now > (target_out + timedelta(minutes=30))
        except Exception:
            is_past_shift = False

        missed_checkout_today = 0
        if is_past_shift:
            missed_checkout_today = sum(1 for r in today_records if r.check_in_time and not r.check_out_time)

        present_today = checked_in_today
        member_label = "Employees"
    else:
        total_members = (
            db.query(Student)
            .filter(
                Student.tenant_id == current_tenant.id,
                Student.is_active == True,
                Student.user_role == "student",
            )
            .count()
        )
        present_today = (
            db.query(distinct(AttendanceRecord.student_id))
            .join(Student, AttendanceRecord.student_id == Student.id)
            .filter(
                AttendanceRecord.tenant_id == current_tenant.id,
                AttendanceRecord.timestamp.between(start_today, end_today),
                Student.user_role == "student",
            )
            .count()
        )
        checked_in_today = present_today
        checked_out_today = 0
        missed_checkout_today = 0
        member_label = "Students"

    # Total registered profiles across all roles in this tenant
    total_all_users = (
        db.query(Student)
        .filter(
            Student.tenant_id == current_tenant.id,
            Student.is_active == True,
        )
        .count()
    )

    total_today_logs = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.tenant_id == current_tenant.id,
            AttendanceRecord.timestamp.between(start_today, end_today),
        )
        .count()
    )

    active_nodes = (
        db.query(NodeDevice)
        .filter(
            NodeDevice.tenant_id == current_tenant.id,
            NodeDevice.is_online == True,
        )
        .count()
    )

    attendance_pct = round((present_today / total_members * 100), 1) if total_members > 0 else 0.0

    return {
        "tenant_id": current_tenant.id,
        "is_corporate": is_corporate,
        "member_label": member_label,
        "total_students": total_members,
        "total_members": total_members,
        "total_all_users": total_all_users,
        "present_today": present_today,
        "checked_in_today": checked_in_today,
        "checked_out_today": checked_out_today,
        "missed_checkout_today": missed_checkout_today,
        "shift_check_in_time": shift_in_str,
        "shift_check_out_time": shift_out_str,
        "shift_hours_display": f"{shift_in_str} - {shift_out_str}",
        "attendance_percentage": attendance_pct,
        "total_today_logs": total_today_logs,
        "active_nodes": active_nodes,
        "date": today.isoformat(),
    }


@router.get("/analytics")
def get_analytics_metrics(
    defaulter_threshold: float = Query(75.0, ge=10.0, le=100.0, description="Defaulter threshold percentage"),
    days: int = Query(7, ge=7, le=60, description="Days range for trend analysis"),
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Comprehensive Analytics Dashboard API scoped to active tenant:
    Computes summary metrics, daily trends, department breakdowns, and low-attendance defaulters.
    """
    today = get_ist_date()
    start_today = datetime.combine(today, dt_time.min)
    end_today = datetime.combine(today, dt_time.max)

    tenant_type = (current_tenant.tenant_type or "educational").lower()
    is_corporate = tenant_type in ["corporate", "company", "enterprise"]
    member_label = "Employees" if is_corporate else "Students"

    # 1. Role Headcount Distribution for current tenant
    if is_corporate:
        employees_count = db.query(Student).filter(Student.tenant_id == current_tenant.id, Student.is_active == True, Student.user_role.in_(["employee", "contractor", "intern"])).count()
        managers_count = db.query(Student).filter(Student.tenant_id == current_tenant.id, Student.is_active == True, Student.user_role == "manager").count()
        staff_count = db.query(Student).filter(Student.tenant_id == current_tenant.id, Student.is_active == True, Student.user_role == "admin_staff").count()
        other_count = db.query(Student).filter(Student.tenant_id == current_tenant.id, Student.is_active == True, ~Student.user_role.in_(["employee", "contractor", "intern", "manager", "admin_staff", "student"])).count()
        
        # If specific roles are not yet assigned, count all active as employees
        if employees_count == 0 and managers_count == 0 and staff_count == 0:
            employees_count = db.query(Student).filter(Student.tenant_id == current_tenant.id, Student.is_active == True).count()

        headcount = {
            "employees": employees_count,
            "managers": managers_count,
            "staff": staff_count,
            "other": other_count,
            "students": employees_count,
            "teachers": managers_count,
            "total": employees_count + managers_count + staff_count + other_count,
        }
        tracked_filter = Student.user_role != "student"
        tracked_query = db.query(Student).filter(
            Student.tenant_id == current_tenant.id,
            Student.is_active == True,
            tracked_filter,
        )
        if tracked_query.count() == 0:
            tracked_filter = True
            tracked_query = db.query(Student).filter(
                Student.tenant_id == current_tenant.id,
                Student.is_active == True,
            )
        tracked_students = tracked_query.all()
    else:
        students_count = db.query(Student).filter(Student.tenant_id == current_tenant.id, Student.is_active == True, Student.user_role == "student").count()
        teachers_count = db.query(Student).filter(Student.tenant_id == current_tenant.id, Student.is_active == True, Student.user_role == "teacher").count()
        staff_count = db.query(Student).filter(Student.tenant_id == current_tenant.id, Student.is_active == True, Student.user_role == "admin_staff").count()
        other_count = db.query(Student).filter(Student.tenant_id == current_tenant.id, Student.is_active == True, ~Student.user_role.in_(["student", "teacher", "admin_staff"])).count()

        headcount = {
            "students": students_count,
            "teachers": teachers_count,
            "staff": staff_count,
            "other": other_count,
            "employees": students_count,
            "managers": teachers_count,
            "total": students_count + teachers_count + staff_count + other_count,
        }
        tracked_filter = Student.user_role == "student"
        tracked_students = db.query(Student).filter(
            Student.tenant_id == current_tenant.id,
            Student.is_active == True,
            tracked_filter,
        ).all()

    primary_count = len(tracked_students)

    # 2. Today's Turnout
    present_today = (
        db.query(distinct(AttendanceRecord.student_id))
        .join(Student, AttendanceRecord.student_id == Student.id)
        .filter(
            AttendanceRecord.tenant_id == current_tenant.id,
            AttendanceRecord.timestamp.between(start_today, end_today),
            tracked_filter,
        )
        .count()
    )
    today_rate = round((present_today / primary_count * 100), 1) if primary_count > 0 else 0.0

    # 3. Daily Attendance Trend for the last N days
    daily_trends = []
    for d in range(days - 1, -1, -1):
        target_date = today - timedelta(days=d)
        d_start = datetime.combine(target_date, dt_time.min)
        d_end = datetime.combine(target_date, dt_time.max)

        present_on_date = (
            db.query(distinct(AttendanceRecord.student_id))
            .join(Student, AttendanceRecord.student_id == Student.id)
            .filter(
                AttendanceRecord.tenant_id == current_tenant.id,
                AttendanceRecord.timestamp.between(d_start, d_end),
                tracked_filter,
            )
            .count()
        )
        rate = round((present_on_date / primary_count * 100), 1) if primary_count > 0 else 0.0

        daily_trends.append({
            "label": target_date.strftime("%b %d"),
            "date": target_date.strftime("%b %d"),
            "full_date": target_date.isoformat(),
            "present_count": present_on_date,
            "total_students": primary_count,
            "total_members": primary_count,
            "attendance_rate": rate,
            "rate_pct": rate,
        })

    # 4. Department Breakdown (Aggregated strictly for tracked members in active tenant)
    dept_rows = (
        db.query(
            Student.department,
            func.count(distinct(Student.id)).label("total_dept_students"),
        )
        .filter(
            Student.tenant_id == current_tenant.id,
            Student.is_active == True,
            tracked_filter,
        )
        .group_by(Student.department)
        .all()
    )

    departments_summary = []
    for dept_name, dept_total in dept_rows:
        dept_present_today = (
            db.query(distinct(AttendanceRecord.student_id))
            .join(Student, AttendanceRecord.student_id == Student.id)
            .filter(
                AttendanceRecord.tenant_id == current_tenant.id,
                AttendanceRecord.timestamp.between(start_today, end_today),
                Student.department == dept_name,
                tracked_filter,
            )
            .count()
        )
        dept_rate = round((dept_present_today / dept_total * 100), 1) if dept_total > 0 else 0.0
        departments_summary.append({
            "department": dept_name or "General",
            "total_students": dept_total,
            "total_members": dept_total,
            "present_today": dept_present_today,
            "turnout_percentage": dept_rate,
            "rate_pct": dept_rate,
        })

    # 5. Defaulter Identification (Members below threshold across unique attendance sessions)
    total_dates_recorded = (
        db.query(func.count(distinct(func.date(AttendanceRecord.timestamp))))
        .filter(AttendanceRecord.tenant_id == current_tenant.id)
        .scalar()
    ) or 1

    defaulters = []
    satisfactory_count = 0

    for s in tracked_students:
        attended_days = (
            db.query(func.count(distinct(func.date(AttendanceRecord.timestamp))))
            .filter(AttendanceRecord.tenant_id == current_tenant.id, AttendanceRecord.student_id == s.id)
            .scalar()
        ) or 0

        override_count = (
            db.query(func.count(AttendanceRecord.id))
            .filter(
                AttendanceRecord.tenant_id == current_tenant.id,
                AttendanceRecord.student_id == s.id,
                AttendanceRecord.is_manual_override == True,
            )
            .scalar()
        ) or 0

        pct = round((attended_days / total_dates_recorded * 100), 1)
        is_defaulter = pct < defaulter_threshold

        if is_defaulter:
            defaulters.append({
                "student_id": s.id,
                "name": s.name,
                "roll_number": s.roll_number,
                "employee_code": s.roll_number,
                "department": s.department or "General",
                "user_role": s.user_role or ("employee" if is_corporate else "student"),
                "class_semester": "" if is_corporate else (s.class_semester or "General"),
                "attended_days": attended_days,
                "total_days": total_dates_recorded,
                "attendance_pct": pct,
                "manual_overrides": override_count,
                "status": "DEFAULTER_WARNING",
            })
        else:
            satisfactory_count += 1

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "is_corporate": is_corporate,
        "member_label": member_label,
        "defaulter_threshold": defaulter_threshold,
        "headcount": headcount,
        "today_turnout": {
            "present_students": present_today,
            "present_members": present_today,
            "total_students": primary_count,
            "total_members": primary_count,
            "turnout_pct": today_rate,
        },
        "daily_trends": daily_trends,
        "departments": departments_summary,
        "defaulters": defaulters,
        "defaulter_count": len(defaulters),
        "satisfactory_count": satisfactory_count,
        "total_active_sessions": total_dates_recorded,
    }


@router.get("/export-compliance")
def export_compliance_report(
    defaulter_threshold: float = Query(75.0, ge=10.0, le=100.0),
    export_format: str = Query("xlsx", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Exports structured institutional/corporate compliance audit report in Excel or CSV format for active tenant."""
    total_dates_recorded = (
        db.query(func.count(distinct(func.date(AttendanceRecord.timestamp))))
        .filter(AttendanceRecord.tenant_id == current_tenant.id)
        .scalar()
    ) or 1
    total_dates_recorded = max(1, total_dates_recorded)

    tenant_type = (current_tenant.tenant_type or "educational").lower()
    is_corporate = tenant_type in ["corporate", "company", "enterprise"]

    students = (
        db.query(Student)
        .filter(Student.tenant_id == current_tenant.id, Student.is_active == True)
        .order_by(Student.department.asc(), Student.name.asc())
        .all()
    )

    rows = []
    for s in students:
        attended = (
            db.query(func.count(distinct(func.date(AttendanceRecord.timestamp))))
            .filter(AttendanceRecord.tenant_id == current_tenant.id, AttendanceRecord.student_id == s.id)
            .scalar()
        ) or 0

        override_count = (
            db.query(func.count(AttendanceRecord.id))
            .filter(
                AttendanceRecord.tenant_id == current_tenant.id,
                AttendanceRecord.student_id == s.id,
                AttendanceRecord.is_manual_override == True,
            )
            .scalar()
        ) or 0

        pct = round((attended / total_dates_recorded * 100), 1) if total_dates_recorded > 0 else 0.0
        status_label = "COMPLIANT" if pct >= defaulter_threshold else "DEFAULTER"

        if is_corporate:
            rows.append({
                "Employee Code / ID": s.roll_number,
                "Full Name": s.name,
                "Designation / Role": (s.user_role or "Employee").capitalize(),
                "Department": s.department or "General",
                "Working Days Recorded": total_dates_recorded,
                "Days Present": attended,
                "Manual Overrides Count": override_count,
                "Attendance Percentage (%)": pct,
                "Compliance Status": status_label,
            })
        else:
            rows.append({
                "Student ID / Roll": s.roll_number,
                "Full Name": s.name,
                "Role": (s.user_role or "student").capitalize(),
                "Department": s.department or "General",
                "Class / Semester": s.class_semester or "General",
                "Total Sessions Held": total_dates_recorded,
                "Sessions Attended": attended,
                "Manual Overrides Count": override_count,
                "Attendance Percentage (%)": pct,
                "Compliance Status": status_label,
            })

    df = pd.DataFrame(rows)
    today_str = get_ist_date().strftime("%Y%m%d")

    # Fetch institution branding
    branding = current_tenant.branding
    inst_name = branding.institution_name if branding else current_tenant.name
    short_code = branding.short_code if branding else current_tenant.slug.upper()

    if export_format == "csv":
        csv_buffer = io.StringIO()
        csv_buffer.write(f"# INSTITUTION / COMPANY: {inst_name} ({short_code})\n")
        csv_buffer.write(f"# REPORT: {'Corporate Attendance & Workforce Compliance Audit' if is_corporate else 'Institutional Attendance Compliance Audit'}\n")
        csv_buffer.write(f"# DEFAULTER THRESHOLD: {defaulter_threshold}%\n")
        csv_buffer.write(f"# GENERATED (IST): {get_ist_now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        return StreamingResponse(
            io.BytesIO(csv_buffer.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=compliance_audit_{current_tenant.slug}_{today_str}.csv"},
        )
    else:
        excel_buffer = io.BytesIO()
        sheet_title = "Workforce Compliance" if is_corporate else "Compliance Audit"
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_title, startrow=4)
            ws = writer.sheets[sheet_title]

            # Header Banner styling
            ws.merge_cells("A1:K1")
            ws["A1"] = f"{inst_name} ({short_code}) — {'Corporate Attendance Compliance Report' if is_corporate else 'Attendance Compliance Report'}"
            ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
            ws["A1"].fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
            ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

            ws.merge_cells("A2:K2")
            ws["A2"] = f"Defaulter Threshold: <{defaulter_threshold}% | Generated (IST): {get_ist_now().strftime('%Y-%m-%d %H:%M:%S')} | Total Tracked Profiles: {len(students)}"
            ws["A2"].font = Font(name="Calibri", size=10, italic=True)
            ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

        excel_buffer.seek(0)
        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=compliance_audit_{current_tenant.slug}_{today_str}.xlsx"},
        )


@router.get("/export")
def export_attendance_report(
    date_str: Optional[str] = Query(None, description="Filter date YYYY-MM-DD"),
    start_date: Optional[str] = Query(None, description="Start date filter YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date filter YYYY-MM-DD"),
    roll_number: Optional[str] = Query(None, description="Filter by roll/employee number"),
    department: Optional[str] = Query(None, description="Filter by department"),
    user_role: Optional[str] = Query(None, description="Filter by user role"),
    is_override: Optional[bool] = Query(None, description="Filter only manual overrides"),
    export_format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Exports raw attendance history into downloadable CSV or Excel spreadsheet scoped to tenant."""
    tenant_type = (current_tenant.tenant_type or "educational").lower()
    is_corporate = tenant_type in ["corporate", "company", "enterprise"]
    branding = current_tenant.branding
    now = get_ist_now()

    query = (
        db.query(AttendanceRecord)
        .join(Student, AttendanceRecord.student_id == Student.id, isouter=True)
        .filter(AttendanceRecord.tenant_id == current_tenant.id)
        .order_by(AttendanceRecord.timestamp.desc())
    )

    if start_date and end_date:
        try:
            s_date = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()
            e_date = datetime.strptime(end_date.strip(), "%Y-%m-%d").date()
            start_dt = datetime.combine(s_date, dt_time.min)
            end_dt = datetime.combine(e_date, dt_time.max)
            query = query.filter(AttendanceRecord.timestamp.between(start_dt, end_dt))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date or end_date format. Use YYYY-MM-DD.")
    elif start_date:
        try:
            s_date = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()
            start_dt = datetime.combine(s_date, dt_time.min)
            query = query.filter(AttendanceRecord.timestamp >= start_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD.")
    elif date_str:
        try:
            target_date = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
            start_dt = datetime.combine(target_date, dt_time.min)
            end_dt = datetime.combine(target_date, dt_time.max)
            query = query.filter(AttendanceRecord.timestamp.between(start_dt, end_dt))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    if roll_number:
        query = query.filter(Student.roll_number.ilike(f"%{roll_number.strip()}%"))

    if department:
        query = query.filter(Student.department == department.strip())

    if user_role:
        query = query.filter(Student.user_role == user_role.strip().lower())

    if is_override is not None:
        query = query.filter(AttendanceRecord.is_manual_override == is_override)

    results = query.all()

    data = []
    for r in results:
        eval_dict = serialize_evaluated_record(r, is_corporate, branding, now)
        s = r.student

        if is_corporate:
            data.append({
                "Log ID": r.id,
                "Employee Code / ID": s.roll_number if s else "N/A",
                "Full Name": s.name if s else "Unknown",
                "Department": s.department if s else "N/A",
                "Designation / Role": (s.user_role if s and s.user_role else "employee").capitalize(),
                "Attendance Date": r.timestamp.strftime("%Y-%m-%d") if r.timestamp else "",
                "Check-In Time": eval_dict.get("check_in_short", "--"),
                "Check-Out Time": eval_dict.get("check_out_short", "--"),
                "Total Active Hours": eval_dict.get("work_duration_formatted", "--"),
                "Shift Status": eval_dict.get("status_badge_label", eval_dict.get("shift_status", "On Time")),
                "Ingestion Node": r.node_id,
                "Manual Override": "Yes" if r.is_manual_override else "No",
                "Override Reason": r.override_reason or "",
            })
        else:
            data.append({
                "Log ID": r.id,
                "Roll Number": s.roll_number if s else "N/A",
                "Name": s.name if s else "Unknown",
                "Department": s.department if s else "N/A",
                "Role": (s.user_role if s and s.user_role else "student").capitalize(),
                "Node Ingestion": r.node_id,
                "Timestamp (IST)": r.timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.timestamp else "",
                "Confidence Distance": round(r.confidence_distance, 4) if r.confidence_distance is not None else "",
                "Status": r.status,
                "Manual Override": "Yes" if r.is_manual_override else "No",
                "Override Reason": r.override_reason or "",
            })

    df = pd.DataFrame(data)
    date_label = date_str or get_ist_date().strftime("%Y%m%d")

    # Fetch institution branding
    inst_name = branding.institution_name if branding else current_tenant.name
    short_code = branding.short_code if branding else current_tenant.slug.upper()

    if export_format == "csv":
        csv_buffer = io.StringIO()
        csv_buffer.write(f"# INSTITUTION: {inst_name} ({short_code})\n")
        csv_buffer.write(f"# LOGS: Attendance Audit Export\n")
        csv_buffer.write(f"# GENERATED (IST): {get_ist_now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        return StreamingResponse(
            io.BytesIO(csv_buffer.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=attendance_logs_{current_tenant.slug}_{date_label}.csv"},
        )
    else:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Attendance Logs", startrow=3)
            ws = writer.sheets["Attendance Logs"]

            # Merged Institutional Header Banner
            ws.merge_cells("A1:K1")
            ws["A1"] = f"{inst_name} ({short_code}) — Attendance Log Records"
            ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
            ws["A1"].fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
            ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

            ws.merge_cells("A2:K2")
            ws["A2"] = f"Generated (IST): {get_ist_now().strftime('%Y-%m-%d %H:%M:%S')} | Total Records: {len(data)}"
            ws["A2"].font = Font(name="Calibri", size=10, italic=True)
            ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

        excel_buffer.seek(0)
        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=attendance_logs_{current_tenant.slug}_{date_label}.xlsx"},
        )


@router.get("/live-stream")
async def live_stream_events():
    """
    Server-Sent Events (SSE) streaming endpoint for real-time live attendance feed.
    """
    queue = attendance_manager.subscribe()

    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'CONNECTED', 'message': 'Live stream connected.'})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield f": ping\n\n"
        finally:
            attendance_manager.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/self-config")
@router.get("/geofence-config")
def get_self_attendance_config(
    tenant_slug: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Returns public self-attendance and geofencing configuration for student camera view.
    Does not require login.
    """
    target_tenant = current_tenant
    if tenant_slug:
        t = resolve_tenant(db, tenant_slug)
        if t:
            target_tenant = t

    branding = target_tenant.branding
    is_enabled = bool(branding.enable_self_attendance) if branding and branding.enable_self_attendance is not None else False
    is_geo_set = branding is not None and branding.geo_latitude is not None and branding.geo_longitude is not None

    return {
        "status": "success",
        "tenant_id": target_tenant.id,
        "tenant_slug": target_tenant.slug,
        "tenant_name": target_tenant.name,
        "institution_name": branding.institution_name if branding else target_tenant.name,
        "short_code": branding.short_code if branding else "FA-HUB",
        "logo_url": f"/data/branding/{branding.logo_filename}" if branding and branding.logo_filename else None,
        "primary_accent_color": branding.primary_accent_color if branding else "#6366f1",
        "enable_self_attendance": is_enabled,
        "is_configured": is_geo_set,
        "geo_latitude": branding.geo_latitude if branding else None,
        "geo_longitude": branding.geo_longitude if branding else None,
        "geo_radius_meters": float(branding.geo_radius_meters) if (branding and branding.geo_radius_meters) else 150.0,
        "max_gps_accuracy_meters": float(branding.max_gps_accuracy_meters) if (branding and branding.max_gps_accuracy_meters) else 50.0,
        "face_threshold": float(branding.self_attendance_face_threshold) if (branding and branding.self_attendance_face_threshold) else 0.52,
    }


@router.post("/self-mark")
async def self_mark_attendance(
    latitude: float = Form(...),
    longitude: float = Form(...),
    accuracy: float = Form(...),
    tenant_slug: Optional[str] = Form(None),
    frame: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Frictionless Face-Based Self-Attendance via Personal Device:
    1. Validates strict anti-mock HTML5 GPS geofence against campus coordinates.
    2. Runs face detection & 1:N biometric similarity matching against active tenant's face vectors.
    3. Enforces single-face policy, anti-spoofing liveness, and sliding deduplication window.
    """
    target_tenant = current_tenant
    if tenant_slug:
        t = resolve_tenant(db, tenant_slug)
        if t:
            target_tenant = t

    # Tenant Operational Status check
    check_tenant_operational_access(target_tenant)

    branding = target_tenant.branding
    if not branding or not branding.enable_self_attendance:
        raise HTTPException(
            status_code=403,
            detail="Self-attendance is currently disabled by institution administration.",
        )

    if branding.geo_latitude is None or branding.geo_longitude is None:
        raise HTTPException(
            status_code=400,
            detail="Institution geofence coordinates have not been configured by the administrator.",
        )

    # 1. Geofence & GPS Accuracy Validation
    max_radius = branding.geo_radius_meters if branding.geo_radius_meters is not None else 150.0
    max_acc = branding.max_gps_accuracy_meters if branding.max_gps_accuracy_meters is not None else 50.0

    is_valid_geo, dist_meters, geo_err = validate_geofence(
        user_lat=latitude,
        user_lon=longitude,
        user_accuracy=accuracy,
        target_lat=branding.geo_latitude,
        target_lon=branding.geo_longitude,
        max_radius_meters=max_radius,
        max_accuracy_meters=max_acc,
    )

    if not is_valid_geo:
        raise HTTPException(
            status_code=403,
            detail=geo_err or "GPS Geofence validation failed. You must be on campus premises.",
        )

    # 2. Read & Decode Camera Image
    contents = await frame.read()
    image_bgr = decode_image_bytes(contents)
    if image_bgr is None:
        raise HTTPException(status_code=400, detail="Invalid camera capture image.")

    # 3. Biometric Face Detection & Recognition
    enable_anti_spoof = True
    if branding.enable_anti_spoofing is not None:
        enable_anti_spoof = bool(branding.enable_anti_spoofing)
    if branding.liveness_mode == "DISABLED":
        enable_anti_spoof = False

    face_thresh = branding.self_attendance_face_threshold if branding.self_attendance_face_threshold is not None else 0.52

    try:
        detections = face_engine.detect_and_recognize_faces(
            image_bgr,
            node_id="SELF-ATTENDANCE-MOBILE",
            tenant_id=target_tenant.id,
            is_single_shot=True,
            enable_anti_spoofing=enable_anti_spoof,
            custom_distance_threshold=face_thresh,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Biometric processing error: {str(e)}")

    # 4. Strict Single-Face Only Gate (Decision 1 A)
    if len(detections) == 0:
        raise HTTPException(
            status_code=400,
            detail="No face detected in camera frame. Please center your face inside the circle with clear lighting.",
        )

    if len(detections) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"Multiple faces ({len(detections)}) detected. Only 1 person is allowed in the frame for self-attendance.",
        )

    det = detections[0]

    # 5. Anti-Spoofing Gate
    if not det.get("is_live", True):
        reasons = ", ".join(det.get("liveness_reasons", ["Anti-spoof liveness check failed"]))
        raise HTTPException(
            status_code=400,
            detail=f"Liveness verification failed ({reasons}). Please look directly at the camera in natural lighting.",
        )

    # 6. Biometric Identity Match Gate
    if not det.get("is_match", False) or det.get("student_id") is None:
        raise HTTPException(
            status_code=404,
            detail="Face not recognized in institution records. Please verify you are registered or contact admin.",
        )

    student_id = det["student_id"]
    confidence_dist = det.get("distance", 1.0)
    face_box = det.get("box")

    # Cooldown window
    custom_cooldown_secs = max(60, int((branding.cooldown_minutes or 60) * 60))

    # 7. Persist Attendance Record
    mark_res = attendance_manager.mark_attendance(
        student_id=student_id,
        node_id="SELF-ATTENDANCE-MOBILE",
        confidence_distance=confidence_dist,
        frame_bgr=image_bgr,
        face_box=face_box,
        tenant_id=target_tenant.id,
        custom_cooldown_seconds=custom_cooldown_secs,
        geo_latitude=latitude,
        geo_longitude=longitude,
        geo_distance_meters=dist_meters,
        is_self_attendance=True,
    )

    if mark_res.get("cooldown_active"):
        return {
            "status": "cooldown",
            "message": f"Attendance already recorded recently. Next check-in allowed in {mark_res['cooldown_remaining_minutes']} minutes.",
            "cooldown_remaining_seconds": mark_res.get("cooldown_remaining_seconds", 0),
            "student_name": det.get("name"),
            "student_roll": det.get("roll_number"),
            "distance_meters": dist_meters,
        }

    token = create_access_token(
        user_id=student_id,
        role=det.get("user_role", "STUDENT").upper(),
        tenant_id=target_tenant.id,
        username=det.get("roll_number") or f"student_{student_id}",
    )

    return {
        "status": "success",
        "message": f"Attendance successfully marked for {det.get('name')}!",
        "access_token": token,
        "token_type": "bearer",
        "student": {
            "id": student_id,
            "name": det.get("name"),
            "roll_number": det.get("roll_number"),
            "department": det.get("department"),
            "user_role": det.get("user_role", "student"),
        },
        "confidence_pct": det.get("confidence_pct", 0.0),
        "distance_meters": dist_meters,
        "timestamp": mark_res["record"]["timestamp"],
        "record": mark_res["record"],
    }

