import json
from datetime import datetime
from typing import List, Optional, Dict, Any
import numpy as np
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Date,
    Boolean,
    ForeignKey,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship
from src.utils.timezone import get_ist_now

Base = declarative_base()


class User(Base):
    """
    User entity for Multi-Tier Role-Based Access Control (RBAC).
    Roles:
    - SUPER_ADMIN: Global control plane access across all SaaS tenants.
    - TENANT_ADMIN: Institutional Dean, Principal, or Campus Admin.
    - TEACHER: Faculty member assigned to specific classes & divisions.
    - STUDENT: Student with access to personal records and attendance turnout.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    username = Column(String(50), nullable=False, index=True)
    email = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False, default="STUDENT")  # SUPER_ADMIN, TENANT_ADMIN, TEACHER, STUDENT
    full_name = Column(String(100), nullable=False)
    phone_number = Column(String(30), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=get_ist_now)
    last_login_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_user_tenant_role", "tenant_id", "role"),
        Index("ix_user_tenant_username", "tenant_id", "username"),
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    teacher_assignments = relationship("TeacherClassAssignment", back_populates="teacher", cascade="all, delete-orphan")
    student_profile = relationship("Student", back_populates="user", uselist=False, foreign_keys="[Student.user_id]")

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "tenant_name": self.tenant.name if self.tenant else "Global Platform",
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "full_name": self.full_name,
            "phone_number": self.phone_number,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }


class Tenant(Base):
    """
    Multi-tenant Organization / Institute entity for SaaS isolation.
    """
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(50), unique=True, nullable=False, index=True)  # e.g. 'default', 'mit', 'oxford'
    name = Column(String(150), nullable=False)                          # e.g. 'FaceAttendance Campus'
    contact_email = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # SaaS Subscription & Quotas
    tenant_type = Column(String(30), default="educational", nullable=False)     # educational, corporate
    subscription_plan = Column(String(30), default="STANDARD", nullable=False)   # FREE, STANDARD, ENTERPRISE
    subscription_status = Column(String(30), default="ACTIVE", nullable=False)   # ACTIVE, SUSPENDED, EXPIRED, DELETED
    max_face_encodings = Column(Integer, default=500, nullable=False)
    max_nodes = Column(Integer, default=10, nullable=False)
    subscription_expires_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_ist_now)

    # Tokenized Corporate & Direct Access Links
    uuid = Column(String(36), unique=True, nullable=True, index=True)
    admin_token = Column(String(64), unique=True, nullable=True, index=True)
    onboarding_token = Column(String(64), unique=True, nullable=True, index=True)
    attendance_slug = Column(String(64), unique=True, nullable=True, index=True)

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="tenant", cascade="all, delete-orphan")
    attendance_records = relationship("AttendanceRecord", back_populates="tenant", cascade="all, delete-orphan")
    node_devices = relationship("NodeDevice", back_populates="tenant", cascade="all, delete-orphan")
    face_encodings = relationship("FaceEncoding", back_populates="tenant", cascade="all, delete-orphan")
    branding = relationship("SystemBranding", back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    departments = relationship("Department", back_populates="tenant", cascade="all, delete-orphan")
    academic_years = relationship("AcademicYear", back_populates="tenant", cascade="all, delete-orphan")
    classes = relationship("ClassModel", back_populates="tenant", cascade="all, delete-orphan")
    divisions = relationship("Division", back_populates="tenant", cascade="all, delete-orphan")
    teacher_assignments = relationship("TeacherClassAssignment", back_populates="tenant", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="tenant", cascade="all, delete-orphan")
    batch_uploads = relationship("StudentBatchUpload", back_populates="tenant", cascade="all, delete-orphan")
    leave_types = relationship("LeaveType", back_populates="tenant", cascade="all, delete-orphan")
    leave_cadre_quotas = relationship("LeaveCadreQuota", back_populates="tenant", cascade="all, delete-orphan")
    leave_balances = relationship("LeaveBalance", back_populates="tenant", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="tenant", cascade="all, delete-orphan")

    def to_dict(self):
        t_uuid = self.uuid or self.slug
        admin_login_path = f"/auth/token-login/{t_uuid}/{self.admin_token}" if (t_uuid and self.admin_token) else None
        onboarding_path = f"/onboard/{t_uuid}/{self.onboarding_token}" if (t_uuid and self.onboarding_token) else None
        checkin_path = f"/check-in/{t_uuid}/{self.attendance_slug}" if (t_uuid and self.attendance_slug) else f"/self-attendance/{self.slug}"

        return {
            "id": self.id,
            "uuid": self.uuid,
            "slug": self.slug,
            "name": self.name,
            "tenant_type": self.tenant_type or "educational",
            "contact_email": self.contact_email,
            "is_active": self.is_active,
            "is_deleted": bool(self.is_deleted),
            "deleted_at": self.deleted_at.strftime("%Y-%m-%d %H:%M:%S") if self.deleted_at else None,
            "subscription_plan": self.subscription_plan or "STANDARD",
            "subscription_status": self.subscription_status or "ACTIVE",
            "max_face_encodings": self.max_face_encodings or 500,
            "max_nodes": self.max_nodes or 10,
            "subscription_expires_at": self.subscription_expires_at.strftime("%Y-%m-%d") if self.subscription_expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "admin_token": self.admin_token,
            "onboarding_token": self.onboarding_token,
            "attendance_slug": self.attendance_slug,
            "portal_url": f"/portal/{self.slug}",
            "tenant_login_url": f"/portal/{self.slug}",
            "tokenized_portal_url": f"/portal/{t_uuid}/{self.admin_token}" if (t_uuid and self.admin_token) else f"/portal/{self.slug}",
            "admin_login_url": admin_login_path,
            "onboarding_url": onboarding_path,
            "checkin_url": checkin_path,
            "enrolled_faces_count": len(self.face_encodings) if self.face_encodings else 0,
            "active_nodes_count": len(self.node_devices) if self.node_devices else 0,
            "students_count": len(self.students) if self.students else 0,
        }


class Department(Base):
    """
    Institutional Department entity per tenant (e.g. 'Computer Science', 'Information Technology').
    """
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(30), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_ist_now)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tenant_department_name"),
    )

    tenant = relationship("Tenant", back_populates="departments")
    classes = relationship("ClassModel", back_populates="department_rel")
    students = relationship("Student", back_populates="department_rel")

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "code": self.code or self.name[:6].upper(),
            "description": self.description or "",
            "classes_count": len(self.classes) if self.classes else 0,
            "students_count": len(self.students) if self.students else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AcademicYear(Base):
    """
    Academic Year entity per tenant (e.g. '2025-2026', '2026-2027').
    """
    __tablename__ = "academic_years"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    name = Column(String(50), nullable=False)  # e.g. "2026-2027"
    is_current = Column(Boolean, default=True, nullable=False)
    start_date = Column(String(30), nullable=True)
    end_date = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=get_ist_now)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tenant_academic_year"),
    )

    tenant = relationship("Tenant", back_populates="academic_years")
    students = relationship("Student", back_populates="academic_year")

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "is_current": self.is_current,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ClassModel(Base):
    """
    Institutional Class / Course / Semester entity (e.g. 'FY Computer Science', 'SY IT').
    """
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    department = Column(String(100), default="Computer Science", nullable=False)
    name = Column(String(100), nullable=False)  # e.g. "FY Computer Science"
    code = Column(String(30), nullable=True)   # e.g. "FY-CS"
    created_at = Column(DateTime, default=get_ist_now)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tenant_class_name"),
    )

    tenant = relationship("Tenant", back_populates="classes")
    department_rel = relationship("Department", back_populates="classes")
    divisions = relationship("Division", back_populates="class_obj", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="class_obj", foreign_keys="[Student.class_id]")
    teacher_assignments = relationship("TeacherClassAssignment", back_populates="class_obj", cascade="all, delete-orphan")

    def to_dict(self):
        dept_name = self.department_rel.name if self.department_rel else (self.department or "Computer Science")
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "department_id": self.department_id,
            "department": dept_name,
            "department_code": self.department_rel.code if self.department_rel else "",
            "name": self.name,
            "code": self.code or self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "divisions": [d.to_dict() for d in (self.divisions or [])],
            "students_count": len(self.students) if self.students else 0,
        }


class Division(Base):
    """
    Class Section / Division entity (e.g. 'Division A', 'Division B', 'Batch 1').
    """
    __tablename__ = "divisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(50), nullable=False)  # e.g. "Division A"
    created_at = Column(DateTime, default=get_ist_now)

    __table_args__ = (
        UniqueConstraint("tenant_id", "class_id", "name", name="uq_tenant_class_division"),
    )

    tenant = relationship("Tenant", back_populates="divisions")
    class_obj = relationship("ClassModel", back_populates="divisions")
    students = relationship("Student", back_populates="division_obj", foreign_keys="[Student.division_id]")
    teacher_assignments = relationship("TeacherClassAssignment", back_populates="division_obj", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "class_id": self.class_id,
            "class_name": self.class_obj.name if self.class_obj else "Unknown Class",
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "students_count": len(self.students) if self.students else 0,
        }


class TeacherClassAssignment(Base):
    """
    Mapping between Faculty (User with role TEACHER) and assigned Classes / Divisions.
    """
    __tablename__ = "teacher_class_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    division_id = Column(Integer, ForeignKey("divisions.id", ondelete="CASCADE"), nullable=True, index=True)
    academic_year_id = Column(Integer, ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=True, index=True)
    subject = Column(String(100), default="General", nullable=False)
    created_at = Column(DateTime, default=get_ist_now)

    __table_args__ = (
        Index("ix_teacher_assign_tenant_user", "tenant_id", "teacher_id"),
    )

    tenant = relationship("Tenant", back_populates="teacher_assignments")
    teacher = relationship("User", back_populates="teacher_assignments")
    class_obj = relationship("ClassModel", back_populates="teacher_assignments")
    division_obj = relationship("Division", back_populates="teacher_assignments")
    academic_year = relationship("AcademicYear")

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "teacher_id": self.teacher_id,
            "teacher_name": self.teacher.full_name if self.teacher else "Unknown Teacher",
            "teacher_username": self.teacher.username if self.teacher else "N/A",
            "class_id": self.class_id,
            "class_name": self.class_obj.name if self.class_obj else "Unknown Class",
            "division_id": self.division_id,
            "division_name": self.division_obj.name if self.division_obj else "All Divisions",
            "academic_year_id": self.academic_year_id,
            "academic_year_name": self.academic_year.name if self.academic_year else "Current",
            "subject": self.subject,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class StudentBatchUpload(Base):
    """
    Tracks bulk Excel spreadsheet upload sessions with validation statistics and soft-delete/rollback support.
    """
    __tablename__ = "student_batch_uploads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    total_rows = Column(Integer, default=0)
    valid_rows = Column(Integer, default=0)
    imported_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, nullable=False)  # False when batch is rolled back / soft-deleted
    created_at = Column(DateTime, default=get_ist_now)

    # Relationships
    tenant = relationship("Tenant", back_populates="batch_uploads")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_user_id])
    students = relationship("Student", back_populates="batch_upload", foreign_keys="Student.batch_upload_id")

    def to_dict(self):
        active_student_count = sum(1 for s in (self.students or []) if s.is_active)
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "filename": self.filename,
            "uploaded_by_user_id": self.uploaded_by_user_id,
            "uploader_name": self.uploaded_by.full_name if self.uploaded_by else "Admin",
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "imported_count": self.imported_count,
            "active_student_count": active_student_count,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    roll_number = Column(String(50), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    gender = Column(String(20), nullable=True, default="Other")  # Male, Female, Other
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    department = Column(String(100), default="Computer Science")
    email = Column(String(100), nullable=True)
    phone_number = Column(String(50), nullable=True)
    user_role = Column(String(30), default="student", nullable=False)  # student, teacher, admin_staff, other
    class_semester = Column(String(50), nullable=True, default="General")
    
    # Enhanced Academic Structure Links
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)
    division_id = Column(Integer, ForeignKey("divisions.id", ondelete="SET NULL"), nullable=True, index=True)
    academic_year_id = Column(Integer, ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    batch_upload_id = Column(Integer, ForeignKey("student_batch_uploads.id", ondelete="SET NULL"), nullable=True, index=True)

    # Progression & Transfer Tracking History
    previous_department_id = Column(Integer, nullable=True)
    previous_class_id = Column(Integer, nullable=True)
    previous_division_id = Column(Integer, nullable=True)
    previous_academic_year_id = Column(Integer, nullable=True)
    last_promoted_at = Column(DateTime, nullable=True)
    last_transferred_at = Column(DateTime, nullable=True)

    # Corporate Compensation & Cadre Attributes
    hourly_rate = Column(Float, nullable=True)
    monthly_base_salary = Column(Float, nullable=True)
    cadre_level = Column(String(50), nullable=True)
    date_of_joining = Column(Date, nullable=True)

    # Offboarding / Relieving Status & Audit
    employment_status = Column(String(30), default="ACTIVE", nullable=False)  # ACTIVE, RELIEVED, TERMINATED, RESIGNED
    relieved_at = Column(DateTime, nullable=True)
    relieving_reason = Column(Text, nullable=True)
    relieved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=get_ist_now)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "roll_number", name="uq_tenant_student_roll"),
        Index("ix_student_tenant_active", "tenant_id", "is_active"),
        Index("ix_student_tenant_status", "tenant_id", "employment_status"),
        Index("ix_student_class_div", "tenant_id", "class_id", "division_id"),
        Index("ix_student_batch", "tenant_id", "batch_upload_id"),
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="students")
    department_rel = relationship("Department", back_populates="students", foreign_keys=[department_id])
    encodings = relationship("FaceEncoding", back_populates="student", cascade="all, delete-orphan")
    attendance_records = relationship("AttendanceRecord", back_populates="student", cascade="all, delete-orphan")
    class_obj = relationship("ClassModel", back_populates="students", foreign_keys=[class_id])
    division_obj = relationship("Division", back_populates="students", foreign_keys=[division_id])
    academic_year = relationship("AcademicYear", back_populates="students", foreign_keys=[academic_year_id])
    user = relationship("User", back_populates="student_profile", foreign_keys=[user_id])
    batch_upload = relationship("StudentBatchUpload", back_populates="students", foreign_keys=[batch_upload_id])
    relieved_by_user = relationship("User", foreign_keys=[relieved_by_user_id])
    leave_balances = relationship("LeaveBalance", back_populates="student", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="student", cascade="all, delete-orphan")

    def to_dict(self):
        photos_list = []
        for enc in (self.encodings or []):
            if enc.photo_path:
                clean_path = enc.photo_path.replace("\\", "/").lstrip("/")
                if not clean_path.startswith("faces/"):
                    clean_path = f"faces/{clean_path}"
                url = f"/data/{clean_path}"
            else:
                url = None
            photos_list.append({
                "id": enc.id,
                "angle": enc.sample_angle,
                "url": url,
                "created_at": enc.created_at.isoformat() if enc.created_at else None,
            })

        dept_display = self.department_rel.name if self.department_rel else (self.department or "Computer Science")
        class_display = self.class_obj.name if self.class_obj else (self.class_semester or "General")
        division_display = self.division_obj.name if self.division_obj else "N/A"
        year_display = self.academic_year.name if self.academic_year else "Current"

        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "roll_number": self.roll_number,
            "name": self.name,
            "gender": self.gender or "Other",
            "department_id": self.department_id,
            "department": dept_display,
            "department_code": self.department_rel.code if self.department_rel else "",
            "email": self.email,
            "phone_number": self.phone_number,
            "user_role": self.user_role or "student",
            "role": self.user_role or "student",
            "class_semester": class_display,
            "class_id": self.class_id,
            "class_name": class_display,
            "division_id": self.division_id,
            "division_name": division_display,
            "academic_year_id": self.academic_year_id,
            "academic_year_name": year_display,
            "batch_upload_id": self.batch_upload_id,
            "previous_department_id": self.previous_department_id,
            "previous_class_id": self.previous_class_id,
            "previous_division_id": self.previous_division_id,
            "previous_academic_year_id": self.previous_academic_year_id,
            "last_promoted_at": self.last_promoted_at.isoformat() if self.last_promoted_at else None,
            "last_transferred_at": self.last_transferred_at.isoformat() if self.last_transferred_at else None,
            "hourly_rate": self.hourly_rate,
            "monthly_base_salary": self.monthly_base_salary,
            "cadre_level": self.cadre_level,
            "date_of_joining": self.date_of_joining.strftime("%Y-%m-%d") if self.date_of_joining else None,
            "employment_status": self.employment_status or ("ACTIVE" if self.is_active else "RELIEVED"),
            "relieved_at": self.relieved_at.strftime("%Y-%m-%d %H:%M:%S") if self.relieved_at else None,
            "relieving_reason": self.relieving_reason or "",
            "relieved_by_user_id": self.relieved_by_user_id,
            "relieved_by_name": self.relieved_by_user.full_name if self.relieved_by_user else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active,
            "samples_count": len(self.encodings) if self.encodings else 0,
            "photos": photos_list,
        }


class FaceEncoding(Base):
    __tablename__ = "face_encodings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    sample_angle = Column(String(20), default="frontal")  # frontal, left, right, etc.
    vector_json = Column(Text, nullable=False)            # 128 float values as JSON list
    photo_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=get_ist_now)

    __table_args__ = (
        Index("ix_face_enc_tenant_student", "tenant_id", "student_id"),
    )

    tenant = relationship("Tenant", back_populates="face_encodings")
    student = relationship("Student", back_populates="encodings")

    def get_numpy_vector(self) -> np.ndarray:
        """Parses stored JSON back into 128-d float64 numpy array."""
        return np.array(json.loads(self.vector_json), dtype=np.float64)

    @classmethod
    def from_numpy(cls, student_id: int, vector: np.ndarray, sample_angle: str = "frontal", photo_path: str = None, tenant_id: int = 1):
        """Creates FaceEncoding instance from numpy array."""
        return cls(
            tenant_id=tenant_id,
            student_id=student_id,
            sample_angle=sample_angle,
            vector_json=json.dumps(vector.tolist()),
            photo_path=photo_path,
        )


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=True, index=True)
    node_id = Column(String(50), nullable=False, default="NODE-CLASSROOM-101", index=True)
    timestamp = Column(DateTime, default=get_ist_now, index=True)
    confidence_distance = Column(Float, nullable=False)
    status = Column(String(20), default="PRESENT")  # PRESENT, UNKNOWN
    snapshot_path = Column(String(255), nullable=True)
    is_manual_override = Column(Boolean, default=False, nullable=False)
    override_reason = Column(String(255), nullable=True)
    override_by = Column(String(100), nullable=True)
    geo_latitude = Column(Float, nullable=True)
    geo_longitude = Column(Float, nullable=True)
    geo_distance_meters = Column(Float, nullable=True)
    is_self_attendance = Column(Boolean, default=False, nullable=False)

    # Corporate Check-In / Check-Out and Shift Tracking
    punch_type = Column(String(20), default="CHECK_IN", nullable=False)  # CHECK_IN, CHECK_OUT, ATTENDANCE
    check_in_time = Column(DateTime, nullable=True)
    check_out_time = Column(DateTime, nullable=True)
    work_duration_minutes = Column(Integer, nullable=True)
    shift_status = Column(String(30), default="ON_TIME", nullable=False)  # ON_TIME, LATE_CHECKIN, EARLY_DEPARTURE, MISSED_CHECKOUT, COMPLETED, PRESENT

    __table_args__ = (
        Index("ix_attendance_tenant_ts", "tenant_id", "timestamp"),
        Index("ix_attendance_tenant_node", "tenant_id", "node_id"),
        Index("ix_attendance_student_date", "tenant_id", "student_id", "timestamp"),
    )

    tenant = relationship("Tenant", back_populates="attendance_records")
    student = relationship("Student", back_populates="attendance_records")

    @property
    def work_duration_formatted(self) -> str:
        if self.work_duration_minutes is not None:
            hrs = int(self.work_duration_minutes // 60)
            mins = int(self.work_duration_minutes % 60)
            return f"{hrs}h {mins:02d}m" if hrs > 0 else f"{mins}m"
        elif self.check_in_time and self.check_out_time:
            secs = int((self.check_out_time - self.check_in_time).total_seconds())
            if secs >= 0:
                mins = secs // 60
                hrs = mins // 60
                rem_mins = mins % 60
                return f"{hrs}h {rem_mins:02d}m" if hrs > 0 else f"{mins}m"
        return "--"

    def to_dict(self):
        class_name = self.student.class_obj.name if (self.student and self.student.class_obj) else (self.student.class_semester if self.student else "General")
        div_name = self.student.division_obj.name if (self.student and self.student.division_obj) else "N/A"
        
        c_in = self.check_in_time or self.timestamp
        c_in_str = c_in.strftime("%Y-%m-%d %H:%M:%S") if c_in else None
        c_in_short = c_in.strftime("%I:%M %p") if c_in else "N/A"
        
        c_out_str = self.check_out_time.strftime("%Y-%m-%d %H:%M:%S") if self.check_out_time else None
        c_out_short = self.check_out_time.strftime("%I:%M %p") if self.check_out_time else "--"

        duration_formatted = self.work_duration_formatted

        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "student_id": self.student_id,
            "student_name": self.student.name if self.student else "Unknown",
            "roll_number": self.student.roll_number if self.student else "N/A",
            "department": self.student.department if self.student else "N/A",
            "user_role": self.student.user_role if self.student else "student",
            "class_semester": class_name,
            "division_name": div_name,
            "node_id": self.node_id,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else None,
            "confidence_distance": round(self.confidence_distance, 4) if self.confidence_distance is not None else 0.0,
            "match_confidence_pct": round(max(0.0, (1.0 - (self.confidence_distance / 0.6))) * 100, 1) if self.confidence_distance is not None else 0.0,
            "status": self.status,
            "snapshot_path": self.snapshot_path,
            "is_manual_override": bool(self.is_manual_override),
            "override_reason": self.override_reason,
            "override_by": self.override_by,
            "geo_latitude": self.geo_latitude,
            "geo_longitude": self.geo_longitude,
            "geo_distance_meters": round(self.geo_distance_meters, 1) if self.geo_distance_meters is not None else None,
            "is_self_attendance": bool(self.is_self_attendance),
            "punch_type": self.punch_type or "CHECK_IN",
            "check_in_time": c_in_str,
            "check_in_short": c_in_short,
            "check_out_time": c_out_str,
            "check_out_short": c_out_short,
            "work_duration_minutes": self.work_duration_minutes,
            "work_duration_formatted": duration_formatted,
            "shift_status": self.shift_status or "ON_TIME",
        }


class NodeDevice(Base):
    __tablename__ = "node_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    node_id = Column(String(50), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    location = Column(String(100), default="Classroom")
    last_heartbeat = Column(DateTime, default=get_ist_now)
    is_online = Column(Boolean, default=True)
    fps = Column(Float, default=2.0)
    total_detections = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("tenant_id", "node_id", name="uq_tenant_node_id"),
    )

    tenant = relationship("Tenant", back_populates="node_devices")

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "node_id": self.node_id,
            "name": self.name,
            "location": self.location,
            "last_heartbeat": self.last_heartbeat.strftime("%Y-%m-%d %H:%M:%S") if self.last_heartbeat else None,
            "is_online": self.is_online,
            "fps": self.fps,
            "total_detections": self.total_detections,
        }


class SystemBranding(Base):
    __tablename__ = "system_branding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, default=1, unique=True, index=True)
    institution_name = Column(String(150), default="FaceAttendance Campus", nullable=False)
    short_code = Column(String(30), default="FA-HUB", nullable=False)
    tagline = Column(String(255), default="Raspberry Pi Zero Edge Nodes & Central Face Recognition")
    logo_filename = Column(String(255), nullable=True)
    primary_accent_color = Column(String(20), default="#c2410c")
    header_badge_text = Column(String(50), default="Thin-Client Hub")
    contact_email = Column(String(100), nullable=True)
    cooldown_minutes = Column(Integer, default=60, nullable=False)
    enable_anti_spoofing = Column(Boolean, default=False, nullable=False)
    liveness_mode = Column(String(20), default="off", nullable=False)
    temporal_frames_required = Column(Integer, default=3, nullable=False)
    enable_audio_chime = Column(Boolean, default=True, nullable=False)
    enable_haptic_feedback = Column(Boolean, default=True, nullable=False)
    enable_self_attendance = Column(Boolean, default=False, nullable=False)
    geo_latitude = Column(Float, nullable=True)
    geo_longitude = Column(Float, nullable=True)
    geo_radius_meters = Column(Float, default=150.0, nullable=False)
    max_gps_accuracy_meters = Column(Float, default=50.0, nullable=False)
    self_attendance_face_threshold = Column(Float, default=0.52, nullable=False)
    
    # Corporate Shift Configuration (Default: 10:30 AM Check-In, 6:00 PM Check-Out, 15m Grace)
    shift_check_in_time = Column(String(10), default="10:30", nullable=False)
    shift_check_out_time = Column(String(10), default="18:00", nullable=False)
    shift_grace_minutes = Column(Integer, default=15, nullable=False)
    min_checkout_interval_minutes = Column(Integer, default=15, nullable=False)

    # Corporate Payroll & Wage Configuration
    payroll_structure = Column(String(30), default="HOURLY", nullable=False)  # HOURLY, MONTHLY_CADRE, HYBRID
    default_hourly_rate = Column(Float, default=15.0, nullable=True)
    standard_working_hours_per_day = Column(Float, default=8.0, nullable=True)
    enable_overtime = Column(Boolean, default=True, nullable=False)
    overtime_rate_multiplier = Column(Float, default=1.5, nullable=True)
    missed_checkout_policy = Column(String(30), default="HALF_DAY", nullable=False)  # HALF_DAY, ZERO_HOURS, STANDARD_SHIFT
    currency_symbol = Column(String(10), default="$", nullable=False)

    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now)

    tenant = relationship("Tenant", back_populates="branding")

    def to_dict(self):
        logo_url = f"/data/branding/{self.logo_filename}" if self.logo_filename else None
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "institution_name": self.institution_name,
            "short_code": self.short_code,
            "tagline": self.tagline,
            "logo_filename": self.logo_filename,
            "logo_url": logo_url,
            "primary_accent_color": self.primary_accent_color or "#c2410c",
            "header_badge_text": self.header_badge_text or "Thin-Client Hub",
            "contact_email": self.contact_email,
            "cooldown_minutes": self.cooldown_minutes or 60,
            "enable_anti_spoofing": bool(self.enable_anti_spoofing if self.enable_anti_spoofing is not None else False),
            "liveness_mode": self.liveness_mode or "off",
            "temporal_frames_required": self.temporal_frames_required if self.temporal_frames_required is not None else 3,
            "enable_audio_chime": bool(self.enable_audio_chime),
            "enable_haptic_feedback": bool(self.enable_haptic_feedback),
            "enable_self_attendance": bool(self.enable_self_attendance if self.enable_self_attendance is not None else False),
            "geo_latitude": self.geo_latitude,
            "geo_longitude": self.geo_longitude,
            "geo_radius_meters": float(self.geo_radius_meters if self.geo_radius_meters is not None else 150.0),
            "max_gps_accuracy_meters": float(self.max_gps_accuracy_meters if self.max_gps_accuracy_meters is not None else 50.0),
            "self_attendance_face_threshold": float(self.self_attendance_face_threshold if self.self_attendance_face_threshold is not None else 0.52),
            "shift_check_in_time": self.shift_check_in_time or "10:30",
            "shift_check_out_time": self.shift_check_out_time or "18:00",
            "shift_grace_minutes": self.shift_grace_minutes if self.shift_grace_minutes is not None else 15,
            "min_checkout_interval_minutes": self.min_checkout_interval_minutes if self.min_checkout_interval_minutes is not None else 15,
            "payroll_structure": self.payroll_structure or "HOURLY",
            "default_hourly_rate": float(self.default_hourly_rate if self.default_hourly_rate is not None else 15.0),
            "standard_working_hours_per_day": float(self.standard_working_hours_per_day if self.standard_working_hours_per_day is not None else 8.0),
            "enable_overtime": bool(self.enable_overtime if self.enable_overtime is not None else True),
            "overtime_rate_multiplier": float(self.overtime_rate_multiplier if self.overtime_rate_multiplier is not None else 1.5),
            "missed_checkout_policy": self.missed_checkout_policy or "HALF_DAY",
            "currency_symbol": self.currency_symbol or "$",
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class AuditLog(Base):
    """
    Platform and Institutional Audit Trail entity.
    Tracks administrative events like promotions, rollbacks, quota modifications, role adjustments, tenant suspensions.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_name = Column(String(100), nullable=False)
    actor_role = Column(String(30), nullable=False)
    action_type = Column(String(50), nullable=False, index=True)  # TENANT_CREATED, TENANT_SUSPENDED, STUDENT_PROMOTED, PROMOTION_ROLLBACK, etc.
    target_type = Column(String(50), nullable=True)              # TENANT, STUDENT, CLASS, TEACHER, QUOTA
    target_id = Column(String(50), nullable=True)
    description = Column(Text, nullable=False)
    ip_address = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=get_ist_now, index=True)

    __table_args__ = (
        Index("ix_audit_tenant_action", "tenant_id", "action_type"),
    )

    tenant = relationship("Tenant", back_populates="audit_logs")
    user = relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "tenant_name": self.tenant.name if self.tenant else "Global Platform",
            "user_id": self.user_id,
            "actor_name": self.actor_name,
            "actor_role": self.actor_role,
            "action_type": self.action_type,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "description": self.description,
            "ip_address": self.ip_address,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else None,
        }


