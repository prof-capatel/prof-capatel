"""
Enrollment Service
Handles onboarding, profile updates, multi-angle face vector extraction,
designation-to-template auto-resolution, and department transfers.
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import cv2
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status, UploadFile

from src.config import FACES_DIR
from src.core.camera_utils import decode_image_bytes, evaluate_image_quality
from src.core.face_engine import face_engine
from src.database.models import (
    Student,
    FaceEncoding,
    Tenant,
    Department,
    ClassModel,
    Division,
    AcademicYear,
    AuditLog,
    User,
    WorkShift,
    CompanyLocation,
    DesignationMaster,
    SalaryTemplate,
    EmployeeSalaryStructure,
)
from src.utils.timezone import get_ist_now, get_ist_date

logger = logging.getLogger("enrollment_service")


class EnrollmentService:
    def __init__(self, db: Session):
        self.db = db

    def list_students(
        self,
        tenant_id: int,
        department_id: Optional[int] = None,
        class_id: Optional[int] = None,
        division_id: Optional[int] = None,
        user_role: Optional[str] = None,
        search_term: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = (
            self.db.query(Student)
            .filter(Student.tenant_id == tenant_id, Student.is_active == True)
            .options(
                joinedload(Student.department_rel),
                joinedload(Student.designation_rel),
                joinedload(Student.location),
                joinedload(Student.salary_template_rel),
                joinedload(Student.shift),
                joinedload(Student.class_rel),
                joinedload(Student.division_rel),
            )
        )
        if department_id:
            query = query.filter(Student.department_id == department_id)
        if class_id:
            query = query.filter(Student.class_id == class_id)
        if division_id:
            query = query.filter(Student.division_id == division_id)
        if user_role:
            query = query.filter(Student.user_role == user_role.strip().lower())
        if search_term:
            term = f"%{search_term.strip()}%"
            query = query.filter((Student.name.ilike(term)) | (Student.roll_number.ilike(term)))

        students = query.order_by(Student.name.asc()).all()
        return [s.to_dict() for s in students]

    def get_student_by_id(self, tenant_id: int, student_id: int) -> Student:
        student = (
            self.db.query(Student)
            .filter(Student.id == student_id, Student.tenant_id == tenant_id)
            .options(
                joinedload(Student.department_rel),
                joinedload(Student.designation_rel),
                joinedload(Student.location),
                joinedload(Student.salary_template_rel),
                joinedload(Student.shift),
            )
            .first()
        )
        if not student:
            raise HTTPException(status_code=404, detail="Student / Employee not found in this institution.")
        return student

    def transfer_department(
        self,
        tenant_id: int,
        student_id: int,
        new_department_id: int,
        transfer_reason: Optional[str] = "Department Restructuring",
        current_user: Optional[User] = None,
    ) -> Dict[str, Any]:
        student = self.get_student_by_id(tenant_id, student_id)
        dept = self.db.query(Department).filter(Department.id == new_department_id, Department.tenant_id == tenant_id).first()
        if not dept:
            raise HTTPException(status_code=404, detail="Target department not found.")

        old_dept_name = student.department or (student.department_rel.name if student.department_rel else "None")
        student.department_id = dept.id
        student.department = dept.name

        log_entry = AuditLog(
            tenant_id=tenant_id,
            user_id=current_user.id if current_user else None,
            event_type="DEPARTMENT_TRANSFER",
            description=f"Transferred '{student.name}' ({student.roll_number}) from '{old_dept_name}' to '{dept.name}'. Reason: {transfer_reason}",
            created_at=get_ist_now(),
        )
        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(student)

        return {
            "status": "success",
            "message": f"Successfully transferred {student.name} to {dept.name}.",
            "data": student.to_dict(),
        }
