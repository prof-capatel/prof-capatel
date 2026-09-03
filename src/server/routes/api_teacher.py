import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database.models import (
    Tenant,
    User,
    AcademicYear,
    ClassModel,
    Division,
    TeacherClassAssignment,
    Student,
    AttendanceRecord,
    FaceEncoding,
    AuditLog,
)
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant
from src.server.rbac_middleware import require_roles, get_current_user
from src.core.face_engine import face_engine
from src.utils.timezone import get_ist_now

logger = logging.getLogger("api_teacher")
router = APIRouter(
    prefix="/api/v1/teacher",
    tags=["Teacher Classroom Workflows"],
    dependencies=[Depends(require_roles(["SUPER_ADMIN", "TENANT_ADMIN", "TEACHER"]))],
)


@router.get("/my-classes")
def get_my_assigned_classes(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the classes, divisions, and subjects assigned to the logged-in teacher.
    If current user is Tenant Admin or Super Admin, returns all institutional classes.
    """
    if current_user.role in ["SUPER_ADMIN", "TENANT_ADMIN"]:
        classes = db.query(ClassModel).filter(ClassModel.tenant_id == tenant.id).all()
        result = []
        for c in classes:
            c_dict = c.to_dict()
            c_dict["assigned_subject"] = "All Subjects (Admin Access)"
            result.append(c_dict)
        return {"status": "success", "is_admin": True, "classes": result}

    assignments = db.query(TeacherClassAssignment).filter(
        TeacherClassAssignment.tenant_id == tenant.id,
        TeacherClassAssignment.teacher_id == current_user.id,
    ).all()

    assigned_list = [a.to_dict() for a in assignments]
    return {
        "status": "success",
        "is_admin": False,
        "teacher_name": current_user.full_name,
        "assignments": assigned_list,
    }


@router.get("/attendance-sheet")
def get_classroom_attendance_sheet(
    class_id: Optional[int] = None,
    division_id: Optional[int] = None,
    date_str: Optional[str] = None,  # YYYY-MM-DD
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves real-time & historical classroom attendance records for assigned class cohorts.
    Returns complete student roster with PRESENT / ABSENT status and verified timestamps.
    """
    # 1. Fetch Students in target class & division
    student_query = db.query(Student).filter(Student.tenant_id == tenant.id, Student.is_active == True)
    if class_id:
        student_query = student_query.filter(Student.class_id == class_id)
    if division_id:
        student_query = student_query.filter(Student.division_id == division_id)
    students = student_query.order_by(Student.roll_number.asc()).all()

    # 2. Filter attendance logs for the target date (default: today IST)
    target_date = date_str if date_str else get_ist_now().strftime("%Y-%m-%d")
    
    student_ids = [s.id for s in students]
    records = db.query(AttendanceRecord).filter(
        AttendanceRecord.tenant_id == tenant.id,
        AttendanceRecord.student_id.in_(student_ids),
        func.date(AttendanceRecord.timestamp) == target_date,
    ).all()

    # Map student_id -> latest attendance record for that date
    attendance_map = {}
    for r in records:
        if r.student_id not in attendance_map or r.timestamp > attendance_map[r.student_id].timestamp:
            attendance_map[r.student_id] = r

    roster = []
    present_count = 0
    absent_count = 0

    for s in students:
        rec = attendance_map.get(s.id)
        if rec and rec.status == "PRESENT":
            present_count += 1
            status_label = "PRESENT"
            checkin_time = rec.timestamp.strftime("%H:%M:%S") if rec.timestamp else None
            node_id = rec.node_id
            is_override = rec.is_manual_override
            override_reason = rec.override_reason
        else:
            absent_count += 1
            status_label = "ABSENT"
            checkin_time = None
            node_id = None
            is_override = False
            override_reason = None

        roster.append({
            "student_id": s.id,
            "roll_number": s.roll_number,
            "name": s.name,
            "department": s.department,
            "class_name": s.class_obj.name if s.class_obj else (s.class_semester or "General"),
            "division_name": s.division_obj.name if s.division_obj else "N/A",
            "status": status_label,
            "checkin_time": checkin_time,
            "node_id": node_id,
            "is_manual_override": is_override,
            "override_reason": override_reason,
            "photos_count": len(s.encodings) if s.encodings else 0,
        })

    turnout_pct = round((present_count / len(students) * 100), 1) if students else 0.0

    return {
        "status": "success",
        "date": target_date,
        "class_id": class_id,
        "division_id": division_id,
        "total_enrolled": len(students),
        "present_count": present_count,
        "absent_count": absent_count,
        "turnout_pct": turnout_pct,
        "roster": roster,
    }
