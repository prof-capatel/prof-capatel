import logging
import base64
import time
import json
import hmac
import hashlib
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, extract

from src.core.camera_utils import decode_image_bytes
from src.core.face_engine import FaceEngine
from src.database.models import (
    Tenant,
    Student,
    User,
    FaceEncoding,
    AttendanceRecord,
    LeaveType,
    LeaveBalance,
    LeaveRequest,
    SystemBranding,
    PayrollPayslip,
    EmployeeSalaryStructure,
    AuditLog,
    EmployeeGeofenceBreach,
)
from src.database.session import get_db, SessionLocal
from src.server.tenant_middleware import resolve_tenant
from src.server.routes.api_leave import get_or_create_leave_balance
from src.core.payroll_engine import number_to_words_inr, calculate_employee_payroll
from src.services.attendance_service import AttendanceService
from src.utils.auth_utils import hash_password, verify_password
from src.utils.timezone import get_ist_now
from src.utils.financial_year import get_financial_year_info, parse_financial_year_code

logger = logging.getLogger("api_employee_portal")

router = APIRouter(prefix="/api/v1/employee", tags=["Employee Face Login & Self-Service"])

EMP_SECRET_KEY = "face_attendance_employee_self_service_session_secret_2026"
EMP_COOKIE_NAME = "emp_session_token"


# --------------------------------------------------------------------------
# JWT Token Helpers for Passwordless Employee Authentication
# --------------------------------------------------------------------------