class SubscriptionPlan(Base):
    """
    SaaS Subscription Tier Plan configuration.
    Defines available tiers (FREE, STANDARD, ENTERPRISE, CUSTOM) with default quota ceilings.
    """
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_code = Column(String(30), unique=True, nullable=False, index=True)  # FREE, STANDARD, ENTERPRISE, PRO
    name = Column(String(100), nullable=False)                               # Free Starter, Standard Campus, Enterprise Hub
    max_face_encodings = Column(Integer, default=500, nullable=False)
    max_nodes = Column(Integer, default=10, nullable=False)
    price_monthly = Column(Float, default=0.0, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=get_ist_now)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now)

    def to_dict(self):
        return {
            "id": self.id,
            "plan_code": self.plan_code,
            "name": self.name,
            "max_face_encodings": self.max_face_encodings,
            "max_nodes": self.max_nodes,
            "price_monthly": self.price_monthly,
            "description": self.description or "",
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class LeaveType(Base):
    """
    Leave Type master configuration per tenant (e.g. Casual Leave, Medical Leave, Earned Leave, Unpaid Leave).
    """
    __tablename__ = "leave_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)           # e.g., "Casual Leave"
    code = Column(String(20), nullable=False)            # e.g., "CL"
    description = Column(Text, nullable=True)
    is_paid = Column(Boolean, default=True, nullable=False)
    default_days_per_year = Column(Float, default=12.0, nullable=False)
    accrual_frequency = Column(String(20), default="ANNUAL", nullable=False) # ANNUAL, MONTHLY
    requires_document = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=get_ist_now)

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_tenant_leave_code"),
        Index("ix_leave_type_tenant_active", "tenant_id", "is_active"),
    )

    tenant = relationship("Tenant", back_populates="leave_types")
    cadre_quotas = relationship("LeaveCadreQuota", back_populates="leave_type", cascade="all, delete-orphan")
    balances = relationship("LeaveBalance", back_populates="leave_type", cascade="all, delete-orphan")
    requests = relationship("LeaveRequest", back_populates="leave_type", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "code": self.code,
            "description": self.description or "",
            "is_paid": bool(self.is_paid),
            "default_days_per_year": float(self.default_days_per_year if self.default_days_per_year is not None else 12.0),
            "accrual_frequency": self.accrual_frequency or "ANNUAL",
            "requires_document": bool(self.requires_document),
            "is_active": bool(self.is_active),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "cadre_quotas": [q.to_dict() for q in (self.cadre_quotas or [])],
        }


