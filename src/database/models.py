import json
from datetime import datetime
from typing import List, Optional
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
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    roll_number = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    department = Column(String(100), default="Computer Science")
    email = Column(String(100), nullable=True)
    user_role = Column(String(30), default="student", nullable=False)  # student, teacher, admin_staff, other
    class_semester = Column(String(50), nullable=True, default="General")
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    encodings = relationship("FaceEncoding", back_populates="student", cascade="all, delete-orphan")
    attendance_records = relationship("AttendanceRecord", back_populates="student", cascade="all, delete-orphan")

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

        return {
            "id": self.id,
            "roll_number": self.roll_number,
            "name": self.name,
            "department": self.department,
            "email": self.email,
            "user_role": self.user_role or "student",
            "class_semester": self.class_semester or "General",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active,
            "samples_count": len(self.encodings) if self.encodings else 0,
            "photos": photos_list,
        }


class FaceEncoding(Base):
    __tablename__ = "face_encodings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    sample_angle = Column(String(20), default="frontal")  # frontal, left, right, etc.
    vector_json = Column(Text, nullable=False)            # 128 float values as JSON list
    photo_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="encodings")

    def get_numpy_vector(self) -> np.ndarray:
        """Parses stored JSON back into 128-d float64 numpy array."""
        return np.array(json.loads(self.vector_json), dtype=np.float64)

    @classmethod
    def from_numpy(cls, student_id: int, vector: np.ndarray, sample_angle: str = "frontal", photo_path: str = None):
        """Creates FaceEncoding instance from numpy array."""
        return cls(
            student_id=student_id,
            sample_angle=sample_angle,
            vector_json=json.dumps(vector.tolist()),
            photo_path=photo_path,
        )


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True, index=True)
    node_id = Column(String(50), nullable=False, default="NODE-CLASSROOM-101", index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    confidence_distance = Column(Float, nullable=False)
    status = Column(String(20), default="PRESENT")  # PRESENT, UNKNOWN
    snapshot_path = Column(String(255), nullable=True)
    is_manual_override = Column(Boolean, default=False, nullable=False)
    override_reason = Column(String(255), nullable=True)
    override_by = Column(String(100), nullable=True)

    student = relationship("Student", back_populates="attendance_records")

    def to_dict(self):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "student_name": self.student.name if self.student else "Unknown",
            "roll_number": self.student.roll_number if self.student else "N/A",
            "department": self.student.department if self.student else "N/A",
            "user_role": self.student.user_role if self.student else "student",
            "class_semester": self.student.class_semester if self.student else "General",
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

    node_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    location = Column(String(100), default="Classroom")
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    is_online = Column(Boolean, default=True)
    fps = Column(Float, default=2.0)
    total_detections = Column(Integer, default=0)

    def to_dict(self):
        return {
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
    institution_name = Column(String(150), default="FaceAttendance Campus", nullable=False)
    short_code = Column(String(30), default="FA-HUB", nullable=False)
    tagline = Column(String(255), default="Raspberry Pi Zero Edge Nodes & Central Face Recognition")
    logo_filename = Column(String(255), nullable=True)
    primary_accent_color = Column(String(20), default="#6366f1")
    header_badge_text = Column(String(50), default="Thin-Client Hub")
    contact_email = Column(String(100), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        logo_url = f"/data/branding/{self.logo_filename}" if self.logo_filename else None
        return {
            "id": self.id,
            "institution_name": self.institution_name,
            "short_code": self.short_code,
            "tagline": self.tagline,
            "logo_filename": self.logo_filename,
            "logo_url": logo_url,
            "primary_accent_color": self.primary_accent_color or "#6366f1",
            "header_badge_text": self.header_badge_text or "Thin-Client Hub",
            "contact_email": self.contact_email,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