def create_employee_token(student_id: int, tenant_id: int, roll_number: str, name: str, expires_in_sec: int = 86400) -> str:
    """Generates an HMAC-SHA256 signed JWT session token for an authenticated employee."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "student_id": student_id,
        "tenant_id": tenant_id,
        "roll_number": roll_number,
        "name": name,
        "exp": int(time.time()) + expires_in_sec,
    }
    b64_header = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    b64_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(EMP_SECRET_KEY.encode(), f"{b64_header}.{b64_payload}".encode(), hashlib.sha256).digest()
    b64_sig = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{b64_header}.{b64_payload}.{b64_sig}"


def decode_employee_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates employee JWT session token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        b64_header, b64_payload, b64_sig = parts
        expected_sig = hmac.new(EMP_SECRET_KEY.encode(), f"{b64_header}.{b64_payload}".encode(), hashlib.sha256).digest()
        actual_sig = base64.urlsafe_b64decode(b64_sig + "=" * ((4 - len(b64_sig) % 4) % 4))
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload_bytes = base64.urlsafe_b64decode(b64_payload + "=" * ((4 - len(b64_payload) % 4) % 4))
        payload = json.loads(payload_bytes)
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception as e:
        logger.debug(f"Employee token decoding failed: {e}")
        return None


def get_current_employee(
    request: Request,
    db: Session = Depends(get_db),
) -> Student:
    """Dependency: Extracts and validates the authenticated employee from cookie or Authorization header."""
    token = request.cookies.get(EMP_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Employee authentication required. Please scan your face or sign in with credentials.",
        )

    student = None
    payload = decode_employee_token(token)
    if payload:
        student_id = payload.get("student_id")
        tenant_id = payload.get("tenant_id")
        student = (
            db.query(Student)
            .filter(
                Student.id == student_id,
                Student.tenant_id == tenant_id,
            )
            .first()
        )
    else:
        # Fallback: attempt decoding as standard RBAC access token
        from src.server.rbac_middleware import decode_access_token
        access_payload = decode_access_token(token)
        if access_payload and access_payload.get("user_id"):
            user = db.query(User).filter(User.id == access_payload["user_id"]).first()
            if user:
                if user.student_profile:
                    student = user.student_profile
                elif user.tenant_id:
                    student = db.query(Student).filter(
                        Student.user_id == user.id,
                        Student.tenant_id == user.tenant_id,
                    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Employee session has expired or is invalid. Please re-authenticate.",
        )

    if not student.is_active or (student.employment_status and student.employment_status.upper() in ["RELIEVED", "TERMINATED", "RESIGNED"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee account is inactive or relieved. Access to self-service is restricted.",
        )

    return student


# --------------------------------------------------------------------------
# Request Payload Schemas
# --------------------------------------------------------------------------

class EmployeeFaceLoginPayload(BaseModel):
    tenant_identifier: str  # tenant slug, UUID, or ID
    photo_base64: str       # data:image/jpeg;base64,... or raw base64 string


class EmployeeLeaveApplyPayload(BaseModel):
    leave_type_id: int
    start_date: str         # YYYY-MM-DD
    end_date: str           # YYYY-MM-DD
    is_half_day: Optional[bool] = False
    half_day_period: Optional[str] = "NONE"  # NONE, FIRST_HALF, SECOND_HALF
    reason: str


class EmployeeMobileCheckInPayload(BaseModel):
    latitude: float
    longitude: float
    accuracy: Optional[float] = 10.0
    photo_base64: Optional[str] = None
    punch_type: Optional[str] = "AUTO"
    is_mock_location: Optional[bool] = False
    device_info: Optional[str] = None


class EmployeeGeofenceHeartbeatPayload(BaseModel):
    latitude: float
    longitude: float
    accuracy: Optional[float] = 10.0
    is_mock_location: Optional[bool] = False
    device_info: Optional[str] = None


class EmployeeChangePasswordPayload(BaseModel):
    current_password: Optional[str] = None
    new_password: str
    confirm_password: Optional[str] = None
    is_mock_location: Optional[bool] = False
    device_info: Optional[str] = None


# --------------------------------------------------------------------------
# Authentication Endpoints
# --------------------------------------------------------------------------

@router.post("/face-login")
async def employee_face_login(
    payload: EmployeeFaceLoginPayload,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Passwordless 1:N Facial Authentication Endpoint for Employees.
    Matches live camera snapshot against active employee encodings in the tenant.
    Issues a secure HTTP-Only JWT session cookie on successful match.
    """
    tenant = resolve_tenant(db, payload.tenant_identifier)
    if not tenant:
        raise HTTPException(status_code=404, detail="Organization / Institute not found.")

    if not tenant.is_active or tenant.is_deleted:
        raise HTTPException(status_code=403, detail="Organization subscription is currently inactive.")

    # 1. Clean & Decode Base64 Image
    raw_b64 = payload.photo_base64
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(raw_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed base64 image data.")

    image_bgr = decode_image_bytes(image_bytes)
    if image_bgr is None:
        raise HTTPException(status_code=400, detail="Could not decode camera image frame.")

    # 2. Extract Face Vector
    vector, face_box, msg = FaceEngine.compute_single_face_vector(image_bgr)
    if vector is None:
        raise HTTPException(
            status_code=400,
            detail="Face detection failed. Please center your face in the camera frame with good lighting.",
        )

    # 3. Retrieve Enrolled Face Encodings for this Tenant (Active Employees only)
    branding = tenant.branding
    threshold = float(branding.self_attendance_face_threshold if branding and branding.self_attendance_face_threshold else 0.52)
    import numpy as np

    encodings = (
        db.query(FaceEncoding)
        .join(Student, FaceEncoding.student_id == Student.id)
        .filter(
            FaceEncoding.tenant_id == tenant.id,
            Student.is_active == True,
            or_(Student.employment_status == "ACTIVE", Student.employment_status == None),
        )
        .all()
    )

    if not encodings:
        # Check if user is a pending self-registered employee
        pending_encodings = (
            db.query(FaceEncoding)
            .join(Student, FaceEncoding.student_id == Student.id)
            .filter(
                FaceEncoding.tenant_id == tenant.id,
                or_(
                    Student.employment_status == "PENDING_APPROVAL",
                    and_(Student.is_active == False, Student.employment_status != "RELIEVED", Student.employment_status != "TERMINATED"),
                ),
            )
            .all()
        )
        for p_enc in pending_encodings:
            try:
                p_vec = p_enc.get_numpy_vector()
                p_dist = float(np.linalg.norm(p_vec - vector))
                if p_dist <= threshold:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Your registration is pending administrator approval. Please contact HR/Admin.",
                    )
            except HTTPException:
                raise
            except Exception:
                pass

        raise HTTPException(
            status_code=404,
            detail="No enrolled face profiles found for this organization. Please contact your HR administrator.",
        )

    # 4. Compare Euclidean Distance
    best_match_student = None
    min_dist = float("inf")

    for enc in encodings:
        try:
            sample_vec = enc.get_numpy_vector()
            dist = float(np.linalg.norm(sample_vec - vector))
            if dist < min_dist:
                min_dist = dist
                if dist <= threshold:
                    best_match_student = enc.student
        except Exception as e:
            logger.debug(f"Vector comparison note: {e}")

    if not best_match_student:
        # Check if the face matches a pending self-registered employee
        pending_encodings = (
            db.query(FaceEncoding)
            .join(Student, FaceEncoding.student_id == Student.id)
            .filter(
                FaceEncoding.tenant_id == tenant.id,
                or_(
                    Student.employment_status == "PENDING_APPROVAL",
                    and_(Student.is_active == False, Student.employment_status != "RELIEVED", Student.employment_status != "TERMINATED"),
                ),
            )
            .all()
        )
        for p_enc in pending_encodings:
            try:
                p_vec = p_enc.get_numpy_vector()
                p_dist = float(np.linalg.norm(p_vec - vector))
                if p_dist <= threshold:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Your registration is pending administrator approval. Please contact HR/Admin.",
                    )
            except HTTPException:
                raise
            except Exception:
                pass

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Face not recognized (distance: {round(min_dist, 3)}, threshold: {threshold}). Please try again with clear lighting or contact HR.",
        )

    # 5. Issue JWT Session Token
    token = create_employee_token(
        student_id=best_match_student.id,
        tenant_id=tenant.id,
        roll_number=best_match_student.roll_number,
        name=best_match_student.name,
        expires_in_sec=604800,  # 7-day extended session
    )

    response.set_cookie(
        key=EMP_COOKIE_NAME,
        value=token,
        max_age=604800,  # 7-day persistence
        httponly=True,
        samesite="lax",
        secure=False,  # Allows local HTTP / LAN testing
        path="/",
    )

    match_confidence = round(max(0.0, (1.0 - (min_dist / 0.6))) * 100, 1)

    return {
        "status": "success",
        "message": f"Welcome, {best_match_student.name}! Face authenticated successfully.",
        "token": token,
        "employee": best_match_student.to_dict(),
        "confidence_pct": match_confidence,
        "redirect_url": f"/employee/{tenant.slug}/dashboard",
    }


