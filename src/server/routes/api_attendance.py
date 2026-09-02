import asyncio
from datetime import datetime, date, timedelta, time as dt_time
import io
import json
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, case
from openpyxl.styles import Font, PatternFill, Alignment

from src.config import EXPORTS_DIR
from src.core.attendance_manager import attendance_manager
from src.database.models import AttendanceRecord, Student, NodeDevice, SystemBranding
from src.database.session import get_db

router = APIRouter(prefix="/api/v1/attendance", tags=["Attendance Management"])


class ManualOverrideRequest(BaseModel):
    student_id: int
    timestamp: Optional[str] = None  # Format: "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DDTHH:MM"
    reason: str = "Admin Manual Verification"
    override_by: Optional[str] = "Admin"
    node_id: Optional[str] = "MANUAL-OVERRIDE"


@router.post("/manual-override")
def mark_manual_override(payload: ManualOverrideRequest, db: Session = Depends(get_db)):
    """
    Biometric Fallback / Manual Override:
    Force-marks a student present with an explicit audit tag, timestamp, and justification reason.
    """
    student = db.query(Student).filter(Student.id == payload.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found.")

    if not payload.reason or not payload.reason.strip():
        raise HTTPException(status_code=400, detail="An override justification reason is required.")

    # Parse custom timestamp if provided, else use current UTC time
    log_time = datetime.utcnow()
    if payload.timestamp:
        try:
            clean_ts = payload.timestamp.replace("T", " ")
            if len(clean_ts) == 16:  # YYYY-MM-DD HH:MM
                clean_ts += ":00"
            log_time = datetime.strptime(clean_ts, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid timestamp format. Use YYYY-MM-DD HH:MM:SS.")

    record = AttendanceRecord(
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
        "student_id": student.id,
        "student_name": student.name,
        "roll_number": student.roll_number,
        "department": student.department,
        "node_id": record.node_id,
        "timestamp": record.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "confidence_distance": 0.0,
        "match_confidence_pct": 100.0,
        "status": "PRESENT",
        "is_manual_override": True,
        "override_reason": record.override_reason,
        "override_by": record.override_by,
        "snapshot_path": None,
    })

    return {
        "status": "success",
        "message": f"Manual override recorded for '{student.name}' ({student.roll_number}).",
        "record": record.to_dict(),
    }


@router.get("/records")
def get_attendance_records(
    date_str: Optional[str] = Query(None, description="Date filter YYYY-MM-DD"),
    roll_number: Optional[str] = Query(None, description="Filter by student roll number"),
    department: Optional[str] = Query(None, description="Filter by department"),
    user_role: Optional[str] = Query(None, description="Filter by user role"),
    is_override: Optional[bool] = Query(None, description="Filter only manual overrides"),
    node_id: Optional[str] = Query(None, description="Filter by node ID"),
    limit: int = Query(150, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Retrieves paginated and filtered attendance records with multi-parameter criteria."""
    query = db.query(AttendanceRecord).join(Student, AttendanceRecord.student_id == Student.id, isouter=True)

    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
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
        query = query.filter(AttendanceRecord.node_id == node_id)

    records = query.order_by(AttendanceRecord.timestamp.desc()).limit(limit).all()
    return {"records": [r.to_dict() for r in records]}


@router.get("/stats")
def get_attendance_stats(db: Session = Depends(get_db)):
    """Computes summary statistics for the dashboard cards, filtering student role by default."""
    today = date.today()
    start_today = datetime.combine(today, dt_time.min)
    end_today = datetime.combine(today, dt_time.max)

    # Active student headcount (excluding non-students from standard classroom calculation)
    total_students = (
        db.query(Student)
        .filter(Student.is_active == True, Student.user_role == "student")
        .count()
    )

    # Total registered profiles across all roles
    total_all_users = db.query(Student).filter(Student.is_active == True).count()

    # Count unique students present today
    present_today = (
        db.query(distinct(AttendanceRecord.student_id))
        .join(Student, AttendanceRecord.student_id == Student.id)
        .filter(
            AttendanceRecord.timestamp.between(start_today, end_today),
            Student.user_role == "student",
        )
        .count()
    )

    total_today_logs = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.timestamp.between(start_today, end_today))
        .count()
    )

    active_nodes = (
        db.query(NodeDevice)
        .filter(NodeDevice.is_online == True)
        .count()
    )

    attendance_pct = round((present_today / total_students * 100), 1) if total_students > 0 else 0.0

    return {
        "total_students": total_students,
        "total_all_users": total_all_users,
        "present_today": present_today,
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
):
    """
    Comprehensive Analytics Dashboard API:
    Computes summary metrics, daily trends, department breakdowns, and low-attendance defaulters.
    """
    today = date.today()
    start_today = datetime.combine(today, dt_time.min)
    end_today = datetime.combine(today, dt_time.max)

    # 1. Role Headcount Distribution
    students_count = db.query(Student).filter(Student.is_active == True, Student.user_role == "student").count()
    teachers_count = db.query(Student).filter(Student.is_active == True, Student.user_role == "teacher").count()
    staff_count = db.query(Student).filter(Student.is_active == True, Student.user_role == "admin_staff").count()
    other_count = db.query(Student).filter(Student.is_active == True, Student.user_role == "other").count()

    # 2. Today's Student Turnout
    present_today = (
        db.query(distinct(AttendanceRecord.student_id))
        .join(Student, AttendanceRecord.student_id == Student.id)
        .filter(
            AttendanceRecord.timestamp.between(start_today, end_today),
            Student.user_role == "student",
        )
        .count()
    )
    today_rate = round((present_today / students_count * 100), 1) if students_count > 0 else 0.0

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
                AttendanceRecord.timestamp.between(d_start, d_end),
                Student.user_role == "student",
            )
            .count()
        )
        rate = round((present_on_date / students_count * 100), 1) if students_count > 0 else 0.0
        daily_trends.append({
            "date": target_date.strftime("%Y-%m-%d"),
            "label": target_date.strftime("%a, %b %d"),
            "present_count": present_on_date,
            "total_students": students_count,
            "rate_pct": rate,
        })

    # 4. Department Turnout Breakdown
    dept_results = (
        db.query(
            Student.department,
            func.count(Student.id).label("total_dept"),
        )
        .filter(Student.is_active == True, Student.user_role == "student")
        .group_by(Student.department)
        .all()
    )

    departments_summary = []
    for dept_name, total_dept in dept_results:
        dept_present_today = (
            db.query(distinct(AttendanceRecord.student_id))
            .join(Student, AttendanceRecord.student_id == Student.id)
            .filter(
                AttendanceRecord.timestamp.between(start_today, end_today),
                Student.department == dept_name,
                Student.user_role == "student",
            )
            .count()
        )
        rate = round((dept_present_today / total_dept * 100), 1) if total_dept > 0 else 0.0
        departments_summary.append({
            "department": dept_name or "General",
            "total_students": total_dept,
            "present_today": dept_present_today,
            "rate_pct": rate,
        })

    # 5. Low-Attendance Defaulters List
    # Calculate total unique dates recorded in attendance system
    total_dates_recorded = (
        db.query(func.count(distinct(func.date(AttendanceRecord.timestamp))))
        .scalar()
    ) or 1
    total_dates_recorded = max(1, total_dates_recorded)

    students_list = (
        db.query(Student)
        .filter(Student.is_active == True, Student.user_role == "student")
        .order_by(Student.name.asc())
        .all()
    )

    defaulters = []
    satisfactory_count = 0

    for s in students_list:
        attended_days = (
            db.query(func.count(distinct(func.date(AttendanceRecord.timestamp))))
            .filter(AttendanceRecord.student_id == s.id)
            .scalar()
        ) or 0

        override_count = (
            db.query(func.count(AttendanceRecord.id))
            .filter(AttendanceRecord.student_id == s.id, AttendanceRecord.is_manual_override == True)
            .scalar()
        ) or 0

        pct = round((attended_days / total_dates_recorded * 100), 1)
        is_defaulter = pct < defaulter_threshold

        if is_defaulter:
            defaulters.append({
                "student_id": s.id,
                "name": s.name,
                "roll_number": s.roll_number,
                "department": s.department,
                "class_semester": s.class_semester,
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
        "defaulter_threshold": defaulter_threshold,
        "headcount": {
            "students": students_count,
            "teachers": teachers_count,
            "staff": staff_count,
            "other": other_count,
            "total": students_count + teachers_count + staff_count + other_count,
        },
        "today_turnout": {
            "present_students": present_today,
            "total_students": students_count,
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
):
    """Exports structured institutional compliance audit report in Excel or CSV format."""
    total_dates_recorded = (
        db.query(func.count(distinct(func.date(AttendanceRecord.timestamp))))
        .scalar()
    ) or 1
    total_dates_recorded = max(1, total_dates_recorded)

    students = db.query(Student).filter(Student.is_active == True).order_by(Student.department.asc(), Student.name.asc()).all()

    report_data = []
    for s in students:
        attended_days = (
            db.query(func.count(distinct(func.date(AttendanceRecord.timestamp))))
            .filter(AttendanceRecord.student_id == s.id)
            .scalar()
        ) or 0

        override_count = (
            db.query(func.count(AttendanceRecord.id))
            .filter(AttendanceRecord.student_id == s.id, AttendanceRecord.is_manual_override == True)
            .scalar()
        ) or 0

        pct = round((attended_days / total_dates_recorded * 100), 1)
        compliance_status = "Satisfactory" if pct >= defaulter_threshold else f"Defaulter Warning (< {defaulter_threshold}%)"

        report_data.append({
            "Student ID / Roll": s.roll_number,
            "Full Name": s.name,
            "Role": s.user_role.capitalize(),
            "Department": s.department,
            "Class / Semester": s.class_semester or "General",
            "Total Sessions Held": total_dates_recorded,
            "Sessions Attended": attended_days,
            "Manual Overrides Count": override_count,
            "Attendance Percentage (%)": pct,
            "Compliance Status": compliance_status,
        })

    df = pd.DataFrame(report_data)
    date_str = date.today().strftime("%Y%m%d")

    # Fetch institution branding
    branding = db.query(SystemBranding).filter(SystemBranding.id == 1).first()
    inst_name = branding.institution_name if branding else "FaceAttendance Campus"
    short_code = branding.short_code if branding else "FA-HUB"

    if export_format == "csv":
        csv_buffer = io.StringIO()
        csv_buffer.write(f"# INSTITUTION: {inst_name} ({short_code})\n")
        csv_buffer.write(f"# REPORT: Attendance Compliance Audit (Threshold: {defaulter_threshold}%)\n")
        csv_buffer.write(f"# GENERATED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        return StreamingResponse(
            io.BytesIO(csv_buffer.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=institutional_compliance_report_{date_str}.csv"},
        )
    else:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Compliance Audit", startrow=3)
            ws = writer.sheets["Compliance Audit"]

            # Merged Institutional Header Banner
            ws.merge_cells("A1:J1")
            ws["A1"] = f"{inst_name} ({short_code}) — Institutional Compliance Report"
            ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
            ws["A1"].fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
            ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

            ws.merge_cells("A2:J2")
            ws["A2"] = f"Audit Threshold: {defaulter_threshold}% | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total Sessions: {total_dates_recorded}"
            ws["A2"].font = Font(name="Calibri", size=10, italic=True)
            ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

        excel_buffer.seek(0)
        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=institutional_compliance_report_{date_str}.xlsx"},
        )


@router.get("/export")
def export_attendance_report(
    date_str: Optional[str] = Query(None, description="Filter date YYYY-MM-DD"),
    export_format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
):
    """Exports raw attendance history into downloadable CSV or Excel spreadsheet."""
    query = (
        db.query(
            AttendanceRecord.id,
            Student.roll_number,
            Student.name,
            Student.department,
            Student.user_role,
            AttendanceRecord.node_id,
            AttendanceRecord.timestamp,
            AttendanceRecord.confidence_distance,
            AttendanceRecord.status,
            AttendanceRecord.is_manual_override,
            AttendanceRecord.override_reason,
        )
        .join(Student, AttendanceRecord.student_id == Student.id, isouter=True)
        .order_by(AttendanceRecord.timestamp.desc())
    )

    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_dt = datetime.combine(target_date, dt_time.min)
            end_dt = datetime.combine(target_date, dt_time.max)
            query = query.filter(AttendanceRecord.timestamp.between(start_dt, end_dt))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    results = query.all()

    data = []
    for row in results:
        data.append({
            "Log ID": row[0],
            "Roll Number": row[1] or "N/A",
            "Name": row[2] or "Unknown",
            "Department": row[3] or "N/A",
            "Role": (row[4] or "student").capitalize(),
            "Node Ingestion": row[5],
            "Timestamp": row[6].strftime("%Y-%m-%d %H:%M:%S") if row[6] else "",
            "Confidence Distance": round(row[7], 4) if row[7] is not None else "",
            "Status": row[8],
            "Manual Override": "Yes" if row[9] else "No",
            "Override Reason": row[10] or "",
        })

    df = pd.DataFrame(data)
    date_label = date_str or datetime.now().strftime("%Y%m%d")

    # Fetch institution branding
    branding = db.query(SystemBranding).filter(SystemBranding.id == 1).first()
    inst_name = branding.institution_name if branding else "FaceAttendance Campus"
    short_code = branding.short_code if branding else "FA-HUB"

    if export_format == "csv":
        csv_buffer = io.StringIO()
        csv_buffer.write(f"# INSTITUTION: {inst_name} ({short_code})\n")
        csv_buffer.write(f"# LOGS: Attendance Audit Export\n")
        csv_buffer.write(f"# GENERATED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        return StreamingResponse(
            io.BytesIO(csv_buffer.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=attendance_logs_{date_label}.csv"},
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
            ws["A2"] = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total Records: {len(data)}"
            ws["A2"].font = Font(name="Calibri", size=10, italic=True)
            ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

        excel_buffer.seek(0)
        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=attendance_logs_{date_label}.xlsx"},
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
