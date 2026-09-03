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
    student_profile = relationship("Student", back_populates="user", uselist=False)

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
    subscription_plan = Column(String(30), default="STANDARD", nullable=False)   # FREE, STANDARD, ENTERPRISE
    subscription_status = Column(String(30), default="ACTIVE", nullable=False)   # ACTIVE, SUSPENDED, EXPIRED
    max_face_encodings = Column(Integer, default=500, nullable=False)
    max_nodes = Column(Integer, default=10, nullable=False)
    subscription_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_ist_now)

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="tenant", cascade="all, delete-orphan")
    attendance_records = relationship("AttendanceRecord", back_populates="tenant", cascade="all, delete-orphan")
    node_devices = relationship("NodeDevice", back_populates="tenant", cascade="all, delete-orphan")
    face_encodings = relationship("FaceEncoding", back_populates="tenant", cascade="all, delete-orphan")
    branding = relationship("SystemBranding", back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    academic_years = relationship("AcademicYear", back_populates="tenant", cascade="all, delete-orphan")
    classes = relationship("ClassModel", back_populates="tenant", cascade="all, delete-orphan")
    divisions = relationship("Division", back_populates="tenant", cascade="all, delete-orphan")
    teacher_assignments = relationship("TeacherClassAssignment", back_populates="tenant", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="tenant", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "contact_email": self.contact_email,
            "is_active": self.is_active,
            "subscription_plan": self.subscription_plan or "STANDARD",
            "subscription_status": self.subscription_status or "ACTIVE",
            "max_face_encodings": self.max_face_encodings or 500,
            "max_nodes": self.max_nodes or 10,
            "subscription_expires_at": self.subscription_expires_at.strftime("%Y-%m-%d") if self.subscription_expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "enrolled_faces_count": len(self.face_encodings) if self.face_encodings else 0,
            "active_nodes_count": len(self.node_devices) if self.node_devices else 0,
            "students_count": len(self.students) if self.students else 0,
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
    department = Column(String(100), default="Computer Science", nullable=False)
    name = Column(String(100), nullable=False)  # e.g. "FY Computer Science"
    code = Column(String(30), nullable=True)   # e.g. "FY-CS"
    created_at = Column(DateTime, default=get_ist_now)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tenant_class_name"),
    )

    tenant = relationship("Tenant", back_populates="classes")
    divisions = relationship("Division", back_populates="class_obj", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="class_obj", foreign_keys="[Student.class_id]")
    teacher_assignments = relationship("TeacherClassAssignment", back_populates="class_obj", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "department": self.department,
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
            "class_name": self.class_obj.name if self.class_obj else "N/A",
            "division_id": self.division_id,
            "division_name": self.division_obj.name if self.division_obj else "All Divisions",
            "academic_year_id": self.academic_year_id,
            "academic_year_name": self.academic_year.name if self.academic_year else "Current",
            "subject": self.subject,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    roll_number = Column(String(50), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    department = Column(String(100), default="Computer Science")
    email = Column(String(100), nullable=True)
    user_role = Column(String(30), default="student", nullable=False)  # student, teacher, admin_staff, other
    class_semester = Column(String(50), nullable=True, default="General")
    
    # Enhanced Academic Structure Links
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)
    division_id = Column(Integer, ForeignKey("divisions.id", ondelete="SET NULL"), nullable=True, index=True)
    academic_year_id = Column(Integer, ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Progression & Rollback History
    previous_class_id = Column(Integer, nullable=True)
    previous_division_id = Column(Integer, nullable=True)
    previous_academic_year_id = Column(Integer, nullable=True)
    last_promoted_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=get_ist_now)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "roll_number", name="uq_tenant_student_roll"),
        Index("ix_student_tenant_active", "tenant_id", "is_active"),
        Index("ix_student_class_div", "tenant_id", "class_id", "division_id"),
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="students")
    encodings = relationship("FaceEncoding", back_populates="student", cascade="all, delete-orphan")
    attendance_records = relationship("AttendanceRecord", back_populates="student", cascade="all, delete-orphan")
    class_obj = relationship("ClassModel", back_populates="students", foreign_keys=[class_id])
    division_obj = relationship("Division", back_populates="students", foreign_keys=[division_id])
    academic_year = relationship("AcademicYear", back_populates="students", foreign_keys=[academic_year_id])
    user = relationship("User", back_populates="student_profile", foreign_keys=[user_id])

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

        class_display = self.class_obj.name if self.class_obj else (self.class_semester or "General")
        division_display = self.division_obj.name if self.division_obj else "N/A"
        year_display = self.academic_year.name if self.academic_year else "Current"

        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "roll_number": self.roll_number,
            "name": self.name,
            "department": self.department,
            "email": self.email,
            "user_role": self.user_role or "student",
            "class_semester": class_display,
            "class_id": self.class_id,
            "class_name": class_display,
            "division_id": self.division_id,
            "division_name": division_display,
            "academic_year_id": self.academic_year_id,
            "academic_year_name": year_display,
            "previous_class_id": self.previous_class_id,
            "previous_division_id": self.previous_division_id,
            "previous_academic_year_id": self.previous_academic_year_id,
            "last_promoted_at": self.last_promoted_at.isoformat() if self.last_promoted_at else None,
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

    __table_args__ = (
        Index("ix_attendance_tenant_ts", "tenant_id", "timestamp"),
        Index("ix_attendance_tenant_node", "tenant_id", "node_id"),
    )

    tenant = relationship("Tenant", back_populates="attendance_records")
    student = relationship("Student", back_populates="attendance_records")

    def to_dict(self):
        class_name = self.student.class_obj.name if (self.student and self.student.class_obj) else (self.student.class_semester if self.student else "General")
        div_name = self.student.division_obj.name if (self.student and self.student.division_obj) else "N/A"
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
    primary_accent_color = Column(String(20), default="#6366f1")
    header_badge_text = Column(String(50), default="Thin-Client Hub")
    contact_email = Column(String(100), nullable=True)
    cooldown_minutes = Column(Integer, default=60, nullable=False)
    enable_anti_spoofing = Column(Boolean, default=True, nullable=False)
    liveness_mode = Column(String(20), default="BALANCED", nullable=False)
    temporal_frames_required = Column(Integer, default=3, nullable=False)
    enable_audio_chime = Column(Boolean, default=True, nullable=False)
    enable_haptic_feedback = Column(Boolean, default=True, nullable=False)
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
            "primary_accent_color": self.primary_accent_color or "#6366f1",
            "header_badge_text": self.header_badge_text or "Thin-Client Hub",
            "contact_email": self.contact_email,
            "cooldown_minutes": self.cooldown_minutes or 60,
            "enable_anti_spoofing": bool(self.enable_anti_spoofing if self.enable_anti_spoofing is not None else True),
            "liveness_mode": self.liveness_mode or "BALANCED",
            "temporal_frames_required": self.temporal_frames_required if self.temporal_frames_required is not None else 3,
            "enable_audio_chime": bool(self.enable_audio_chime),
            "enable_haptic_feedback": bool(self.enable_haptic_feedback),
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