@router.post("/logout")
def employee_logout(response: Response):
    """Clears the employee session cookie."""
    response.delete_cookie(key=EMP_COOKIE_NAME, path="/")
    return {"status": "success", "message": "Logged out successfully."}


# --------------------------------------------------------------------------
# Employee Profile & Dashboard Information
# --------------------------------------------------------------------------

@router.get("/me")
def get_employee_profile(
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Returns the authenticated employee's profile and organization info."""
    tenant = db.query(Tenant).filter(Tenant.id == student.tenant_id).first()
    branding = tenant.branding if tenant else None

    return {
        "status": "success",
        "employee": student.to_dict(),
        "tenant": {
            "name": tenant.name if tenant else "Organization",
            "slug": tenant.slug if tenant else "default",
            "type": tenant.tenant_type if tenant else "corporate",
            "institution_name": branding.institution_name if branding else "Company Hub",
            "primary_accent_color": branding.primary_accent_color if branding else "#c2410c",
            "logo_url": f"/data/branding/{branding.logo_filename}" if (branding and branding.logo_filename) else None,
            "currency_symbol": branding.currency_symbol if branding else "₹",
        },
    }


@router.get("/has-password")
def check_employee_has_password(
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Checks whether the authenticated employee has an existing password configured."""
    user = student.user
    if not user and student.user_id:
        user = db.query(User).filter(User.id == student.user_id).first()
    has_pwd = bool(user and user.password_hash)
    return {
        "status": "success",
        "has_password": has_pwd,
        "username": student.roll_number,
    }


@router.post("/change-password")
def change_employee_password(
    payload: EmployeeChangePasswordPayload,
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """
    Authenticated Employee Password Update:
    Allows employees to set or update their account password for username/password login.
    If the user has an existing password, current_password is required and validated.
    If enrolled strictly via face recognition, allows setting their initial password without current_password.
    """
    new_pwd = payload.new_password.strip() if payload.new_password else ""
    if len(new_pwd) < 6:
        raise HTTPException(
            status_code=400,
            detail="New password must be at least 6 characters in length."
        )
    if payload.confirm_password and payload.confirm_password.strip() != new_pwd:
        raise HTTPException(
            status_code=400,
            detail="New password and confirmation password do not match."
        )

    # Find or link User record for this employee
    user = student.user
    if not user and student.user_id:
        user = db.query(User).filter(User.id == student.user_id).first()

    if user and user.password_hash:
        if not payload.current_password or not payload.current_password.strip():
            raise HTTPException(
                status_code=400,
                detail="Current password is required to update your existing password."
            )
        if not verify_password(payload.current_password.strip(), user.password_hash):
            raise HTTPException(
                status_code=400,
                detail="Incorrect current password. Please verify and try again."
            )

    hashed = hash_password(new_pwd)

    if not user:
        username_candidate = student.roll_number.strip().lower()
        existing_u = db.query(User).filter(
            User.username == username_candidate,
            User.tenant_id == student.tenant_id,
        ).first()
        if existing_u:
            user = existing_u
            user.password_hash = hashed
            user.is_active = True
        else:
            user = User(
                tenant_id=student.tenant_id,
                username=username_candidate,
                email=student.email or f"{username_candidate}@tenant{student.tenant_id}.local",
                password_hash=hashed,
                role="EMPLOYEE",
                full_name=student.name,
                is_active=True,
            )
            db.add(user)
            db.flush()
        student.user_id = user.id
    else:
        user.password_hash = hashed
        user.is_active = True

    db.commit()
    return {
        "status": "success",
        "message": "Password updated successfully. You can now use your Employee ID and password to sign in.",
    }


@router.get("/attendance")
def get_employee_attendance_history(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    limit: int = 200,
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Returns the authenticated employee's punch records with optional month and year filtering."""
    query = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.tenant_id == student.tenant_id,
            AttendanceRecord.student_id == student.id,
            AttendanceRecord.is_deleted == False,
        )
    )

    if year:
        query = query.filter(extract("year", AttendanceRecord.timestamp) == year)
    if month:
        query = query.filter(extract("month", AttendanceRecord.timestamp) == month)

    if start_date:
        try:
            s_dt = datetime.strptime(start_date.strip()[:10], "%Y-%m-%d")
            query = query.filter(AttendanceRecord.timestamp >= s_dt)
        except ValueError:
            pass

    if end_date:
        try:
            e_dt = datetime.strptime(end_date.strip()[:10] + " 23:59:59", "%Y-%m-%d %H:%M:%S")
            query = query.filter(AttendanceRecord.timestamp <= e_dt)
        except ValueError:
            pass

    records = query.order_by(AttendanceRecord.timestamp.desc()).limit(limit).all()

    return {
        "status": "success",
        "count": len(records),
        "records": [r.to_dict() for r in records],
    }