class LeaveCadreQuota(Base):
    """
    Cadre/Role-based quota override for a specific leave type within a tenant.
    """
    __tablename__ = "leave_cadre_quotas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False, index=True)
    cadre_level = Column(String(50), nullable=False)     # e.g., "Executive", "Senior Manager", "Staff", "Intern"
    allocated_days = Column(Float, default=12.0, nullable=False)
    created_at = Column(DateTime, default=get_ist_now)

    __table_args__ = (
        UniqueConstraint("tenant_id", "leave_type_id", "cadre_level", name="uq_tenant_leave_cadre"),
    )

    tenant = relationship("Tenant", back_populates="leave_cadre_quotas")
    leave_type = relationship("LeaveType", back_populates="cadre_quotas")

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "leave_type_id": self.leave_type_id,
            "leave_type_name": self.leave_type.name if self.leave_type else "",
            "leave_type_code": self.leave_type.code if self.leave_type else "",
            "cadre_level": self.cadre_level,
            "allocated_days": float(self.allocated_days if self.allocated_days is not None else 0.0),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }


class LeaveBalance(Base):
    """
    Real-time leave balance tracker per employee, leave type, and calendar year.
    """
    __tablename__ = "leave_balances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False, index=True)
    year = Column(Integer, nullable=False)               # e.g. 2026
    total_allocated = Column(Float, default=0.0, nullable=False)
    used_days = Column(Float, default=0.0, nullable=False)
    pending_days = Column(Float, default=0.0, nullable=False)
    remaining_days = Column(Float, default=0.0, nullable=False)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now)

    __table_args__ = (
        UniqueConstraint("tenant_id", "student_id", "leave_type_id", "year", name="uq_tenant_student_leave_year"),
        Index("ix_leave_balance_student_year", "tenant_id", "student_id", "year"),
    )

    tenant = relationship("Tenant", back_populates="leave_balances")
    student = relationship("Student", back_populates="leave_balances")
    leave_type = relationship("LeaveType", back_populates="balances")

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "student_id": self.student_id,
            "student_name": self.student.name if self.student else "",
            "roll_number": self.student.roll_number if self.student else "",
            "department": self.student.department if self.student else "",
            "cadre_level": self.student.cadre_level if self.student else "",
            "leave_type_id": self.leave_type_id,
            "leave_type_name": self.leave_type.name if self.leave_type else "",
            "leave_type_code": self.leave_type.code if self.leave_type else "",
            "is_paid": bool(self.leave_type.is_paid) if self.leave_type else True,
            "year": self.year,
            "total_allocated": float(self.total_allocated if self.total_allocated is not None else 0.0),
            "used_days": float(self.used_days if self.used_days is not None else 0.0),
            "pending_days": float(self.pending_days if self.pending_days is not None else 0.0),
            "remaining_days": float(self.remaining_days if self.remaining_days is not None else 0.0),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class LeaveRequest(Base):
    """
    Employee Leave Application and Admin Approval Request.
    """
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_half_day = Column(Boolean, default=False, nullable=False)
    half_day_period = Column(String(20), default="NONE", nullable=False) # NONE, FIRST_HALF, SECOND_HALF
    total_days = Column(Float, default=1.0, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(30), default="PENDING", nullable=False)       # PENDING, APPROVED, REJECTED, CANCELLED
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    admin_remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_ist_now)

    __table_args__ = (
        Index("ix_leave_req_tenant_status", "tenant_id", "status"),
        Index("ix_leave_req_student_dates", "tenant_id", "student_id", "start_date", "end_date"),
    )

    tenant = relationship("Tenant", back_populates="leave_requests")
    student = relationship("Student", back_populates="leave_requests")
    leave_type = relationship("LeaveType", back_populates="requests")
    reviewed_by_user = relationship("User", foreign_keys=[reviewed_by_user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "student_id": self.student_id,
            "student_name": self.student.name if self.student else "",
            "roll_number": self.student.roll_number if self.student else "",
            "department": self.student.department if self.student else "",
            "cadre_level": self.student.cadre_level if self.student else "",
            "leave_type_id": self.leave_type_id,
            "leave_type_name": self.leave_type.name if self.leave_type else "",
            "leave_type_code": self.leave_type.code if self.leave_type else "",
            "is_paid": bool(self.leave_type.is_paid) if self.leave_type else True,
            "start_date": self.start_date.strftime("%Y-%m-%d") if self.start_date else None,
            "end_date": self.end_date.strftime("%Y-%m-%d") if self.end_date else None,
            "is_half_day": bool(self.is_half_day),
            "half_day_period": self.half_day_period or "NONE",
            "total_days": float(self.total_days if self.total_days is not None else 1.0),
            "reason": self.reason or "",
            "status": self.status or "PENDING",
            "reviewed_by_user_id": self.reviewed_by_user_id,
            "reviewer_name": self.reviewed_by_user.full_name if self.reviewed_by_user else (self.reviewed_by_user.username if self.reviewed_by_user else None),
            "reviewed_at": self.reviewed_at.strftime("%Y-%m-%d %H:%M:%S") if self.reviewed_at else None,
            "admin_remarks": self.admin_remarks or "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }


