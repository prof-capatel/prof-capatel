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
from sqlalchemy import or_, and_, func

from src.core.camera_utils import decode_image_bytes
from src.core.face_engine import FaceEngine
from src.database.models import (
    Tenant,
    Student,
    FaceEncoding,
    AttendanceRecord,
    LeaveType,
    LeaveBalance,
    LeaveRequest,
    SystemBranding,
)
from src.database.session import get_db, SessionLocal
from src.server.tenant_middleware import resolve_tenant
from src.server.routes.api_leave import get_or_create_leave_balance
from src.utils.timezone import get_ist_now

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
            detail="Employee authentication required. Please scan your face to log in.",
        )

    payload = decode_employee_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Employee session has expired or is invalid. Please re-authenticate.",
        )

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

    if not student:
        raise HTTPException(status_code=404, detail="Employee record not found.")

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
        raise HTTPException(
            status_code=404,
            detail="No enrolled face profiles found for this organization. Please contact your HR administrator.",
        )

    # 4. Compare Euclidean Distance
    branding = tenant.branding
    threshold = float(branding.self_attendance_face_threshold if branding and branding.self_attendance_face_threshold else 0.52)

    best_match_student = None
    min_dist = float("inf")

    import numpy as np

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
        expires_in_sec=86400,  # 24 hours
    )

    response.set_cookie(
        key=EMP_COOKIE_NAME,
        value=token,
        max_age=86400,
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


@router.get("/attendance")
def get_employee_attendance_history(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 60,
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Returns the authenticated employee's recent punch records and work hours."""
    query = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.tenant_id == student.tenant_id,
            AttendanceRecord.student_id == student.id,
        )
    )

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

    # 3. Calculate earnings
    regular_earnings = (total_regular_hours + paid_leave_hours) * hourly_rate
    overtime_earnings = total_overtime_hours * hourly_rate * ot_mult
    total_gross_earnings = regular_earnings + overtime_earnings

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
    }


# --------------------------------------------------------------------------
# Employee Leave Self-Service Endpoints
# --------------------------------------------------------------------------

@router.get("/leave/balances")
def get_my_leave_balances(
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Returns the employee's current annual leave balances and category quotas."""
    current_year = get_ist_now().year
    leave_types = db.query(LeaveType).filter(LeaveType.tenant_id == student.tenant_id, LeaveType.is_active == True).all()

    balances = []
    for lt in leave_types:
        bal = get_or_create_leave_balance(db, student.tenant_id, student, lt, current_year)
        balances.append(bal.to_dict())

    db.commit()

    return {
        "status": "success",
        "year": current_year,
        "balances": balances,
    }


@router.get("/leave/requests")
def get_my_leave_requests(
    limit: int = 50,
    student: Student = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Returns the authenticated employee's leave applications and approval statuses."""
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

    # Check live balance
    now_ist = get_ist_now()
    req_year = s_date.year
    balance = get_or_create_leave_balance(db, student.tenant_id, student, leave_type, req_year)

    if leave_type.is_paid and balance.remaining_days < total_days:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient leave balance. You requested {total_days} day(s), but only have {balance.remaining_days} day(s) remaining for {leave_type.name}.",
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
    req_year = req.start_date.year if req.start_date else now_ist.year

    # Release pending days from balance
    leave_type = db.query(LeaveType).filter(LeaveType.id == req.leave_type_id).first()
    balance = None
    if leave_type:
        balance = get_or_create_leave_balance(db, student.tenant_id, student, leave_type, req_year)
        balance.pending_days = max(0.0, balance.pending_days - req.total_days)
        balance.remaining_days = max(0.0, balance.total_allocated - balance.used_days - balance.pending_days)
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