@router.get("/payroll")
def get_employee_payroll_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """
    Returns transparent breakdown of the employee's work hours, overtime,
    approved paid leave credits, and estimated gross earnings for the period.
    """
    if not student.tenant or not student.tenant.has_payroll_module:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Payroll & Compensation is not enabled for your organization's subscription edition.",
        )

    now_ist = get_ist_now()
    if not start_date or not end_date:
        # Default to current calendar month
        first_day = now_ist.date().replace(day=1)
        start_dt = datetime.combine(first_day, datetime.min.time())
        end_dt = datetime.combine(now_ist.date(), datetime.max.time())
    else:
        try:
            s_d = datetime.strptime(start_date.strip()[:10], "%Y-%m-%d").date()
            e_d = datetime.strptime(end_date.strip()[:10], "%Y-%m-%d").date()
            start_dt = datetime.combine(s_d, datetime.min.time())
            end_dt = datetime.combine(e_d, datetime.max.time())
        except ValueError:
            first_day = now_ist.date().replace(day=1)
            start_dt = datetime.combine(first_day, datetime.min.time())
            end_dt = datetime.combine(now_ist.date(), datetime.max.time())

    branding = db.query(SystemBranding).filter(SystemBranding.tenant_id == student.tenant_id).first()
    hourly_rate = float(student.hourly_rate if student.hourly_rate is not None else (branding.default_hourly_rate if branding else 15.0))
    ot_mult = float(branding.overtime_rate_multiplier if branding and branding.overtime_rate_multiplier else 1.5)
    std_daily_hours = float(branding.standard_working_hours_per_day if branding and branding.standard_working_hours_per_day else 8.0)
    enable_ot = bool(branding.enable_overtime if branding else True)
    currency = branding.currency_symbol if branding else "₹"

    # 1. Fetch attendance records in date range
    records = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.tenant_id == student.tenant_id,
            AttendanceRecord.student_id == student.id,
            AttendanceRecord.timestamp.between(start_dt, end_dt),
        )
        .all()
    )

    # Group records by calendar day
    daily_minutes: Dict[date, int] = {}
    missed_checkouts_count = 0

    for r in records:
        r_date = r.timestamp.date() if r.timestamp else now_ist.date()
        if r.work_duration_minutes is not None:
            daily_minutes[r_date] = daily_minutes.get(r_date, 0) + r.work_duration_minutes
        elif r.check_in_time and not r.check_out_time and r_date < now_ist.date():
            # Missed checkout on past date -> credit half day (4.0 hrs)
            missed_checkouts_count += 1
            daily_minutes[r_date] = daily_minutes.get(r_date, 0) + int(std_daily_hours * 30)

    total_regular_hours = 0.0
    total_overtime_hours = 0.0

    for d, mins in daily_minutes.items():
        hrs = mins / 60.0
        if enable_ot and hrs > std_daily_hours:
            total_regular_hours += std_daily_hours
            total_overtime_hours += (hrs - std_daily_hours)
        else:
            total_regular_hours += hrs

    # 2. Fetch approved paid leaves in date range
    approved_leaves = (
        db.query(LeaveRequest)
        .join(LeaveType, LeaveRequest.leave_type_id == LeaveType.id)
        .filter(
            LeaveRequest.tenant_id == student.tenant_id,
            LeaveRequest.student_id == student.id,
            LeaveRequest.status == "APPROVED",
            LeaveType.is_paid == True,
            LeaveRequest.start_date <= end_dt.date(),
            LeaveRequest.end_date >= start_dt.date(),
        )
        .all()
    )

    paid_leave_days = sum(float(l.total_days or 0.0) for l in approved_leaves)
    paid_leave_hours = paid_leave_days * std_daily_hours

    # 3. Compute detailed payroll via central engine (supporting Structured, Hourly & Daily Wage)
    payroll_res = calculate_employee_payroll(
        db=db,
        tenant=student.tenant,
        student=student,
        start_date=start_dt.date(),
        end_date=end_dt.date(),
        total_working_days=26.0,
    )

    regular_earnings = float(payroll_res.get("basic_earned", (total_regular_hours + paid_leave_hours) * hourly_rate))
    overtime_earnings = float(payroll_res.get("ot_earnings", total_overtime_hours * hourly_rate * ot_mult))
    total_gross_earnings = float(payroll_res.get("gross_earnings", regular_earnings + overtime_earnings))
    net_salary = float(payroll_res.get("net_salary", total_gross_earnings))

    return {
        "status": "success",
        "period": {
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "end_date": end_dt.strftime("%Y-%m-%d"),
        },
        "hourly_rate": hourly_rate,
        "currency_symbol": currency,
        "standard_working_hours_per_day": std_daily_hours,
        "overtime_multiplier": ot_mult,
        "compensation_model": payroll_res.get("compensation_model", "STRUCTURED_SALARY"),
        "active_days_count": len(daily_minutes),
        "total_punch_hours": round(total_regular_hours + total_overtime_hours, 2),
        "regular_hours": round(total_regular_hours, 2),
        "overtime_hours": round(total_overtime_hours, 2),
        "missed_checkouts_count": missed_checkouts_count,
        "paid_leave_days": round(paid_leave_days, 1),
        "paid_leave_hours": round(paid_leave_hours, 2),
        "regular_earnings": round(regular_earnings, 2),
        "overtime_earnings": round(overtime_earnings, 2),
        "gross_earnings": round(total_gross_earnings, 2),
        "net_salary": round(net_salary, 2),
        "structure": payroll_res.get("parameters", {}),
        "breakdown": payroll_res.get("breakdown", {}),
    }


