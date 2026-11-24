"""
Attendance Service
Handles punch processing, shift reconciliation, manual overrides,
attendance logging, analytics aggregation, and export generation.
"""

import io
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session, joinedload
from openpyxl.styles import Font, PatternFill, Alignment
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

from src.core.attendance_manager import attendance_manager
from src.database.models import (
    AttendanceRecord,
    Student,
    Tenant,
    SystemBranding,
    WorkShift,
    Department,
    EmployeeGeofenceBreach,
)
from src.utils.geo_utils import validate_geofence, haversine_distance
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
                AttendanceRecord.is_deleted == False,
                AttendanceRecord.timestamp.between(start_today, end_today),
            )
            .order_by(AttendanceRecord.timestamp.desc())
            .first()
        )

        should_checkout = False
        if requested_punch == "CHECK_OUT":
            if is_corporate and (not latest_today_rec or latest_today_rec.check_out_time is not None or not latest_today_rec.check_in_time):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot record Check-Out for '{student.name}': No active Check-In record found for today."
                )
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
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot record Check-Out for '{student.name}': No active Check-In record found for today."
                )
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

    def record_punch(
        self,
        tenant_id: int,
        student_id: int,
        node_id: str = "MOBILE-APP",
        punch_type: str = "AUTO",
        geo_latitude: Optional[float] = None,
        geo_longitude: Optional[float] = None,
        geo_accuracy: Optional[float] = None,
        frame_bgr: Optional[np.ndarray] = None,
        confidence_distance: float = 0.0,
        face_box: Optional[Dict[str, int]] = None,
        is_self_attendance: bool = True,
        custom_cooldown_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Unified Attendance Punch Pipeline:
        Serves Centralized Webcam Kiosks, Self-Attendance Browser Portals, and Mobile App Clients.
        1. Validates tenant and employee operational status.
        2. Enforces strict geofence verification if GPS coordinates or self-attendance are provided.
        3. Invokes core corporate shift state machine, cooldown windows, and deduplication cache.
        4. Resolves any active out-of-bounds breach when a valid punch is accepted.
        """
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Organization / Institute not found.")
        if not tenant.is_active or tenant.is_deleted:
            raise HTTPException(status_code=403, detail="Organization subscription is inactive or suspended.")

        student = self.db.query(Student).filter(Student.id == student_id, Student.tenant_id == tenant_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Employee record not found.")
        if not student.is_active or (student.employment_status and student.employment_status.upper() in ["RELIEVED", "TERMINATED", "RESIGNED"]):
            raise HTTPException(status_code=403, detail="Employee account is relieved or inactive.")

        branding = tenant.branding
        dist_meters = None

        is_mobile_app = (node_id == "MOBILE-APP")

        # Multi-Office Location Geofence Resolution
        assigned_location = student.location if (student and student.location and student.location.is_active) else None

        if assigned_location:
            geofence_enabled = bool(assigned_location.self_attendance_geofencing_enabled)
            target_lat = assigned_location.latitude
            target_lon = assigned_location.longitude
            max_radius = float(assigned_location.radius_meters if assigned_location.radius_meters is not None else 150.0)
            max_acc = float(branding.max_gps_accuracy_meters if (branding and branding.max_gps_accuracy_meters is not None) else 50.0)
            location_label = f"assigned office '{assigned_location.name}'"
        else:
            # Per policy: treat geofencing as disabled by default until an office is explicitly assigned
            geofence_enabled = False
            target_lat = float(branding.geo_latitude) if (branding and branding.geo_latitude is not None) else None
            target_lon = float(branding.geo_longitude) if (branding and branding.geo_longitude is not None) else None
            max_radius = float(branding.geo_radius_meters if (branding and branding.geo_radius_meters is not None) else 150.0)
            max_acc = float(branding.max_gps_accuracy_meters if (branding and branding.max_gps_accuracy_meters is not None) else 50.0)
            location_label = "unassigned office"

        if not geofence_enabled:
            # When geofencing is disabled for the employee's location (or employee has no assigned office):
            # - Mobile app: Allowed to check-in/out from ANY location without geofence perimeter restrictions.
            # - Web portal self-attendance: Blocked (requires geofencing/self-attendance to be enabled).
            if not is_mobile_app and is_self_attendance:
                raise HTTPException(status_code=403, detail="Self-attendance via web portal is disabled by organization administrator.")

            # Calculate distance for audit purposes if coordinates are provided, but do not block
            if geo_latitude is not None and geo_longitude is not None and target_lat is not None and target_lon is not None:
                try:
                    dist_meters = haversine_distance(float(geo_latitude), float(geo_longitude), float(target_lat), float(target_lon))
                except Exception:
                    dist_meters = None
        else:
            # Geofencing is ENABLED for this office: Enforce strict perimeter radius check
            if geo_latitude is not None and geo_longitude is not None:
                if target_lat is None or target_lon is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Geofence coordinates for {location_label} are not configured by administrator."
                    )

                user_acc = float(geo_accuracy) if geo_accuracy is not None else 10.0

                is_valid_geo, dist_meters, geo_err = validate_geofence(
                    user_lat=float(geo_latitude),
                    user_lon=float(geo_longitude),
                    user_accuracy=user_acc,
                    target_lat=float(target_lat),
                    target_lon=float(target_lon),
                    max_radius_meters=max_radius,
                    max_accuracy_meters=max_acc,
                )

                if not is_valid_geo:
                    err_msg = f"Outside geofenced perimeter for {location_label}. {geo_err}" if geo_err else f"Outside geofenced perimeter for {location_label} ({dist_meters}m from center, radius: {max_radius}m)."
                    raise HTTPException(status_code=403, detail=err_msg)
            elif is_self_attendance:
                if target_lat is not None and target_lon is not None:
                    raise HTTPException(status_code=400, detail=f"GPS location coordinates are required for self-attendance check-in at {location_label}.")

        # Delegate to AttendanceManager for unified corporate dual-punch state machine & shift reconciliation
        mark_res = attendance_manager.mark_attendance(
            student_id=student_id,
            node_id=node_id,
            confidence_distance=confidence_distance,
            frame_bgr=frame_bgr,
            face_box=face_box,
            tenant_id=tenant_id,
            custom_cooldown_seconds=custom_cooldown_seconds,
            geo_latitude=geo_latitude,
            geo_longitude=geo_longitude,
            geo_distance_meters=dist_meters,
            is_self_attendance=is_self_attendance,
        )

        if mark_res is None:
            raise HTTPException(status_code=500, detail="Failed to process attendance record.")

        if mark_res.get("cooldown_active"):
            return {
                "status": "cooldown",
                "attendance_logged": False,
                "cooldown_active": True,
                "message": mark_res.get("message", "Attendance already logged recently. Please wait a moment."),
                "cooldown_remaining_seconds": mark_res.get("cooldown_remaining_seconds", 0),
                "cooldown_remaining_minutes": mark_res.get("cooldown_remaining_minutes", 0),
                "punch_type": mark_res.get("punch_type", "CHECK_IN"),
                "student_name": student.name,
                "distance_meters": dist_meters,
            }

        # Resolve any active breach for this employee upon a successful punch
        now_ist = get_ist_now()
        active_breach = (
            self.db.query(EmployeeGeofenceBreach)
            .filter(
                EmployeeGeofenceBreach.tenant_id == tenant_id,
                EmployeeGeofenceBreach.student_id == student_id,
                EmployeeGeofenceBreach.breach_date == now_ist.date(),
                EmployeeGeofenceBreach.status == "ACTIVE",
            )
            .first()
        )
        if active_breach:
            active_breach.end_time = now_ist
            active_breach.duration_seconds = max(1, int((now_ist - active_breach.start_time).total_seconds()))
            active_breach.status = "RESOLVED"
            self.db.commit()

        return {
            "status": "success",
            "success": True,
            "attendance_logged": True,
            "punch_type": mark_res.get("punch_type", "CHECK_IN"),
            "punch_source": "MOBILE_APP" if node_id == "MOBILE-APP" else "KIOSK",
            "shift_status": mark_res.get("shift_status", "ON_TIME"),
            "work_duration_minutes": mark_res.get("work_duration_minutes"),
            "work_duration_formatted": mark_res.get("work_duration_formatted", "--"),
            "check_in_short": mark_res.get("check_in_short", "--"),
            "check_out_short": mark_res.get("check_out_short", "--"),
            "record": mark_res.get("record"),
            "message": mark_res.get("message", "Attendance registered successfully."),
            "student": student.to_dict(),
            "distance_meters": dist_meters,
        }

    def process_geofence_heartbeat(
        self,
        tenant_id: int,
        student_id: int,
        latitude: float,
        longitude: float,
        accuracy: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Background Geolocation Heartbeat:
        Monitors perimeter compliance strictly during active work shift (between Check-In and Check-Out).
        Logs timestamp, coordinates, and duration of out-of-bounds events for administrative audit trails.
        """
        now_ist = get_ist_now()
        today = now_ist.date()
        start_today = datetime.combine(today, datetime.min.time())
        end_today = datetime.combine(today, datetime.max.time())

        # Check if student is actively checked in today
        active_session = (
            self.db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.tenant_id == tenant_id,
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.is_deleted == False,
                AttendanceRecord.status == "PRESENT",
                AttendanceRecord.check_in_time.isnot(None),
                AttendanceRecord.check_out_time.is_(None),
                AttendanceRecord.timestamp.between(start_today, end_today),
            )
            .order_by(AttendanceRecord.timestamp.desc())
            .first()
        )

        if not active_session:
            return {
                "status": "idle",
                "in_bounds": True,
                "message": "Out-of-bounds monitoring is inactive (employee is not in an active checked-in session).",
                "is_checked_in": False,
            }

        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        branding = tenant.branding if tenant else None
        student = self.db.query(Student).filter(Student.id == student_id, Student.tenant_id == tenant_id).first()
        assigned_location = student.location if (student and student.location and student.location.is_active) else None

        if assigned_location:
            geofence_enabled = bool(assigned_location.self_attendance_geofencing_enabled)
            target_lat = assigned_location.latitude
            target_lon = assigned_location.longitude
            max_radius = float(assigned_location.radius_meters if assigned_location.radius_meters is not None else 150.0)
            location_name = assigned_location.name
        else:
            # Geofencing is treated as disabled by default until an office is assigned
            geofence_enabled = False
            target_lat = float(branding.geo_latitude) if (branding and branding.geo_latitude is not None) else None
            target_lon = float(branding.geo_longitude) if (branding and branding.geo_longitude is not None) else None
            max_radius = float(branding.geo_radius_meters if (branding and branding.geo_radius_meters is not None) else 150.0)
            location_name = "Assigned Campus"

        if not geofence_enabled:
            return {
                "status": "bypassed",
                "in_bounds": True,
                "message": f"Geofencing is disabled for {location_name} (any location allowed).",
                "is_checked_in": True,
            }
        if target_lat is None or target_lon is None:
            return {
                "status": "unconfigured",
                "in_bounds": True,
                "message": f"Geofence perimeter for {location_name} is not configured.",
                "is_checked_in": True,
            }

        target_lat = float(target_lat)
        target_lon = float(target_lon)
        max_radius = float(branding.geo_radius_meters if branding.geo_radius_meters is not None else 150.0)

        dist = haversine_distance(latitude, longitude, target_lat, target_lon)
        active_breach = (
            self.db.query(EmployeeGeofenceBreach)
            .filter(
                EmployeeGeofenceBreach.tenant_id == tenant_id,
                EmployeeGeofenceBreach.student_id == student_id,
                EmployeeGeofenceBreach.breach_date == today,
                EmployeeGeofenceBreach.status == "ACTIVE",
            )
            .order_by(EmployeeGeofenceBreach.start_time.desc())
            .first()
        )

        if dist > max_radius:
            # Out of bounds!
            if active_breach:
                active_breach.end_time = now_ist
                active_breach.duration_seconds = max(1, int((now_ist - active_breach.start_time).total_seconds()))
                active_breach.last_known_latitude = latitude
                active_breach.last_known_longitude = longitude
                active_breach.distance_meters = dist
            else:
                new_breach = EmployeeGeofenceBreach(
                    tenant_id=tenant_id,
                    student_id=student_id,
                    breach_date=today,
                    start_time=now_ist,
                    end_time=now_ist,
                    duration_seconds=0,
                    last_known_latitude=latitude,
                    last_known_longitude=longitude,
                    distance_meters=dist,
                    geofence_radius_meters=max_radius,
                    status="ACTIVE",
                    created_at=now_ist,
                )
                self.db.add(new_breach)
            self.db.commit()

            return {
                "status": "breach_active",
                "in_bounds": False,
                "is_within_geofence": False,
                "breach_logged": True,
                "breach_resolved": False,
                "is_checked_in": True,
                "distance_meters": round(dist, 1),
                "geofence_radius_meters": max_radius,
                "message": f"Out of bounds detected ({round(dist, 1)}m from center).",
            }
        else:
            # In bounds!
            had_breach = active_breach is not None
            if active_breach:
                active_breach.end_time = now_ist
                active_breach.duration_seconds = max(1, int((now_ist - active_breach.start_time).total_seconds()))
                active_breach.status = "RESOLVED"
                self.db.commit()

            return {
                "status": "in_bounds",
                "in_bounds": True,
                "is_within_geofence": True,
                "breach_logged": False,
                "breach_resolved": had_breach,
                "is_checked_in": True,
                "distance_meters": round(dist, 1),
                "geofence_radius_meters": max_radius,
                "message": "Inside geofence perimeter.",
            }

    def get_geofence_breaches(
        self,
        tenant_id: int,
        student_id: Optional[int] = None,
        breach_date: Optional[str] = None,
        status_filter: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieves geofence breach audit trail logs for tenant administrators."""
        query = (
            self.db.query(EmployeeGeofenceBreach)
            .filter(EmployeeGeofenceBreach.tenant_id == tenant_id)
        )
        if student_id:
            query = query.filter(EmployeeGeofenceBreach.student_id == student_id)
        if breach_date:
            try:
                b_d = datetime.strptime(breach_date.strip()[:10], "%Y-%m-%d").date()
                query = query.filter(EmployeeGeofenceBreach.breach_date == b_d)
            except ValueError:
                pass
        if status_filter and status_filter.upper() != "ALL":
            query = query.filter(EmployeeGeofenceBreach.status == status_filter.upper().strip())

        breaches = query.order_by(EmployeeGeofenceBreach.start_time.desc()).limit(limit).all()
        return [b.to_dict() for b in breaches]