# --------------------------------------------------------------------------
# Employee Mobile Geofenced Check-In & Background Tracking
# --------------------------------------------------------------------------

@router.post("/check-in")
async def employee_mobile_checkin(
    payload: EmployeeMobileCheckInPayload,
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """
    Mobile Geofenced Self Check-In / Check-Out:
    Validates employee session, verifies GPS coordinate proximity against tenant's configured geofence radius.
    If tenant mandates selfie biometric verification, compares selfie against employee's enrolled face encodings.
    Shares the exact same unified corporate attendance state machine as centralized webcam kiosks.
    """
    tenant = student.tenant
    branding = tenant.branding if tenant else None

    if payload.is_mock_location:
        now_ist = get_ist_now()
        # 1. Log immutable security audit trail
        db.add(
            AuditLog(
                tenant_id=tenant.id if tenant else None,
                user_id=None,
                actor_name=student.name,
                actor_role="EMPLOYEE",
                action_type="GEOFENCE_BREACH_MOCK_GPS",
                target_type="STUDENT",
                target_id=str(student.id),
                description=f"Mock GPS or location spoofing application detected for employee '{student.name}' (Roll: {student.roll_number}). Coordinates: ({payload.latitude}, {payload.longitude}). Action blocked.",
            )
        )
        # 2. Record geofence breach entry for tenant admin audit
        breach = EmployeeGeofenceBreach(
            tenant_id=tenant.id,
            student_id=student.id,
            breach_date=now_ist.date(),
            start_time=now_ist,
            end_time=now_ist,
            duration_seconds=0,
            last_known_latitude=payload.latitude,
            last_known_longitude=payload.longitude,
            distance_meters=0.0,
            geofence_radius_meters=branding.geo_radius_meters if branding else 100.0,
            status="MOCK_GPS_SPOOF",
        )
        db.add(breach)
        db.commit()

        raise HTTPException(
            status_code=403,
            detail="Mock GPS or location spoofing application detected. Real hardware GPS is required. This security breach has been logged.",
        )

    # Check if selfie face verification is mandated by tenant admin
    frame_bgr = None
    conf_dist = 0.0

    require_face = bool(branding.mobile_require_face_verification if branding else False)
    if require_face or payload.photo_base64:
        if not payload.photo_base64 or not payload.photo_base64.strip():
            raise HTTPException(
                status_code=400,
                detail="A live selfie camera photo is required for mobile check-in by your organization's policy.",
            )

        raw_b64 = payload.photo_base64.strip()
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]

        try:
            img_bytes = base64.b64decode(raw_b64)
        except Exception:
            raise HTTPException(status_code=400, detail="Malformed base64 camera image.")

        frame_bgr = decode_image_bytes(img_bytes)
        if frame_bgr is None:
            raise HTTPException(status_code=400, detail="Could not decode mobile camera capture frame.")

        vector, face_box, msg = FaceEngine.compute_single_face_vector(frame_bgr)
        if vector is None:
            raise HTTPException(
                status_code=400,
                detail="Face not detected in camera frame. Please center your face in good lighting.",
            )

        # Retrieve employee's enrolled face encodings
        enrolled_encs = (
            db.query(FaceEncoding)
            .filter(
                FaceEncoding.tenant_id == student.tenant_id,
                FaceEncoding.student_id == student.id,
            )
            .all()
        )
        if not enrolled_encs:
            raise HTTPException(
                status_code=400,
                detail="No enrolled face template found for your account. Please contact your HR administrator.",
            )

        threshold = float(branding.self_attendance_face_threshold if (branding and branding.self_attendance_face_threshold) else 0.52)
        min_dist = float("inf")
        import numpy as np

        for enc in enrolled_encs:
            try:
                sample_vec = enc.get_numpy_vector()
                dist = float(np.linalg.norm(sample_vec - vector))
                if dist < min_dist:
                    min_dist = dist
            except Exception:
                pass

        if min_dist > threshold:
            raise HTTPException(
                status_code=401,
                detail=f"Biometric facial verification failed (distance: {round(min_dist, 3)}, threshold: {threshold}). Please try again with clear lighting.",
            )
        conf_dist = round(min_dist, 3)

    service = AttendanceService(db)
    result = service.record_punch(
        tenant_id=student.tenant_id,
        student_id=student.id,
        node_id="MOBILE-APP",
        punch_type=payload.punch_type or "AUTO",
        geo_latitude=payload.latitude,
        geo_longitude=payload.longitude,
        geo_accuracy=payload.accuracy,
        frame_bgr=frame_bgr,
        confidence_distance=conf_dist,
        is_self_attendance=True,
    )
    if result.get("cooldown_active"):
        raise HTTPException(status_code=400, detail=result.get("message", "Punch cooldown is currently active. Please wait."))
    if not result.get("attendance_logged"):
        raise HTTPException(status_code=400, detail=result.get("message", "Attendance could not be registered."))
    return result


@router.post("/geofence/heartbeat")
def employee_geofence_heartbeat(
    payload: EmployeeGeofenceHeartbeatPayload,
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """
    Background Geolocation Heartbeat:
    Dispatched periodically by mobile client while employee is in an active shift session.
    Logs out-of-bounds events and breach duration for administrative audit trails.
    """
    if payload.is_mock_location:
        now_ist = get_ist_now()
        db.add(
            AuditLog(
                tenant_id=student.tenant_id,
                user_id=None,
                actor_name=student.name,
                actor_role="EMPLOYEE",
                action_type="GEOFENCE_BREACH_MOCK_GPS",
                target_type="STUDENT",
                target_id=str(student.id),
                description=f"Mock GPS or location spoofing detected during heartbeat sync for employee '{student.name}'.",
            )
        )
        db.commit()
        raise HTTPException(
            status_code=403,
            detail="Mock GPS or location spoofing application detected. Real hardware GPS is required. This security breach has been logged.",
        )

    service = AttendanceService(db)
    return service.process_geofence_heartbeat(
        tenant_id=student.tenant_id,
        student_id=student.id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy=payload.accuracy or 10.0,
    )


@router.get("/geofence/config")
def get_employee_geofence_config(
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Returns the employee's organization geofencing parameters and current punch status."""
    tenant = student.tenant
    branding = tenant.branding if tenant else None
    service = AttendanceService(db)
    punch_status = service.get_employee_punch_status(student.tenant_id, student.id)

    return {
        "status": "success",
        "geofence_enabled": bool(branding.enable_self_attendance if branding else False),
        "center_latitude": float(branding.geo_latitude) if (branding and branding.geo_latitude is not None) else None,
        "center_longitude": float(branding.geo_longitude) if (branding and branding.geo_longitude is not None) else None,
        "radius_meters": int(branding.geo_radius_meters) if (branding and branding.geo_radius_meters is not None) else 150,
        "tenant_id": student.tenant_id,
        "tenant_name": tenant.name if tenant else "",
        "institution_name": branding.institution_name if branding else (tenant.name if tenant else ""),
        "geo_latitude": branding.geo_latitude if branding else None,
        "geo_longitude": branding.geo_longitude if branding else None,
        "geo_radius_meters": float(branding.geo_radius_meters if (branding and branding.geo_radius_meters) else 150.0),
        "max_gps_accuracy_meters": float(branding.max_gps_accuracy_meters if (branding and branding.max_gps_accuracy_meters) else 50.0),
        "mobile_require_face_verification": bool(branding.mobile_require_face_verification if branding else False),
        "enable_self_attendance": bool(branding.enable_self_attendance if branding else False),
        "punch_status": punch_status,
    }


# --------------------------------------------------------------------------
# Employee Leave Self-Service Endpoints
# --------------------------------------------------------------------------

@router.get("/leave/balances")
def get_my_leave_balances(
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Returns the employee's current annual leave balances and category quotas per Financial Year."""
    if not student.tenant or not student.tenant.has_leave_module:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Leave Management is not enabled for your organization's subscription edition.",
        )

    start_m = student.tenant.financial_year_start_month if (student.tenant and student.tenant.financial_year_start_month) else 4
    fy_info = get_financial_year_info(get_ist_now(), start_month=start_m)
    leave_types = db.query(LeaveType).filter(LeaveType.tenant_id == student.tenant_id, LeaveType.is_active == True).all()

    balances = []
    for lt in leave_types:
        bal = get_or_create_leave_balance(
            db,
            student.tenant_id,
            student,
            lt,
            year=fy_info["start_year"],
            financial_year=fy_info["fy_code"],
        )
        balances.append(bal.to_dict())

    db.commit()

    return {
        "status": "success",
        "year": fy_info["start_year"],
        "financial_year": fy_info["fy_code"],
        "financial_year_label": fy_info["fy_label"],
        "balances": balances,
    }


@router.get("/leave/requests")
def get_my_leave_requests(
    limit: int = 50,
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Returns the authenticated employee's leave applications and approval statuses."""
    if not student.tenant or not student.tenant.has_leave_module:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Leave Management is not enabled for your organization's subscription edition.",
        )

    requests = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.tenant_id == student.tenant_id,
            LeaveRequest.student_id == student.id,
        )
        .order_by(LeaveRequest.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "status": "success",
        "requests": [r.to_dict() for r in requests],
        "count": len(requests),
    }


@router.post("/leave/apply")
def apply_for_leave(
    payload: EmployeeLeaveApplyPayload,
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """
    Submits a new leave request.
    Verifies quota availability and increments balance pending_days.
    """
    if not student.tenant or not student.tenant.has_leave_module:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Leave Management is not enabled for your organization's subscription edition.",
        )

    if not payload.reason or not payload.reason.strip():
        raise HTTPException(status_code=400, detail="Please provide a valid reason for the leave application.")

    try:
        s_date = datetime.strptime(payload.start_date.strip()[:10], "%Y-%m-%d").date()
        e_date = datetime.strptime(payload.end_date.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Please use YYYY-MM-DD.")

    if s_date > e_date:
        raise HTTPException(status_code=400, detail="Start date cannot be after end date.")

    # Calculate total days
    calendar_days = (e_date - s_date).days + 1
    total_days = 0.5 if (payload.is_half_day and calendar_days == 1) else float(calendar_days)

    leave_type = (
        db.query(LeaveType)
        .filter(LeaveType.id == payload.leave_type_id, LeaveType.tenant_id == student.tenant_id, LeaveType.is_active == True)
        .first()
    )
    if not leave_type:
        raise HTTPException(status_code=404, detail="Leave category not found or inactive.")

    # Check live balance for Financial Year
    now_ist = get_ist_now()
    start_m = student.tenant.financial_year_start_month if (student.tenant and student.tenant.financial_year_start_month) else 4
    fy_info = get_financial_year_info(s_date, start_month=start_m)
    balance = get_or_create_leave_balance(
        db,
        student.tenant_id,
        student,
        leave_type,
        year=fy_info["start_year"],
        financial_year=fy_info["fy_code"],
    )

    if leave_type.is_paid and balance.remaining_days < total_days:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient leave balance. You requested {total_days} day(s), but only have {balance.remaining_days} day(s) remaining for {leave_type.name} in {fy_info['fy_label']}.",
        )

    # Create Leave Request
    new_req = LeaveRequest(
        tenant_id=student.tenant_id,
        student_id=student.id,
        leave_type_id=leave_type.id,
        start_date=s_date,
        end_date=e_date,
        is_half_day=bool(payload.is_half_day),
        half_day_period=payload.half_day_period or "NONE",
        total_days=total_days,
        financial_year=fy_info["fy_code"],
        reason=payload.reason.strip(),
        status="PENDING",
        created_at=now_ist,
    )
    db.add(new_req)

    # Reserve pending days on balance
    balance.pending_days += total_days
    balance.remaining_days = max(0.0, balance.total_allocated - balance.used_days - balance.pending_days)
    balance.updated_at = now_ist

    db.commit()
    db.refresh(new_req)

    return {
        "status": "success",
        "message": f"Leave application submitted successfully for {total_days} day(s). Awaiting HR approval.",
        "request": new_req.to_dict(),
        "updated_balance": balance.to_dict(),
    }


@router.post("/leave/requests/{request_id}/cancel")
def cancel_pending_leave_request(
    request_id: int,
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """
    Allows an employee to cancel an erroneously submitted leave application BEFORE it is approved/reviewed.
    Releases the reserved pending quota back to the employee's available balance.
    """
    if not student.tenant or not student.tenant.has_leave_module:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Leave Management is not enabled for your organization's subscription edition.",
        )

    req = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.id == request_id,
            LeaveRequest.student_id == student.id,
            LeaveRequest.tenant_id == student.tenant_id,
        )
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Leave request not found.")

    if req.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel this request: it is already in '{req.status}' status. Only PENDING requests can be canceled.",
        )

    now_ist = get_ist_now()
    start_m = student.tenant.financial_year_start_month if (student.tenant and student.tenant.financial_year_start_month) else 4
    req_date = req.start_date if req.start_date else now_ist.date()
    fy_info = get_financial_year_info(req_date, start_month=start_m)

    # Release pending days from balance
    leave_type = db.query(LeaveType).filter(LeaveType.id == req.leave_type_id).first()
    balance = None
    if leave_type:
        balance = get_or_create_leave_balance(
            db,
            student.tenant_id,
            student,
            leave_type,
            year=fy_info["start_year"],
            financial_year=fy_info["fy_code"],
        )
        balance.pending_days = max(0.0, round(balance.pending_days - req.total_days, 2))
        balance.remaining_days = max(0.0, round(balance.total_allocated - balance.used_days - balance.pending_days, 2))
        balance.updated_at = now_ist

    req.status = "CANCELLED"
    req.admin_remarks = "Cancelled by employee prior to review."
    db.commit()
    db.refresh(req)

    return {
        "status": "success",
        "message": "Leave application has been successfully cancelled and your quota has been restored.",
        "request": req.to_dict(),
        "updated_balance": balance.to_dict() if balance else None,
    }


# --------------------------------------------------------------------------
# Employee Payslips & Compensation Details
# --------------------------------------------------------------------------

@router.get("/payslips")
def get_employee_payslips(
    year: Optional[int] = None,
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """
    Returns list of monthly itemized payslips generated for this employee.
    """
    query = (
        db.query(PayrollPayslip)
        .filter(
            PayrollPayslip.tenant_id == student.tenant_id,
            PayrollPayslip.student_id == student.id,
        )
    )
    if year:
        query = query.filter(PayrollPayslip.period_year == year)

    payslips = query.order_by(PayrollPayslip.period_year.desc(), PayrollPayslip.period_month.desc()).all()
    return {
        "status": "success",
        "payslips": [p.to_dict() for p in payslips],
        "count": len(payslips),
    }


@router.get("/payslips/{payslip_id}")
def get_employee_payslip_detail(
    payslip_id: int,
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """
    Returns full details of an individual itemized payslip for this employee.
    """
    payslip = (
        db.query(PayrollPayslip)
        .filter(
            PayrollPayslip.id == payslip_id,
            PayrollPayslip.tenant_id == student.tenant_id,
            PayrollPayslip.student_id == student.id,
        )
        .first()
    )
    if not payslip:
        raise HTTPException(status_code=404, detail="Payslip not found.")

    data = payslip.to_dict()
    data["net_in_words"] = number_to_words_inr(payslip.net_salary)
    branding_dict = student.tenant.branding.to_dict() if (student.tenant and student.tenant.branding) else {}
    data["company_name"] = branding_dict.get("institution_name") or (student.tenant.name if student.tenant else "")
    data["company_logo"] = branding_dict.get("logo_url") or ""
    data["currency_symbol"] = branding_dict.get("currency_symbol") or "₹"
    return {"status": "success", "data": data}


@router.get("/compensation")
def get_employee_compensation(
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """
    Returns active compensation structure, CTC breakdown, and statutory enrollment details.
    """
    current_structure = (
        db.query(EmployeeSalaryStructure)
        .filter(
            EmployeeSalaryStructure.tenant_id == student.tenant_id,
            EmployeeSalaryStructure.student_id == student.id,
            EmployeeSalaryStructure.is_current == True,
        )
        .first()
    )

    branding = student.tenant.branding if (student.tenant and student.tenant.branding) else None
    currency = branding.currency_symbol if branding and branding.currency_symbol else "₹"

    return {
        "status": "success",
        "currency": currency,
        "employee": {
            "name": student.name,
            "roll_number": student.roll_number,
            "department": student.department or (student.department_rel.name if student.department_rel else "General"),
            "designation": student.designation or (student.designation_rel.title if student.designation_rel else "Staff"),
            "pan_number": student.pan_number or "",
            "uan_number": student.uan_number or "",
            "esic_number": student.esic_number or "",
            "bank_name": student.bank_name or "",
            "bank_account_number": student.bank_account_number or "",
            "bank_ifsc_code": student.bank_ifsc_code or "",
        },
        "structure": current_structure.to_dict() if current_structure else {
            "compensation_model": "HOURLY" if student.hourly_rate else "MONTHLY_FIXED",
            "monthly_gross": float(student.monthly_base_salary or 0.0),
            "hourly_rate": float(student.hourly_rate or 0.0),
            "annual_ctc": float(student.monthly_base_salary or 0.0) * 12.0,
        },
    }

